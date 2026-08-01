"""Validate and summarize anonymous KB TradeGuard usability-test results."""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

_REQUIRED_NUMERIC = {
    "total_completion_seconds": float,
    "decision_found_seconds": float,
    "risk_accuracy_0_to_3": float,
    "action_accuracy_0_to_3": float,
    "product_understanding_1_to_5": float,
    "data_boundary_understanding_1_to_5": float,
    "consultation_intent_1_to_5": float,
}


def load_completed_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted({"participant_id", *_REQUIRED_NUMERIC} - set(reader.fieldnames or []))
        if missing:
            raise ValueError("Missing usability columns: " + ", ".join(missing))
        rows: list[dict[str, Any]] = []
        for line_number, raw in enumerate(reader, start=2):
            participant_id = str(raw.get("participant_id") or "").strip()
            if not participant_id:
                continue
            if not str(raw.get("total_completion_seconds") or "").strip():
                continue
            parsed = dict(raw)
            for field, converter in _REQUIRED_NUMERIC.items():
                value = str(raw.get(field) or "").strip()
                if not value:
                    raise ValueError(f"Row {line_number} is missing {field}")
                try:
                    parsed[field] = converter(value)
                except ValueError as exc:
                    raise ValueError(f"Row {line_number} has invalid {field}: {value}") from exc
            rows.append(parsed)
    return rows


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "status": "not_run",
            "participant_count": 0,
            "criteria": {},
            "success": False,
            "boundary": "No participant results were fabricated or inferred.",
        }

    metrics = {
        "median_total_completion_seconds": statistics.median(
            row["total_completion_seconds"] for row in rows
        ),
        "median_decision_found_seconds": statistics.median(
            row["decision_found_seconds"] for row in rows
        ),
        "mean_risk_accuracy_0_to_3": statistics.fmean(
            row["risk_accuracy_0_to_3"] for row in rows
        ),
        "mean_action_accuracy_0_to_3": statistics.fmean(
            row["action_accuracy_0_to_3"] for row in rows
        ),
        "mean_product_understanding_1_to_5": statistics.fmean(
            row["product_understanding_1_to_5"] for row in rows
        ),
        "mean_data_boundary_understanding_1_to_5": statistics.fmean(
            row["data_boundary_understanding_1_to_5"] for row in rows
        ),
        "mean_consultation_intent_1_to_5": statistics.fmean(
            row["consultation_intent_1_to_5"] for row in rows
        ),
    }
    criteria = {
        "participant_count_at_least_5": len(rows) >= 5,
        "median_total_completion_at_most_180": metrics["median_total_completion_seconds"] <= 180,
        "median_decision_found_at_most_30": metrics["median_decision_found_seconds"] <= 30,
        "mean_risk_accuracy_at_least_2_4": metrics["mean_risk_accuracy_0_to_3"] >= 2.4,
        "mean_action_accuracy_at_least_2_4": metrics["mean_action_accuracy_0_to_3"] >= 2.4,
        "mean_data_boundary_at_least_4": metrics["mean_data_boundary_understanding_1_to_5"] >= 4,
    }
    success = all(criteria.values())
    return {
        "status": "meets_success_criteria" if success else (
            "insufficient_participants" if len(rows) < 5 else "needs_improvement"
        ),
        "participant_count": len(rows),
        "metrics": metrics,
        "criteria": criteria,
        "success": success,
        "difficult_terms": sorted(
            {str(row.get("difficult_terms") or "").strip() for row in rows if str(row.get("difficult_terms") or "").strip()}
        ),
        "redundant_sections": sorted(
            {str(row.get("redundant_sections") or "").strip() for row in rows if str(row.get("redundant_sections") or "").strip()}
        ),
        "boundary": (
            "This is a small convenience-sample usability result, not generalized evidence of product effectiveness."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path, help="Anonymous completed CSV results")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = summarize_rows(load_completed_rows(args.results))
    text = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
