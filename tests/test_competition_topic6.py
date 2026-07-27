from src.competition_topic6 import prepare_topic6_demo_package
from src.demo_scenarios import load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


def test_topic6_demo_adds_explicit_fx_consultation_without_changing_case_hash():
    package = load_demo_scenario("oa_high_risk")
    before_hash = package.case.case_hash

    prepared = prepare_topic6_demo_package(package)

    assert package.request.product_profiles != prepared.request.product_profiles
    assert prepared.case.case_hash == before_hash
    assert prepared.expected_input_case_hash == before_hash
    assert any(
        profile.declared_needs == ["fx_cashflow_certainty"]
        for profile in prepared.request.product_profiles
    )
    assert any("does not assert hedge suitability" in note for note in prepared.notes)


def test_topic6_preparation_is_idempotent_and_generates_fx_product_candidate():
    package = prepare_topic6_demo_package(load_demo_scenario("oa_high_risk"))
    repeated = prepare_topic6_demo_package(package)
    run = run_single_transaction_package(repeated)

    assert repeated.request.product_profiles == package.request.product_profiles
    assert any(
        candidate.product_category == "foreign_exchange_hedging"
        for candidate in run.updated_case.trade_finance.product_candidates
    )
