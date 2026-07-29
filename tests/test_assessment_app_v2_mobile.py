import assessment_app_v2_mobile


def test_mobile_v2_entrypoint_is_compact_and_phone_focused():
    css = assessment_app_v2_mobile.MOBILE_POLISH_CSS

    assert callable(assessment_app_v2_mobile.main)
    assert ".v21-hero" in css
    assert ".v21-pill-grid" in css
    assert ".v21-flow" in css
    assert "grid-template-columns: 1fr 1fr" in css
    assert "initial_sidebar_state=\"collapsed\"" in open(
        assessment_app_v2_mobile.__file__, encoding="utf-8"
    ).read()


def test_mobile_v2_keeps_main_page_run_control():
    source = open(assessment_app_v2_mobile.__file__, encoding="utf-8").read()

    assert "이 거래 5단계 사전진단 시작" in source
    assert "run_single_transaction_package" in source
    assert "st.rerun()" in source
    assert "assessment_app_v2_mobile.py" not in source
