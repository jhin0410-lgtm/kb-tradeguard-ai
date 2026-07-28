from datetime import date
from decimal import Decimal

import pytest

from src.copilot_case import CaseEvidenceItem, CaseIdentity, UnifiedCopilotCase
from src.intelligence import apply_trade_document_screening
from src.trade_finance_domain import (
    PaymentStructure,
    SourceReference,
    TradeDocumentProfile,
    TradeFinanceDomainState,
)


def _source(source_id="SRC-DOC"):
    return SourceReference(
        source_id=source_id,
        source_name="Reviewed synthetic contract",
        source_tier="user_provided",
        source_kind="user_document",
        source_locator="fixture://contract",
        as_of_date=date(2026, 7, 27),
        effective_date_verified=True,
    )


def _case(evidence_status="approved", named_place=None):
    payment = PaymentStructure(
        payment_structure_id="PAY-001",
        transaction_id="EXP-001",
        method="open_account",
        tenor_days=90,
        deferred_payment_percent=Decimal("100"),
        payment_trigger="Payment 90 days after shipment",
        source=_source("SRC-PAY"),
        record_status="verified",
    )
    contract = TradeDocumentProfile(
        document_id="DOC-001",
        evidence_id="EVID-001",
        document_type="contract",
        incoterms_rule="FCA",
        incoterms_year=2020,
        named_place=named_place,
        payment_structure_id=payment.payment_structure_id,
        linked_transaction_ids=["EXP-001"],
        reviewed_fields={
            "governing_law": "Republic of Korea",
            "dispute_resolution": "KCAB International arbitration",
            "acceptance_period_days": 10,
            "buyer_unilateral_setoff_right": False,
            "buyer_unilateral_amendment_right": False,
        },
        source=_source(),
        record_status="verified",
    )
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-DOC-ASSESSMENT",
            analysis_as_of_date=date(2026, 7, 27),
        ),
        evidence=[
            CaseEvidenceItem(
                evidence_id="EVID-001",
                evidence_type="contract",
                source_name="contract.pdf",
                status=evidence_status,
                linked_transaction_ids=["EXP-001"],
            )
        ],
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "expected_date": "2026-10-31",
            }
        ],
        trade_finance=TradeFinanceDomainState(
            payment_structures=[payment],
            trade_documents=[contract],
        ),
    )


def test_screening_attaches_findings_and_signals_without_mutating_original():
    case = _case()
    before = case.case_hash

    updated, outcome = apply_trade_document_screening(case)

    assert case.trade_finance.clause_findings == []
    assert case.trade_finance.risk_signals == []
    assert case.case_hash == before
    assert outcome.case_before_hash == before
    assert outcome.case_after_hash == updated.case_hash
    assert outcome.evaluated_document_ids == ["DOC-001"]
    assert len(updated.trade_finance.clause_findings) == 1
    assert len(updated.trade_finance.risk_signals) == 1
    assert "INCOTERMS-PLACE-MISSING" in outcome.clause_finding_ids[0]
    assert updated.trade_finance.risk_signals[0].clause_finding_ids == outcome.clause_finding_ids


def test_screening_requires_approved_case_evidence():
    with pytest.raises(ValueError, match="approved case evidence"):
        apply_trade_document_screening(_case(evidence_status="review_required"))


def test_screening_requires_referenced_payment_structure():
    case = _case()
    broken_domain = case.trade_finance.model_copy(update={"payment_structures": []})
    broken = case.model_copy(update={"trade_finance": broken_domain})

    with pytest.raises(ValueError, match="missing payment structure"):
        apply_trade_document_screening(broken)


def test_screening_is_idempotent_for_same_reviewed_snapshot():
    first, first_outcome = apply_trade_document_screening(_case())
    second, second_outcome = apply_trade_document_screening(first)

    assert len(second.trade_finance.clause_findings) == len(first.trade_finance.clause_findings)
    assert len(second.trade_finance.risk_signals) == len(first.trade_finance.risk_signals)
    assert second.case_hash == first.case_hash
    assert second_outcome.clause_finding_ids == first_outcome.clause_finding_ids


def test_resolved_document_rule_removes_stale_prior_finding():
    first, _ = apply_trade_document_screening(_case())
    corrected = _case(named_place="Busan New Port")
    corrected_domain = corrected.trade_finance.model_copy(
        update={
            "clause_findings": first.trade_finance.clause_findings,
            "risk_signals": first.trade_finance.risk_signals,
        }
    )
    corrected_case = corrected.model_copy(update={"trade_finance": corrected_domain})

    updated, outcome = apply_trade_document_screening(corrected_case)

    assert outcome.clause_finding_ids == []
    assert not any(
        item.source.source_id.startswith("TRADE-DOCUMENT-RULES-")
        for item in updated.trade_finance.clause_findings
    )
    assert not any(
        item.source.source_id.startswith("TRADE-DOCUMENT-RULES-")
        for item in updated.trade_finance.risk_signals
    )


def test_registry_upgrade_replaces_prior_version_findings_and_signals():
    first, _ = apply_trade_document_screening(_case())
    old_source_id = "TRADE-DOCUMENT-RULES-trade-document-rules/1.0"
    stale_findings = [
        item.model_copy(
            update={
                "source": item.source.model_copy(update={"source_id": old_source_id})
            }
        )
        for item in first.trade_finance.clause_findings
    ]
    stale_signals = [
        item.model_copy(
            update={
                "source": item.source.model_copy(update={"source_id": old_source_id})
            }
        )
        for item in first.trade_finance.risk_signals
    ]
    corrected = _case(named_place="Busan New Port")
    corrected_domain = corrected.trade_finance.model_copy(
        update={
            "clause_findings": stale_findings,
            "risk_signals": stale_signals,
        }
    )
    corrected_case = corrected.model_copy(update={"trade_finance": corrected_domain})

    updated, outcome = apply_trade_document_screening(corrected_case)

    assert outcome.clause_finding_ids == []
    assert outcome.risk_signal_ids == []
    assert not any(
        item.source.source_id == old_source_id
        for item in updated.trade_finance.clause_findings
    )
    assert not any(
        item.source.source_id == old_source_id
        for item in updated.trade_finance.risk_signals
    )


def test_removed_document_discards_stale_rule_outputs():
    first, _ = apply_trade_document_screening(_case())
    removed_domain = first.trade_finance.model_copy(update={"trade_documents": []})
    removed_case = first.model_copy(update={"trade_finance": removed_domain})

    updated, outcome = apply_trade_document_screening(removed_case)

    assert outcome.evaluated_document_ids == []
    assert outcome.clause_finding_ids == []
    assert outcome.risk_signal_ids == []
    assert not any(
        item.source.source_id.startswith("TRADE-DOCUMENT-RULES-")
        for item in updated.trade_finance.clause_findings
    )
    assert not any(
        item.source.source_id.startswith("TRADE-DOCUMENT-RULES-")
        for item in updated.trade_finance.risk_signals
    )
    reloaded = UnifiedCopilotCase.model_validate(updated.model_dump(mode="python"))
    assert reloaded.case_hash == updated.case_hash


def test_unsupported_document_type_discards_stale_rule_outputs():
    first, _ = apply_trade_document_screening(_case())
    unsupported_documents = [
        item.model_copy(update={"document_type": "commercial_invoice"})
        for item in first.trade_finance.trade_documents
    ]
    unsupported_domain = first.trade_finance.model_copy(
        update={"trade_documents": unsupported_documents}
    )
    unsupported_case = first.model_copy(update={"trade_finance": unsupported_domain})

    updated, outcome = apply_trade_document_screening(unsupported_case)

    assert outcome.evaluated_document_ids == []
    assert outcome.clause_finding_ids == []
    assert outcome.risk_signal_ids == []
    assert not any(
        item.source.source_id.startswith("TRADE-DOCUMENT-RULES-")
        for item in updated.trade_finance.clause_findings
    )
    assert not any(
        item.source.source_id.startswith("TRADE-DOCUMENT-RULES-")
        for item in updated.trade_finance.risk_signals
    )
