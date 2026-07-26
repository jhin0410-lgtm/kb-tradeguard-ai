"""Manual synthetic smoke test for cross-document reconciliation.

Usage:
    python scripts/document_reconciliation_smoke_test.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intelligence import ReconciliationPolicy, reconcile_trade_documents  # noqa: E402
from src.trade_finance_domain import SourceReference, TradeDocumentProfile  # noqa: E402


def _source(source_id: str) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_name="Synthetic reviewed reconciliation document",
        source_tier="user_provided",
        source_kind="user_document",
        source_locator=f"fixture://{source_id}",
        as_of_date=date.today(),
        effective_date_verified=True,
    )


def main() -> int:
    contract = TradeDocumentProfile(
        document_id="DOC-CONTRACT",
        evidence_id="EVID-CONTRACT",
        document_type="contract",
        currency="USD",
        amount=Decimal("100000"),
        shipment_date=date(2026, 10, 1),
        incoterms_rule="FCA",
        incoterms_year=2020,
        named_place="Busan New Port",
        linked_transaction_ids=["EXP-001"],
        reviewed_fields={
            "seller_name": "Acme Export Co., Ltd.",
            "buyer_name": "Vietnam Buyer JSC",
        },
        source=_source("SRC-CONTRACT"),
        record_status="verified",
    )
    invoice = TradeDocumentProfile(
        document_id="DOC-INVOICE",
        evidence_id="EVID-INVOICE",
        document_type="commercial_invoice",
        currency="EUR",
        amount=Decimal("102000"),
        incoterms_rule="FCA",
        incoterms_year=2020,
        named_place="Busan New Port",
        linked_transaction_ids=["EXP-001"],
        reviewed_fields={
            "seller_name": "ACME EXPORT",
            "buyer_name": "Vietnam Buyer JSC",
        },
        source=_source("SRC-INVOICE"),
        record_status="verified",
    )
    letter_of_credit = TradeDocumentProfile(
        document_id="DOC-LC",
        evidence_id="EVID-LC",
        document_type="letter_of_credit",
        currency="USD",
        amount=Decimal("100000"),
        expiry_date=date(2026, 10, 15),
        linked_transaction_ids=["EXP-001"],
        reviewed_fields={
            "beneficiary_name": "Acme Export Co., Ltd.",
            "applicant_name": "Vietnam Buyer JSC",
            "latest_shipment_date": date(2026, 9, 15),
        },
        source=_source("SRC-LC"),
        record_status="verified",
    )
    policy = ReconciliationPolicy(
        amount_tolerance_percent_by_rule={
            "CONTRACT-INVOICE-AMOUNT": Decimal("2")
        },
        tolerance_basis_by_rule={
            "CONTRACT-INVOICE-AMOUNT": "Reviewed signed contract quantity tolerance"
        },
        tolerance_reference_by_rule={"CONTRACT-INVOICE-AMOUNT": "left"},
        party_aliases={"Acme Export Co., Ltd.": "ACME EXPORT"},
    )
    result = reconcile_trade_documents(
        [contract, invoice, letter_of_credit],
        policy,
    )
    output = {
        "status": "ok",
        "authority_boundary": (
            "Human-reviewed field consistency checks only; mismatches require amendment, "
            "tolerance, alias, and supersession review before interpretation."
        ),
        "comparison_summary": {
            status: sum(1 for item in result.comparisons if item.status == status)
            for status in ("match", "within_tolerance", "mismatch", "skipped")
        },
        "comparisons": [item.model_dump(mode="json") for item in result.comparisons],
        "findings": [item.model_dump(mode="json") for item in result.findings],
        "risk_signals": [item.model_dump(mode="json") for item in result.risk_signals],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
