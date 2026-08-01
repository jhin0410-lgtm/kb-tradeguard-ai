import pytest

from src.competition_usability_study import evaluate_usability_response


def test_usability_result_scores_risk_and_action_independently():
    result = evaluate_usability_response(
        participant_code="P01",
        elapsed_seconds=42.125,
        selected_risk_id="RISK-1",
        selected_action_id="ACTION-2",
        expected_risk_id="RISK-1",
        expected_action_id="ACTION-1",
    )

    assert result.participant_code == "P01"
    assert result.risk_correct is True
    assert result.action_correct is False
    assert result.task_success is False
    assert result.as_dict()["elapsed_seconds"] == 42.12


def test_usability_result_uses_anonymous_code_and_never_accepts_negative_time():
    result = evaluate_usability_response(
        participant_code="   ",
        elapsed_seconds=0,
        selected_risk_id="RISK-1",
        selected_action_id="ACTION-1",
        expected_risk_id="RISK-1",
        expected_action_id="ACTION-1",
    )

    assert result.participant_code == "anonymous"
    assert result.task_success is True
    assert "No name" in result.as_dict()["privacy_boundary"]

    with pytest.raises(ValueError, match="non-negative"):
        evaluate_usability_response(
            participant_code="P02",
            elapsed_seconds=-0.1,
            selected_risk_id="RISK-1",
            selected_action_id="ACTION-1",
            expected_risk_id="RISK-1",
            expected_action_id="ACTION-1",
        )
