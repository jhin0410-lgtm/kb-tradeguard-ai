from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_streamlit_entrypoint_renders_portfolio_and_pinned_official_cases():
    source = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")

    assert "render_workflow_map()" in source
    assert "render_portfolio_section(presentation_mode=presentation_mode)" in source
    assert "render_official_case_study_section(presentation_mode=presentation_mode)" in source
    assert source.index("render_portfolio_section(presentation_mode=presentation_mode)") < source.index(
        "render_official_case_study_section(presentation_mode=presentation_mode)"
    )
    assert source.index("render_official_case_study_section(presentation_mode=presentation_mode)") < source.index(
        "render_official_data_section(presentation_mode=presentation_mode)"
    )
