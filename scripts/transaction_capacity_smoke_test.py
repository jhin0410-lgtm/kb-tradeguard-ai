"""Synthetic smoke test for transaction-to-financial-capacity assessment.

Usage:
    python scripts/transaction_capacity_smoke_test.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.copilot_case import CaseDataAsset, CaseIdentity, UnifiedCopilotCase  # noqa: E402
from src.intelligence import (  # noqa: E402
    TransactionCapacityRequest,
    analyze_transaction_capacity,
)
from src.trade_finance_domain import (  # noqa: E402
    CompanyProfile,
    FinancialStatementSnapshot,
    PaymentStructure,
    SourceReference,
    TradeFinanceDomainState,
)


def _source(source_id: str, source_kind: str = "official_api") -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_name="Synthetic reviewed smoke-test source",
        source_tier="tier_1" if source_kind == "official_api" else "user_provided",
        source_kind=source_kind,
        source_locator=f"fixture://{source_id}",
        as_of_date=date(2025, 12, 31),
        effective_date_verified=True,
    )


def main() -> int:
    company = CompanyProfile(
        company_id="COMPANY-001",
        legal_name="Example Exporter Co., Ltd.",
        sme_status="confirmed",
        source=_source("SRC-COMPANY"),
        record_status="verified",
    )
    statement = FinancialStatementSnapshot(
        statement_id="FS-2025-CFS",
        company_id=company.company_id,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        report_type="annual",
        consolidation_scope="consolidated",
        cash_and_cash_equivalents=Decimal("300000000"),
        short_term_financial_assets=Decimal("100000000"),
        current_assets=Decimal("1000000000"),
        current_liabilities=Decimal("600000000"),
        equity=Decimal("500000000"),
        revenue=Decimal("5000000000"),
        operating_cash_flow=Decimal("180000000"),
        source=_source("SRC-FS"),
        record_status="verified",
    )
    payment = PaymentStructure(
        payment_structure_id="PAY-EXP-001",
        transaction_id="EXP-001",
        method="open_account",
        tenor_days=90,
        deferred_payment_percent=Decimal("100"),
        payment_trigger="90 days after shipment",
        source=_source("SRC-PAY", "user_document"),
        record_status="verified",
    )
    case = UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-CAPACITY-SMOKE",
            company_name=company.legal_name,
            analysis_as_of_date=date.today(),
        ),
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "expected_date": "2026-10-31",
            }
        ],
        official_fx_reference=CaseDataAsset(
            asset_name="reviewed FX reference",
            status="available",
            source="synthetic smoke-test FX",
            as_of_date=date.today(),
            payload=[{"currency": "USD", "spot_rate_krw": 1350}],
        ),
        trade_finance=TradeFinanceDomainState(
            company_profile=company,
            financial_statements=[statement],
            payment_structures=[payment],
        ),
    )
    request = TransactionCapacityRequest(
        assessment_id="CAPACITY-EXP-001",
        transaction_id="EXP-001",
        statement_id=statement.statement_id,
        payment_structure_id=payment.payment_structure_id,
        protection_percent=Decimal("80"),
        pre_shipment_funding_need_krw=Decimal("450000000"),
    )
    analysis = analyze_transaction_capacity(case, request)
    output = {
        "status": "ok",
        "authority_boundary": (
            "Deterministic scale and structural review checks only; no expected-loss, "
            "credit approval, insurance acceptance, pricing, limit, or suitability decision."
        ),
        "request": request.model_dump(mode="json"),
        "calculation_id": analysis.calculation.calculation_id,
        "metrics": [item.model_dump(mode="json") for item in analysis.metrics],
        "risk_signals": [item.model_dump(mode="json") for item in analysis.risk_signals],
        "missing_inputs": analysis.missing_inputs,
        "limitations": analysis.limitations,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
