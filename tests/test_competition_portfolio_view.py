from src.competition_portfolio_view import (
    build_currency_exposure_frame,
    build_liquidity_frame,
    build_official_data_frame,
    build_stress_frame,
)
from src.intelligence.portfolio_assessment import analyze_trade_portfolio
from src.portfolio_demo import build_demo_company_workspace


def test_demo_workspace_contains_isolated_multi_transaction_companies():
    workspace = build_demo_company_workspace()

    assert set(workspace.companies) == {"hanbit", "mirae"}
    assert len(workspace.companies["hanbit"].approved_transactions) == 4
    assert len(workspace.companies["mirae"].approved_transactions) == 3
    assert (
        workspace.companies["hanbit"].identity.case_id
        != workspace.companies["mirae"].identity.case_id
    )


def test_portfolio_view_frames_expose_currency_liquidity_stress_and_data_status():
    case = build_demo_company_workspace().active_case
    assessment = analyze_trade_portfolio(case)

    exposure = build_currency_exposure_frame(assessment)
    liquidity = build_liquidity_frame(assessment)
    stress = build_stress_frame(assessment)
    data = build_official_data_frame(case)

    assert set(exposure["통화"]) == {"USD", "EUR", "JPY"}
    assert list(liquidity["월"]) == ["2026-08", "2026-09", "2026-10"]
    assert set(stress["환율충격(%)"]) == {-10.0, -5.0, 5.0, 10.0}
    assert {
        "kexim_fx_reference",
        "world_bank_country_macro",
        "korea_customs_country_product_trade",
        "opendart_financial_statements",
        "nts_business_status",
    }.issubset(set(data["데이터"]))
