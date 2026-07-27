"""Run every governed showcase scenario without starting Streamlit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.assessment_app_support import assessment_summary  # noqa: E402
from src.demo_scenarios import list_demo_scenarios, load_demo_scenario  # noqa: E402
from src.intelligence.single_transaction_package import (  # noqa: E402
    run_single_transaction_package,
)


def main() -> int:
    results = []
    for metadata in list_demo_scenarios():
        package = load_demo_scenario(metadata.scenario_id)
        run = run_single_transaction_package(package)
        summary = assessment_summary(run)
        results.append(
            {
                "scenario_id": metadata.scenario_id,
                "title": metadata.title,
                "expected_disposition": metadata.expected_disposition,
                "actual_disposition": summary["disposition"],
                "stage_statuses": [
                    {
                        "stage_name": item.stage_name,
                        "status": item.status,
                    }
                    for item in run.assessment_result.stage_traces
                ],
                "critical_high_concerns": summary["critical_high_concerns"],
                "missing_information_count": summary["missing_information_count"],
                "product_candidate_count": summary["product_candidate_count"],
                "output_case_hash": run.output_case_hash,
            }
        )
    status = "ok" if all(
        item["expected_disposition"] == item["actual_disposition"] for item in results
    ) else "mismatch"
    print(json.dumps({"status": status, "scenarios": results}, ensure_ascii=False, indent=2))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
