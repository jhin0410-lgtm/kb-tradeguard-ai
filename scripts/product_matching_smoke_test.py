"""Manual synthetic smoke test for consultation-candidate product matching.

Usage:
    python scripts/product_matching_smoke_test.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intelligence import (  # noqa: E402
    TradeFinanceNeedProfile,
    match_trade_finance_products,
)


def main() -> int:
    profile = TradeFinanceNeedProfile(
        profile_id="NEED-VIETNAM-EXPORT-001",
        transaction_id="EXP-001",
        transaction_direction="export",
        transaction_stage="pre_shipment",
        declared_needs=[
            "buyer_credit_investigation",
            "export_receivable_nonpayment_protection",
            "pre_shipment_working_capital",
            "fx_cashflow_certainty",
        ],
        company_size="sme",
        payment_method="open_account",
        tenor_days=90,
        preferred_bank="KB국민은행",
        available_documents=["수출계약 또는 발주서"],
    )
    result = match_trade_finance_products([profile])
    output = {
        "status": "ok",
        "authority_boundary": (
            "Public-condition consultation candidates only; no eligibility, approval, "
            "pricing, limit, insurance acceptance, guarantee issuance, or suitability decision."
        ),
        "profile": profile.model_dump(mode="json"),
        "status_counts": {},
        "product_candidates": [
            item.model_dump(mode="json") for item in result.product_candidates
        ],
        "consultation_requirements": [
            item.model_dump(mode="json")
            for item in result.consultation_requirements
        ],
    }
    for item in result.product_candidates:
        output["status_counts"][item.candidate_status] = (
            output["status_counts"].get(item.candidate_status, 0) + 1
        )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
