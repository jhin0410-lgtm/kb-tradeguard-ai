from pathlib import Path

import src.competition_decision_cockpit as cockpit
from src.competition_topic6 import prepare_topic6_demo_package
from src.demo_scenarios import load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


def _run(scenario_id: str = "oa_high_risk"):
    return run_single_transaction_package(
        prepare_topic6_demo_package(load_demo_scenario(scenario_id))
    )


def test_decision_cockpit_module_contains_required_ui_contracts() -> None:
    text = Path("src/competition_decision_cockpit.py").read_text(encoding="utf-8")
    required = [
        "TRADE DECISION COCKPIT",
        "render_guided_nav",
        "render_decision_cockpit",
        "build_decision_chart_frames",
        "render_decision_charts",
        "render_kb_handoff",
        "render_usability_evidence",
        "FX 스트레스",
        "자연헤지 후 실제 통화별 순노출",
        "검토된 월별 예상 기말현금",
        "analyze_trade_portfolio(run.updated_case)",
        "run.assessment_result.brief",
        "st.container(border=True)",
    ]
    for marker in required:
        assert marker in text
    assert "정규화 지수" not in text


def test_cockpit_renders_governed_package_run(monkeypatch) -> None:
    run = _run()
    rendered: list[str] = []
    monkeypatch.setattr(cockpit.st, "markdown", lambda body, **kwargs: rendered.append(str(body)))

    cockpit.render_decision_cockpit(run, "oa_high_risk")

    html = "\n".join(rendered)
    transaction = run.updated_case.approved_transactions[0]
    brief = run.assessment_result.brief
    assert str(transaction["currency"]) in html
    assert f'{float(transaction["amount_fc"]):,.0f}' in html
    assert cockpit._DISPOSITION_LABELS[brief.disposition] in html
    assert brief.action_plan[0].title in html
    assert "₩" not in html


def test_decision_chart_frames_use_actual_governed_transaction_amounts() -> None:
    run = _run()
    frames, _ = cockpit.build_decision_chart_frames(run)
    transaction = run.updated_case.approved_transactions[0]
    exposure = frames["exposure"].set_index("통화")

    assert not exposure.empty
    assert exposure.loc[transaction["currency"], "수출채권"] == float(transaction["amount_fc"])
    assert set(frames) == {"exposure", "stress", "liquidity"}


def test_canonical_entrypoint_uses_four_step_guided_flow() -> None:
    text = Path("streamlit_app.py").read_text(encoding="utf-8")
    expected_order = [
        "render_decision_cockpit(run, scenario_id)",
        "render_decision_charts(run)",
        "render_product_consultation_section(run, presentation_mode=presentation_mode)",
        "render_kb_handoff()",
    ]
    positions = [text.index(marker) for marker in expected_order]
    assert positions == sorted(positions)
    for label in ("판정", "시나리오", "금융지원", "근거"):
        assert label in text
    assert 'id="final-audit"' in text
    assert 'href="#final-audit"' in text
    assert "render_top_product_candidates" not in text
    assert 'with st.expander("상세 분석·공식 데이터·AI 구조"' in text


def test_mobile_cockpit_contract_is_present() -> None:
    text = Path("src/competition_decision_cockpit.py").read_text(encoding="utf-8")
    assert "@media(max-width:760px)" in text
    assert ".tg-kpi-grid{grid-template-columns:1fr 1fr}" in text
    assert ".tg-next-grid{grid-template-columns:1fr}" in text


def test_top_three_products_are_governed_not_scenario_static() -> None:
    product_text = Path("src/competition_product_view.py").read_text(encoding="utf-8")
    entrypoint = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "build_product_consultation_cards(run, limit=3)" in product_text
    assert "Decision Brief" in product_text
    assert "시나리오별 고정 목록이 아니며" in product_text
    assert "competition_top_products" not in entrypoint


def test_usability_protocol_and_empty_template_are_present() -> None:
    protocol = Path("docs/USABILITY_TEST_PROTOCOL.md").read_text(encoding="utf-8")
    template = Path("data/usability_test_results_template.csv").read_text(encoding="utf-8")
    assert "3분" in protocol
    assert "결과를 임의 생성하지 않습니다" in protocol
    assert "summarize_usability_results.py" in protocol
    assert "participant_id" in template
    assert "P05" in template
