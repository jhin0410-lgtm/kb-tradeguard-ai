from pathlib import Path

import competition_app
import streamlit_app


def test_competition_app_is_single_screen_synthetic_demo():
    source = Path(competition_app.__file__).read_text(encoding="utf-8")

    assert callable(competition_app.main)
    assert competition_app.DEFAULT_SCENARIO_ID == "oa_high_risk"
    assert "load_demo_scenario" in source
    assert "run_single_transaction_package" in source
    assert "file_uploader" not in source
    assert "render_grounded_live_ai_panel" not in source
    assert "tg-bottom-nav" in competition_app.COMPETITION_CSS
    assert "판단 근거 열기" in source
    assert "TRADEGUARD_PUBLIC_DEMO_URL" in source


def test_competition_app_has_presentation_and_mobile_contracts():
    source = Path(competition_app.__file__).read_text(encoding="utf-8")

    assert "presentation" in source
    assert "#summary" in source
    assert "#evidence" in source
    assert "#actions" in source
    assert "#audit" in source
    assert "@media(max-width:760px)" in competition_app.COMPETITION_CSS
    assert callable(streamlit_app.main)


def test_streamlit_entrypoint_binds_the_public_https_demo_url():
    assert streamlit_app.PUBLIC_DEMO_URL == (
        "https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/"
    )
    assert streamlit_app.PUBLIC_DEMO_URL.startswith("https://")
