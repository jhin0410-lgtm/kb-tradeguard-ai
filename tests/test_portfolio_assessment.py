from datetime import date
from decimal import Decimal

import pytest

from src.copilot_case import CaseDataAsset, CaseIdentity, UnifiedCopilotCase
from src.intelligence.portfolio_assessment import (
    CompanyPortfolioWorkspace,
    analyze_trade_portfolio,
    infer_portfolio_need_profiles,
    match_portfolio_products,
)


def _case(**updates):
    payload = {
        "identity": CaseIdentity(
            case_id="CASE-PORTFOLIO-001",
            company_name="Portfolio Exporter",
            analysis_as_of_date=date(2026, 7, 28),
        ),
        "approved_transactions": [
            {
                "transaction_id": "EXP-USD-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "probability": 1,
                "expected_date": "2026-09-30",
                "status": "pre_shipment",
                "payment_method": "open_account",
                "company_size": "sme",
                "preferred_bank": "KB국민은행",
                "available_documents": ["수출계약 또는 발주서"],
            },
            {
                "transaction_id": "IMP-USD-001",
                "transaction_type": "import",
                "currency": "USD",
                "amount_fc": 200000,
                "probability": 1,
                "expected_date": "2026-08-31",
                "status": "confirmed",
                "payment_method": "usance L/C",
                "tenor_days": 120,
                "company_size": "sme",
                "preferred_bank": "KB국민은행",
                "industry_tags": ["materials_parts_equipment"],
                "available_documents": ["수입계약", "Invoice"],
            },
            {
                "transaction_id": "IMP-JPY-001",
                "transaction_type": "import",
                "currency": "JPY",
                "amount_fc": 10000000,
                "probability": 0.5,
                "expected_date": "2026-10-31",
                "status": "confirmed",
                "payment_method": "advance payment",
                "advance_payment_percent": 30,
                "company_size": "sme",
                "preferred_bank": "KB국민은행",
                "available_documents": ["선급금 조건이 포함된 수입계약"],
            },
        ],
        "foreign_cash_positions": [{"currency": "USD", "amount_fc": 50000}],
        "monthly_cost_assumptions": {
            "current_cash_krw": 300000000,
            "monthly_fixed_cost_krw": 50000000,
        },
        "official_fx_reference": CaseDataAsset(
            asset_name="reviewed rates",
            status="available",
            source="fixture",
            as_of_date=date(2026, 7, 28),
            payload=[
                {"currency": "USD", "spot_rate_krw": 1350},
                {"currency_unit": "JPY(100)", "deal_base_rate": 910},
            ],
        ),
    }
    payload.update(updates)
    return UnifiedCopilotCase(**payload)


def test_portfolio_aggregates_currency_exposure_and_normalizes_rate_units():
    assessment = analyze_trade_portfolio(_case())
    by_currency = {item.currency: item for item in assessment.currency_exposures}

    usd = by_currency["USD"]
    assert usd.export_receivables_fc == Decimal("500000")
    assert usd.import_payables_fc == Decimal("200000")
    assert usd.foreign_cash_fc == Decimal("50000")
    assert usd.natural_offset_fc == Decimal("200000")
    assert usd.natural_hedge_ratio_percent == Decimal("40.00")
    assert usd.net_exposure_fc == Decimal("350000")
    assert usd.net_exposure_krw == Decimal("472500000")

    jpy = by_currency["JPY"]
    assert jpy.reference_rate_krw == Decimal("9.1")
    assert jpy.net_direction == "short"
    assert assessment.gross_exposure_krw == Decimal("1036000000")
    assert assessment.net_exposure_krw == Decimal("381500000")


def test_portfolio_builds_probability_weighted_monthly_liquidity_and_stress():
    assessment = analyze_trade_portfolio(_case())
    by_month = {item.period: item for item in assessment.liquidity_buckets}

    assert list(by_month) == ["2026-08", "2026-09", "2026-10"]
    assert by_month["2026-08"].expected_outflow_krw == Decimal("270000000")
    assert by_month["2026-09"].expected_inflow_krw == Decimal("675000000")
    assert by_month["2026-10"].expected_outflow_krw == Decimal("45500000")
    assert by_month["2026-10"].ending_cash_krw == Decimal("509500000")

    stress = {item.shock_percent: item for item in assessment.stress_points}
    assert stress[Decimal("10")].estimated_fx_value_change_krw == Decimal("38150000")
    assert stress[Decimal("-10")].estimated_fx_value_change_krw == Decimal("-38150000")


def test_missing_rate_is_disclosed_and_prevents_total_krw_claim():
    case = _case(
        official_fx_reference=CaseDataAsset(
            asset_name="USD only",
            status="available",
            source="fixture",
            payload={"USD": 1350},
        )
    )
    assessment = analyze_trade_portfolio(case)

    assert assessment.gross_exposure_krw is None
    assert assessment.net_exposure_krw is None
    assert "FX reference for currency: JPY" in assessment.missing_inputs
    october = next(
        item for item in assessment.liquidity_buckets if item.period == "2026-10"
    )
    assert october.missing_currency_rates == ["JPY"]


def test_invalid_or_duplicate_transactions_fail_closed():
    duplicate = [dict(item) for item in _case().approved_transactions]
    duplicate[1]["transaction_id"] = duplicate[0]["transaction_id"]
    with pytest.raises(ValueError, match="IDs must be unique"):
        analyze_trade_portfolio(_case(approved_transactions=duplicate))

    invalid = [dict(item) for item in _case().approved_transactions]
    invalid[0]["amount_fc"] = 0
    with pytest.raises(ValueError):
        analyze_trade_portfolio(_case(approved_transactions=invalid))


def test_portfolio_profiles_and_products_remain_transaction_scoped():
    case = _case()
    profiles = infer_portfolio_need_profiles(case)
    by_transaction = {item.transaction_id: item for item in profiles}

    assert "forward_exchange_hedging" in by_transaction["EXP-USD-001"].declared_needs
    assert "import_letter_of_credit" in by_transaction["IMP-USD-001"].declared_needs
    assert "import_usance_financing" in by_transaction["IMP-USD-001"].declared_needs
    assert (
        "import_advance_payment_protection"
        in by_transaction["IMP-JPY-001"].declared_needs
    )

    _, result = match_portfolio_products(case)
    payment_usance = next(
        item
        for item in result.product_candidates
        if item.product_or_service_name == "KB Payment Usance"
    )
    assert payment_usance.linked_transaction_ids == ["IMP-USD-001"]
    assert payment_usance.candidate_status == "consultation_candidate"
    assert any(
        item.product_or_service_name == "KB 수입신용장 개설 상담"
        and item.linked_transaction_ids == ["IMP-USD-001"]
        for item in result.product_candidates
    )


def test_company_workspace_switches_cases_without_combining_them():
    first = _case()
    second = _case(
        identity=CaseIdentity(
            case_id="CASE-PORTFOLIO-002",
            company_name="Second Company",
            analysis_as_of_date=date(2026, 7, 28),
        )
    )
    workspace = CompanyPortfolioWorkspace(
        workspace_id="WORKSPACE-001",
        companies={"first": first, "second": second},
        active_company_id="first",
    )

    switched = workspace.switch_company("second")

    assert workspace.active_case.identity.case_id == "CASE-PORTFOLIO-001"
    assert switched.active_case.identity.case_id == "CASE-PORTFOLIO-002"
    assert switched.operating_scope.startswith("One analyst")
