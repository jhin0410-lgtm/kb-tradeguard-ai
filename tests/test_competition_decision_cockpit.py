from pathlib import Path


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
    ]
    for marker in required:
        assert marker in text


def test_canonical_entrypoint_uses_four_step_guided_flow() -> None:
    text = Path("streamlit_app.py").read_text(encoding="utf-8")
    expected_order = [
        "render_decision_cockpit(run, scenario_id)",
        "render_decision_charts()",
        "render_product_consultation_section(run, presentation_mode=presentation_mode)",
        "render_kb_handoff()",
        "render_official_case_study_section(presentation_mode=presentation_mode)",
    ]
    positions = [text.index(marker) for marker in expected_order]
    assert positions == sorted(positions)
    for label in ("판정", "시나리오", "금융지원", "근거"):
        assert label in text


def test_mobile_cockpit_contract_is_present() -> None:
    text = Path("src/competition_decision_cockpit.py").read_text(encoding="utf-8")
    assert "@media(max-width:760px)" in text
    assert ".tg-kpi-grid{grid-template-columns:1fr 1fr}" in text
    assert ".tg-next-grid{grid-template-columns:1fr}" in text
