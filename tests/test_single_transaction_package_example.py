from pathlib import Path

from src.intelligence import (
    load_single_transaction_package,
    run_single_transaction_package,
)


def test_minimal_package_example_is_valid_and_reports_missing_inputs():
    root = Path(__file__).resolve().parents[1]
    package = load_single_transaction_package(
        root / "examples" / "single_transaction_assessment_package_minimal.json"
    )
    run = run_single_transaction_package(package)

    assert package.package_version == "single-transaction-package/1.0"
    assert run.assessment_result.brief.disposition == "additional_information_required"
    assert [item.status for item in run.assessment_result.stage_traces[:4]] == [
        "skipped",
        "skipped",
        "skipped",
        "skipped",
    ]
    assert run.assessment_result.stage_traces[-1].status == "completed"
    assert any(
        item.startswith("payment_structure")
        for item in run.assessment_result.brief.missing_information
    )
