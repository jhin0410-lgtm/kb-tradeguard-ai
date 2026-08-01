import pytest

from pathlib import Path

from src.assessment_app_v2 import build_risk_first_summary
from src.competition_topic6 import prepare_topic6_demo_package
from src.competition_usability_study import (
    build_neutral_study_options,
    evaluate_usability_response,
)
from src.demo_scenarios import load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


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


def test_study_options_hide_governed_rank_and_require_explicit_selection():
    package = prepare_topic6_demo_package(load_demo_scenario("oa_high_risk"))
    run = run_single_transaction_package(package)
    summary = build_risk_first_summary(run)
    risk_options, action_options = build_neutral_study_options(summary)

    assert risk_options
    assert action_options
    assert all(not label[:1].isdigit() for label in risk_options)
    assert all(not label[:1].isdigit() for label in action_options)

    source = Path("src/competition_usability_study.py").read_text(encoding="utf-8")
    assert source.count("index=None") == 2
    assert "disabled=not selections_complete" in source
