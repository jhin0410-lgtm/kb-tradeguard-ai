import assessment_app


def test_assessment_app_imports_without_starting_streamlit_runtime():
    assert callable(assessment_app.main)
    assert callable(assessment_app._capacity_metrics)
