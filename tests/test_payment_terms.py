from datetime import date

import pytest

from src.intelligence.payment_terms import normalize_payment_terms
from src.trade_finance_domain import SourceReference


def _source():
    return SourceReference(
        source_id="SRC-PAYMENT-TERMS",
        source_name="Reviewed payment wording fixture",
        source_tier="user_provided",
        source_kind="user_document",
        source_locator="fixture://payment-terms",
        as_of_date=date(2026, 7, 27),
        effective_date_verified=True,
    )


def test_normalizes_dp_at_sight_without_inventing_tenor():
    result = normalize_payment_terms("Documents against payment (D/P) at sight")

    assert result.instrument == "documentary_collection_dp"
    assert result.availability_type == "sight"
    assert result.tenor_days is None
    assert result.tenor_start_event == "unknown"
    assert result.normalized_trigger == "at sight"
    assert result.unresolved_fields == []


def test_normalizes_da_acceptance_and_preserves_missing_details():
    result = normalize_payment_terms("Documents against acceptance (D/A)")

    assert result.instrument == "documentary_collection_da"
    assert result.availability_type == "acceptance"
    assert result.draft_required is True
    assert "tenor_days" in " ".join(result.unresolved_fields)
    assert "tenor_start_event" in " ".join(result.unresolved_fields)
    assert "acceptance_party" in " ".join(result.unresolved_fields)


def test_normalizes_usance_lc_with_bill_of_lading_anchor():
    result = normalize_payment_terms(
        "Irrevocable L/C available by usance draft at 90 days after B/L date, "
        "accepted by issuing bank"
    )

    assert result.instrument == "letter_of_credit"
    assert result.availability_type == "usance"
    assert result.tenor_days == 90
    assert result.tenor_start_event == "bill_of_lading_date"
    assert result.draft_required is True
    assert result.acceptance_party == "issuing bank"
    assert result.normalized_trigger == "90 days after bill_of_lading_date"
    assert result.unresolved_fields == []


def test_deferred_lc_missing_start_event_remains_partial():
    result = normalize_payment_terms("L/C available by deferred payment 60 days")

    assert result.instrument == "letter_of_credit"
    assert result.availability_type == "deferred_payment"
    assert result.tenor_days == 60
    assert result.tenor_start_event == "unknown"
    assert any("tenor_start_event" in item for item in result.unresolved_fields)


def test_sight_term_rejects_positive_tenor_in_model_contract():
    result = normalize_payment_terms("L/C at sight")
    payload = result.model_dump()
    payload["tenor_days"] = 30

    with pytest.raises(ValueError, match="Sight terms"):
        type(result)(**payload)


def test_normalized_terms_build_existing_payment_structure_and_reviewed_fields():
    result = normalize_payment_terms(
        "D/A 45 days after invoice date, accepted by buyer"
    )
    payment = result.to_payment_structure(
        payment_structure_id="PAY-001",
        transaction_id="EXP-001",
        source=_source(),
        deferred_payment_percent=100,
    )
    fields = result.reviewed_fields()

    assert payment.method == "documentary_collection_da"
    assert payment.tenor_days == 45
    assert payment.payment_trigger == "45 days after invoice_date"
    assert payment.record_status == "verified"
    assert fields["availability_type"] == "acceptance"
    assert fields["acceptance_party"] == "buyer"


def test_unknown_wording_is_not_forced_into_supported_instrument():
    result = normalize_payment_terms("Payment according to mutually agreed milestones")

    assert result.instrument == "other"
    assert result.availability_type == "unknown"
    assert any("instrument" in item for item in result.unresolved_fields)
    assert any("availability_type" in item for item in result.unresolved_fields)
