from pathlib import Path

import src.competition_decision_cockpit as cockpit
from src.competition_topic6 import prepare_topic6_demo_package
from src.demo_scenarios import load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


def test_decision_cockpit_module_contains_required_ui_contracts() -> None:
    text = Path("src/competition_decision_cockpit.py").read_text(encoding="utf-8")
    required = [
        "TRADE DECISION COCKPIT",
        "render_guided_nav",
        "render_decision_cockpit",
        "render_decision_charts",
        "render_kb_handoff",
        "render_usability_evidence",
        "FX 스트레스",
        "자연헤지 후 순노출",
        "예상 현금흐름 Timeline",
        "run.updated_case",
        "run.assessment_result.brief",
        "st.container(border=True)",
    ]
    for marker in required:
        assert marker in text


def test_cockpit_renders_governed_package_run(monkeypatch) -> None:
    run = run_single_transaction_package(
        prepare_topic6_demo_package(load_demo_scenario("oa_high_risk"))
    )
    rendered: list[str] = []
    monkeypatch.setattr(
        cockpit.st,
        "markdown",
        lambda body, **kwargs: rendered.append(str(body)),
    )

    cockpit.render_decision_cockpit(run, "oa_high_risk")

    html = "\n".join(rendered)
    transaction = run.updated_case.approved_transactions[0]
    brief = run.assessment_result.brief
    assert str(transaction["currency"]) in html
    assert f'{float(transaction["amount_fc"]):,.0f}' in html
    assert cockpit._DISPOSITION_LABELS[brief.disposition] in html
    assert brief.action_plan[0].title in html
    assert "₩" not in html


def test_canonical_entrypoint_uses_four_step_guided_flow() -> None:
    text = Path("streamlit_app.py").read_text(encoding="utf-8")
    expected_order = [
        "render_decision_cockpit(run, scenario_id)",
        "render_decision_charts()",
        "render_top_product_candidates(scenario_id)",
        "render_product_consultation_section(run, presentation_mode=presentation_mode)",
        "render_kb_handoff()",
        "render_official_case_study_section(presentation_mode=presentation_mode)",
    ]
    positions = [text.index(marker) for marker in expected_order]
    assert positions == sorted(positions)
    for label in ("판정", "시나리오", "금융지원", "근거"):
        assert label in text
    assert 'id="final-audit"' in text
    assert 'href="#final-audit"' in text


def test_mobile_cockpit_contract_is_present() -> None:
    text = Path("src/competition_decision_cockpit.py").read_text(encoding="utf-8")
    assert "@media(max-width:760px)" in text
    assert ".tg-kpi-grid{grid-template-columns:1fr 1fr}" in text
    assert ".tg-next-grid{grid-template-columns:1fr}" in text


def test_top_three_product_summary_has_explicit_boundaries() -> None:
    text = Path("src/competition_top_products.py").read_text(encoding="utf-8")
    assert "PRIORITY" in text
    assert "가입 가능성·승인·금리·한도·보험 인수를 확정하지 않습니다" in text
    assert "선정 이유" in text
    assert "미확인" in text
    assert "다음 행동" in text


def test_usability_protocol_and_empty_template_are_present() -> None:
    protocol = Path("docs/USABILITY_TEST_PROTOCOL.md").read_text(encoding="utf-8")
    template = Path("data/usability_test_results_template.csv").read_text(encoding="utf-8")
    assert "3분" in protocol
    assert "결과를 임의 생성하지 않습니다" in protocol
    assert "participant_id" in template
    assert "P05" in template
