from pathlib import Path


def test_decision_desk_removes_duplicate_verdict_and_action_sections() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")

    assert "app._render_verdict(run)" not in source
    assert "app._render_actions(run" not in source
    assert "01 · 통합 거래 판정" in source
    assert "05 · 문서·재무·실행 상세" in source
    assert "06 · 근거·검증·감사" in source


def test_decision_journey_uses_five_connected_anchors() -> None:
    cockpit = Path("src/competition_decision_cockpit.py").read_text(encoding="utf-8")
    product = Path("src/competition_product_view.py").read_text(encoding="utf-8")

    for marker in (
        'href="#summary"',
        'href="#evidence"',
        'href="#scenarios"',
        'href="#products"',
        'href="#final-audit"',
    ):
        assert marker in cockpit
    assert "03 · FX·유동성 위험 시나리오" in cockpit
    assert "04 · 금융지원·다음 행동" in product
