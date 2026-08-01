from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_streamlit_entrypoint_exposes_connected_product_modes():
    source = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")

    assert "_available_modes" in source
    assert "TRADEGUARD_ENABLE_PRIVATE_WORKSPACE" in source
    assert "render_workflow_map()" in source
    assert "render_portfolio_section(presentation_mode=False, case=run.updated_case)" in source
    assert "render_official_case_study_section(presentation_mode=False)" in source
    assert "render_official_data_section(presentation_mode=False)" in source
    assert "_active_governed_context" in source
    assert "detailed._render_document_tab(run)" in source
    assert "detailed._render_financial_tab(run)" in source
    assert "detailed._render_action_tab(run)" in source

    portfolio_position = source.index(
        "render_portfolio_section(presentation_mode=False, case=run.updated_case)"
    )
    case_study_position = source.index(
        "render_official_case_study_section(presentation_mode=False)"
    )
    official_data_position = source.index(
        "render_official_data_section(presentation_mode=False)"
    )
    assert portfolio_position < case_study_position < official_data_position


def test_public_mode_keeps_reviewed_upload_workspace_opt_in():
    source = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")

    assert "def _private_workspace_enabled" in source
    assert 'return _env_flag("TRADEGUARD_ENABLE_PRIVATE_WORKSPACE")' in source
    assert 'modes = ["decision", "portfolio", "evidence"]' in source
    assert 'modes.insert(1, "analyst")' in source
    assert "Analyst Workspace는 로컬·Private 환경에서만 활성화됩니다" in source
