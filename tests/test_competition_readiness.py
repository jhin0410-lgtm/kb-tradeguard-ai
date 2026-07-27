from src.competition_readiness import build_competition_readiness_report


def test_competition_readiness_report_is_complete_and_deterministic():
    report = build_competition_readiness_report()

    assert report["report_version"] == "competition-readiness/1.2"
    assert report["status"] == "ready"
    assert report["network_calls"] == "none"
    assert report["missing_files"] == []
    assert report["public_repo_safety_status"] == "safe"
    assert report["public_repo_safety_finding_count"] == 0
    assert report["demo_scenario_count"] == 4
    assert report["gold_case_count"] == 30
    assert report["mutation_case_count"] == 150
    assert report["governed_rule_count"] == 22
    assert report["covered_rule_count"] == 22
    assert report["uncovered_rule_ids"] == []
    assert report["unexpected_rule_ids"] == []
    assert report["failures"] == []

    for scenario in report["scenario_results"]:
        assert scenario["matches_expected"] is True
        assert scenario["stage_count"] == 5
        assert scenario["presentation_snapshot_version"] == (
            "competition-presentation/1.0"
        )
        assert scenario["presentation_snapshot_v2_version"] == (
            "competition-presentation/2.0"
        )
        assert scenario["presentation_v2_top_risk_count"] <= 3
        assert len(scenario["input_package_hash"]) == 64
        assert len(scenario["output_case_hash"]) == 64
