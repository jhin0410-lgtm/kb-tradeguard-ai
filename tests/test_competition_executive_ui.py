from pathlib import Path

from src.competition_executive_ui import (
    STAGE_LABELS,
    build_executive_model,
    build_exposure_waterfall,
    build_fx_stress_figure,
    build_handoff_payload,
    build_liquidity_figure,
    provider_configuration_status,
)
from src.competition_topic6 import prepare_topic6_demo_package
from src.demo_scenarios import load_demo_scenario
from src.intelligence.portfolio_assessment import analyze_trade_portfolio
from src.intelligence.single_transaction_package import run_single_transaction_package
from src.portfolio_demo import build_demo_company_workspace


def _run_and_assessment():
    package = prepare_topic6_demo_package(load_demo_scenario("oa_high_risk"))
    run = run_single_transaction_package(package)
    assessment = analyze_trade_portfolio(build_demo_company_workspace().active_case)
    return run, assessment


def test_executive_model_prioritizes_three_or_fewer_consultation_candidates():
    run, assessment = _run_and_assessment()
    model = build_executive_model(run)

    assert model.transaction_label
    assert "금액 확인" not in model.transaction_label
    assert "USD" in model.transaction_label
    assert model.disposition_headline
    assert model.top_risk_title
    assert len(model.product_cards) <= 3
    assert model.missing_information_count >= 0


def test_financial_story_figures_are_populated_from_governed_portfolio_outputs():
    _, assessment = _run_and_assessment()

    stress = build_fx_stress_figure(assessment)
    liquidity = build_liquidity_figure(assessment)
    exposure = build_exposure_waterfall(assessment)

    assert stress.data
    assert liquidity.data
    assert exposure.data
    assert "환율" in stress.layout.title.text
    assert "기말현금" in liquidity.layout.title.text
    assert exposure.layout.title.text == "EUR 노출 구성"


def test_consultation_handoff_preserves_boundary_and_references():
    run, assessment = _run_and_assessment()
    model = build_executive_model(run)
    payload = build_handoff_payload(run, model)

    assert payload["schema_version"] == "kb-tradeguard-consultation-handoff/1.0"
    assert payload["case_id"] == run.updated_case.identity.case_id
    assert payload["brief_reference_ids"]
    assert payload["top_risks"]
    assert payload["priority_actions"]
    assert len(payload["consultation_candidates"]) <= 3
    assert "No approval" in payload["authority_boundary"]
    combined = str(payload)
    assert "승인 확정" not in combined
    assert "확정 금리" not in combined


def test_guided_ui_has_exactly_four_customer_facing_stages():
    assert list(STAGE_LABELS) == ["decision", "scenarios", "support", "evidence"]
    assert list(STAGE_LABELS.values()) == ["1 · 판정", "2 · 시나리오", "3 · 금융지원", "4 · 근거"]


def test_official_api_status_matrix_is_explicit_about_public_and_secret_paths(monkeypatch):
    for name in (
        "KEXIM_API_KEY",
        "KCS_TRADE_API_KEY",
        "DATA_GO_KR_SERVICE_KEY",
        "BOK_ECOS_API_KEY",
        "OPENDART_API_KEY",
        "NTS_BUSINESS_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    rows = provider_configuration_status()
    by_provider = {row["provider"]: row for row in rows}

    assert len(rows) == 7
    assert by_provider["World Bank"]["state"] == "public"
    assert by_provider["UN Comtrade"]["state"] == "public"
    assert by_provider["KEXIM"]["state"] == "missing"
    assert by_provider["관세청"]["state"] == "missing"
    assert by_provider["OpenDART"]["state"] == "missing"

    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "configured-for-test")
    configured = {row["provider"]: row for row in provider_configuration_status()}
    assert configured["국세청"]["state"] == "configured"


def test_canonical_entrypoint_uses_guided_decision_cockpit_order():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")

    hero = source.index("render_executive_hero()")
    selector = source.index("active_stage = render_stage_selector()")
    decision = source.index("model = _render_decision_stage(run, presentation_mode=True)")
    scenarios = source.index("_render_scenario_stage(assessment, presentation_mode=True)")
    support = source.index("render_financial_support(run, model, presentation_mode=True)")
    evidence = source.index("_render_evidence_stage(run, scenario_id, presentation_mode=True)")

    assert hero < selector
    assert decision < scenarios < support < evidence
    assert "render_compact_stage_header(requested_stage)" in source
    assert "데모 설정·전체 6단계 처리 흐름" in source
    assert "render_mobile_stage_nav" in source
    assert "study=true" in Path("src/competition_executive_ui.py").read_text(encoding="utf-8")
    assert "단일 거래 Fixture" in source
    assert "별도 다중 거래 포트폴리오" in source
