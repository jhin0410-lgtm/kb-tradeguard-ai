"""Run a reviewed single-transaction assessment package from JSON.

Usage:
    python scripts/run_single_transaction_package.py package.json --output-dir outputs/case-001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intelligence import (  # noqa: E402
    export_single_transaction_package_run,
    load_single_transaction_package,
    run_single_transaction_package,
)
from src.intelligence.single_transaction_pipeline import (  # noqa: E402
    TransactionAssessmentPipelineError,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and run one reviewed KB TradeGuard single-transaction JSON package."
        )
    )
    parser.add_argument("package_path", help="UTF-8 JSON assessment package")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Artifact directory; defaults to outputs/<package-stem>",
    )
    args = parser.parse_args()

    package_path = Path(args.package_path)
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else ROOT / "outputs" / package_path.stem
    )
    try:
        package = load_single_transaction_package(package_path)
        run = run_single_transaction_package(package)
        exported = export_single_transaction_package_run(run, output_dir)
    except (ValueError, TransactionAssessmentPipelineError, OSError) as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "package_path": str(package_path),
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "package_path": str(package_path),
                "package_version": run.package_version,
                "input_package_hash": run.input_package_hash,
                "input_case_hash": run.input_case_hash,
                "output_case_hash": run.output_case_hash,
                "pipeline_id": run.assessment_result.pipeline_id,
                "pipeline_version": run.assessment_result.pipeline_version,
                "transaction_id": run.assessment_result.transaction_id,
                "disposition": run.assessment_result.brief.disposition,
                "stage_statuses": [
                    {
                        "sequence": item.sequence,
                        "stage_name": item.stage_name,
                        "status": item.status,
                    }
                    for item in run.assessment_result.stage_traces
                ],
                "missing_information": run.assessment_result.brief.missing_information,
                "artifact_manifest": exported.manifest_path,
                "artifact_paths": exported.artifact_paths,
                "authority_boundary": run.assessment_result.authority_boundary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
