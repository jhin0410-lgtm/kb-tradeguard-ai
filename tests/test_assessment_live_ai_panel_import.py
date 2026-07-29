from src import assessment_live_ai_panel


def test_live_ai_panel_imports_without_api_key_or_network_call():
    assert callable(assessment_live_ai_panel.render_grounded_live_ai_panel)
    assert callable(assessment_live_ai_panel._clear_stale_live_ai_state)
