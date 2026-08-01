import csv
from pathlib import Path

from scripts.summarize_usability_results import load_completed_rows, summarize_rows


def test_empty_template_is_reported_as_not_run() -> None:
    rows = load_completed_rows(Path("data/usability_test_results_template.csv"))
    summary = summarize_rows(rows)
    assert summary["status"] == "not_run"
    assert summary["participant_count"] == 0
    assert summary["success"] is False


def test_five_completed_participants_can_meet_declared_criteria(tmp_path) -> None:
    path = tmp_path / "results.csv"
    fieldnames = [
        "participant_id",
        "participant_profile",
        "test_date",
        "device",
        "total_completion_seconds",
        "decision_found_seconds",
        "risk_accuracy_0_to_3",
        "action_accuracy_0_to_3",
        "product_understanding_1_to_5",
        "data_boundary_understanding_1_to_5",
        "difficult_terms",
        "redundant_sections",
        "consultation_intent_1_to_5",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(5):
            writer.writerow(
                {
                    "participant_id": f"P{index + 1:02d}",
                    "participant_profile": "anonymous tester",
                    "test_date": "2026-08-01",
                    "device": "desktop",
                    "total_completion_seconds": 150 + index,
                    "decision_found_seconds": 20 + index,
                    "risk_accuracy_0_to_3": 3,
                    "action_accuracy_0_to_3": 3,
                    "product_understanding_1_to_5": 4,
                    "data_boundary_understanding_1_to_5": 4,
                    "difficult_terms": "",
                    "redundant_sections": "",
                    "consultation_intent_1_to_5": 4,
                    "notes": "",
                }
            )

    summary = summarize_rows(load_completed_rows(path))
    assert summary["status"] == "meets_success_criteria"
    assert summary["participant_count"] == 5
    assert summary["success"] is True
