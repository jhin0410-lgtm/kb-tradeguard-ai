from src.competition_fx_strategy_view import build_fx_consultation_options
from src.competition_topic6 import prepare_topic6_demo_package
from src.demo_scenarios import load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


def _topic6_run():
    package = prepare_topic6_demo_package(load_demo_scenario("oa_high_risk"))
    return run_single_transaction_package(package)


def test_fx_consultation_comparison_covers_baseline_bank_and_insurance_routes():
    options = build_fx_consultation_options(_topic6_run())

    assert [item.option_id for item in options] == [
        "UNHEDGED-BASELINE",
        "KB-FORWARD-CONSULTATION",
        "KSURE-FX-INSURANCE-CONSULTATION",
        "STAGED-HEDGE-DESIGN",
    ]
    assert any("KB" in item.title for item in options)
    assert any("K-SURE" in item.title for item in options)
    assert all(item.required_inputs for item in options)


def test_fx_consultation_comparison_avoids_forecasts_quotes_and_execution_claims():
    text = " ".join(
        part
        for option in build_fx_consultation_options(_topic6_run())
        for part in (
            option.title,
            option.route,
            option.purpose,
            option.tradeoff,
            *option.required_inputs,
        )
    )

    forbidden = ["환율 상승 확정", "최적 헤지비율", "체결환율 확정", "승인 확정", "수익 보장"]
    assert not any(term in text for term in forbidden)
