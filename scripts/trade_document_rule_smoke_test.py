"""Manual synthetic smoke test for governed contract and L/C screening.

Usage:
    python scripts/trade_document_rule_smoke_test.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intelligence import evaluate_trade_document  # noqa: E402
from src.trade_finance_domain import (  # noqa: E402
    PaymentStructure,
    SourceReference,
    TradeDocumentProfile,
)


def _source(source_id: str) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_name="Synthetic reviewed smoke-test document",
        source_tier="user_provided",
        source_kind="user_document",
        source_locator="fixture://trade-document-smoke-test",
        as_of_date=date.today(),
        effective_date_verified=True,
    )


def main() -> int:
    contract_payment = PaymentStructure(
        payment_structure_id="PAY-CONTRACT-001",
        transaction_id="EXP-001",
        method="open_account",
        tenor_days=90,
        deferred_payment_percent=Decimal("100"),
        payment_trigger="Payment 90 days after buyer acceptance",
        source=_source("SRC-PAY-CONTRACT"),
        record_status="verified",
    )
    contract = TradeDocumentProfile(
        document_id="DOC-CONTRACT-001",
        evidence_id="EVID-CONTRACT-001",
        document_type="contract",
        incoterms_rule="FCA",
        incoterms_year=2020,
        named_place=None,
        payment_structure_id=contract_payment.payment_structure_id,
        linked_transaction_ids=["EXP-001"],
        reviewed_fields={
            "governing_law": None,
            "dispute_resolution": None,
            "acceptance_period_days": None,
            "buyer_unilateral_setoff_right": True,
            "buyer_unilateral_amendment_right": False,
        },
        source=_source("SRC-CONTRACT"),
        record_status="verified",
    )

    lc_payment = PaymentStructure(
        payment_structure_id="PAY-LC-001",
        transaction_id="EXP-001",
        method="letter_of_credit",
        issuing_bank="Example International Bank",
        irrevocable=True,
        governing_rules=["Local law only"],
        source=_source("SRC-PAY-LC"),
        record_status="verified",
    )
    lc = TradeDocumentProfile(
        document_id="DOC-LC-001",
        evidence_id="EVID-LC-001",
        document_type="letter_of_credit",
        expiry_date=date(2026, 9, 15),
        payment_structure_id=lc_payment.payment_structure_id,
        linked_transaction_ids=["EXP-001"],
        reviewed_fields={
            "latest_shipment_date": date(2026, 10, 1),
            "presentation_period_days": 0,
            "buyer_controlled_document_requirements": [
                "Acceptance certificate issued only by applicant"
            ],
            "expiry_place": None,
        },
        source=_source("SRC-LC"),
        record_status="verified",
    )

    contract_findings = evaluate_trade_document(contract, contract_payment)
    lc_findings = evaluate_trade_document(lc, lc_payment)
    output = {
        "status": "ok",
        "authority_boundary": (
            "Deterministic screening of reviewed structured fields only; not legal advice, "
            "documentary-compliance certification, or a bank decision."
        ),
        "contract_findings": [item.model_dump(mode="json") for item in contract_findings],
        "letter_of_credit_findings": [item.model_dump(mode="json") for item in lc_findings],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
