from src.assessment_app_presentation import (
    APP_CSS,
    build_presentation_snapshot,
    disposition_presentation,
    scenario_narrative,
)
from src.demo_scenarios import list_demo_scenarios, load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


def test_every_demo_scenario_has_a_complete_presentation_narrative():
    for metadata in list_demo_scenarios():
        narrative = scenario_narrative(metadata.scenario_id)

        assert narrative is not None
        assert narrative.scenario_id == metadata.scenario_id
        assert narrative.business_problem
        assert narrative.decision_question
        assert narrative.judge_watch
        assert 3 <= len(narrative.walkthrough) <= 5


def test_every_demo_disposition_has_a_safe_presentation_state():
    prohibited = {"승인 완료", "적격 확정", "안전 인증", "제재 해소"}

    for metadata in list_demo_scenarios():
        presentation = disposition_presentation(metadata.expected_disposition)
        combined = " ".join(
            [
                presentation.eyebrow,
                presentation.headline,
                presentation.explanation,
                presentation.next_focus,
            ]
        )

        assert presentation.tone in {"critical", "warning", "info", "clear"}
        assert not any(term in combined for term in prohibited)


def test_presentation_snapshot_is_hash_grounded_and_compact():
    package = load_demo_scenario("oa_high_risk")
    run = run_single_transaction_package(package)

    snapshot = build_presentation_snapshot(run, scenario_id="oa_high_risk")

    assert snapshot["snapshot_version"] == "competition-presentation/1.0"
    assert snapshot["input_package_hash"] == run.input_package_hash
    assert snapshot["input_case_hash"] == run.input_case_hash
    assert snapshot["output_case_hash"] == run.output_case_hash
    assert snapshot["disposition"] == "conditions_required_before_commitment"
    assert len(snapshot["stage_statuses"]) == 5
    assert snapshot["scenario_business_problem"]
    assert snapshot["authority_boundary"] == run.assessment_result.authority_boundary


def test_app_css_is_local_and_contains_responsive_competition_components():
    assert "<style>" in APP_CSS
    assert ".tg-hero" in APP_CSS
    assert ".tg-verdict" in APP_CSS
    assert ".tg-stepper" in APP_CSS
    assert "@media" in APP_CSS
    assert "http://" not in APP_CSS
    assert "https://" not in APP_CSS
