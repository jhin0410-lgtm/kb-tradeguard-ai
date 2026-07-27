from datetime import date

import pytest

from src.intelligence.trade_document_rules import evaluate_trade_document
from src.trade_finance_domain import (
    PaymentStructure,
    SourceReference,
    TradeDocumentProfile,
)


def _source(source_id: str) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_name="Reviewed synthetic date fixture",
        source_tier="user_provided",
        source_kind="user_document",
        source_locator=f"fixture://{source_id}",
        as_of_date=date(2026, 7, 27),
        effective_date_verified=True,
    )


def _payment() -> PaymentStructure:
    return PaymentStructure(
        payment_structure_id="PAY-LC-DATE",
        transaction_id="EXP-DATE-001",
        method="letter_of_credit",
        issuing_bank="Example International Bank",
        governing_rules=["UCP 600"],
        source=_source("SRC-PAY-DATE"),
        record_status="verified",
    )


def _document(latest_shipment_date: str) -> TradeDocumentProfile:
    return TradeDocumentProfile(
        document_id="DOC-LC-DATE",
        evidence_id="EVID-LC-DATE",
        document_type="letter_of_credit",
        expiry_date=date(2026, 9, 15),
        payment_structure_id="PAY-LC-DATE",
        linked_transaction_ids=["EXP-DATE-001"],
        reviewed_fields={
            "latest_shipment_date": latest_shipment_date,
            "presentation_period_days": 21,
            "buyer_controlled_document_requirements": [],
            "expiry_place": "Seoul, Republic of Korea",
            "availability_type": "sight",
            "tenor_start_event": "unknown",
            "draft_required": False,
            "draft_tenor_text": None,
            "acceptance_party": None,
        },
        source=_source("SRC-DOC-DATE"),
        record_status="verified",
    )


def test_iso_date_in_reviewed_fields_is_compared_as_a_date():
    findings = evaluate_trade_document(_document("2026-10-01"), _payment())

    assert any(
        "LC-EXPIRY-BEFORE-SHIPMENT" in item.clause_finding_id
        for item in findings
    )


def test_malformed_reviewed_date_fails_closed_with_field_context():
    with pytest.raises(ValueError, match="latest_shipment_date.*ISO YYYY-MM-DD"):
        evaluate_trade_document(_document("01/10/2026"), _payment())
