from datetime import date

import pytest

from src.copilot_case import CaseIdentity, UnifiedCopilotCase
from src.intelligence import TradeFinanceNeedProfile, apply_product_matching


def test_product_profile_direction_must_match_approved_transaction():
    case = UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-PRODUCT-DIRECTION",
            analysis_as_of_date=date(2026, 7, 26),
        ),
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 100000,
                "expected_date": "2026-10-31",
            }
        ],
    )
    conflicting_profile = TradeFinanceNeedProfile(
        profile_id="NEED-CONFLICT-001",
        transaction_id="EXP-001",
        transaction_direction="import",
        transaction_stage="pre_payment",
        declared_needs=["import_working_capital"],
        company_size="sme",
        tenor_days=180,
        industry_tags=["defense"],
    )

    with pytest.raises(ValueError, match="direction conflicts"):
        apply_product_matching(case, [conflicting_profile])
