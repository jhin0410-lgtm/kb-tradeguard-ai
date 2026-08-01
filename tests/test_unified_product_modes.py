from pathlib import Path

import streamlit_app


def test_public_product_modes_exclude_private_workspace(monkeypatch) -> None:
    monkeypatch.delenv("TRADEGUARD_ENABLE_PRIVATE_WORKSPACE", raising=False)

    assert streamlit_app._available_modes() == ["decision", "portfolio", "evidence"]


def test_private_workspace_is_explicitly_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("TRADEGUARD_ENABLE_PRIVATE_WORKSPACE", "true")

    assert streamlit_app._available_modes() == [
        "decision",
        "analyst",
        "portfolio",
        "evidence",
    ]


def test_unified_decision_desk_restores_sidebar_after_legacy_css() -> None:
    source = Path(streamlit_app.__file__).read_text(encoding="utf-8")

    assert "tg-unified-sidebar-override" in source
    assert "[data-testid='stSidebar']{display:block !important}" in source


def test_presentation_forces_decision_mode(monkeypatch) -> None:
    monkeypatch.setattr(streamlit_app.app, "_flag", lambda name: name == "presentation")
    monkeypatch.setattr(streamlit_app, "_query_value", lambda name, default="": "portfolio")

    assert streamlit_app._active_mode() == "decision"
