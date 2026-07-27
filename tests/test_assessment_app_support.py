import io
import json
import zipfile

import pytest

from src.assessment_app_support import (
    assessment_summary,
    build_audit_bundle_bytes,
    concern_rows,
    package_json_bytes,
    parse_package_json_bytes,
    stage_rows,
)
from src.demo_scenarios import load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


def test_uploaded_package_round_trip_and_summary_are_stable():
    package = load_demo_scenario("oa_high_risk")
    uploaded = parse_package_json_bytes(
        package_json_bytes(package), source_name="oa_high_risk.json"
    )
    run = run_single_transaction_package(uploaded)
    summary = assessment_summary(run)

    assert uploaded.package_hash == package.package_hash
    assert summary["disposition"] == "conditions_required_before_commitment"
    assert summary["critical_high_concerns"] >= 1
    assert summary["completed_stage_count"] == 5
    assert len(stage_rows(run)) == 5
    assert concern_rows(run)


def test_invalid_uploaded_json_fails_with_source_context():
    with pytest.raises(ValueError, match="broken.json"):
        parse_package_json_bytes(b"{broken", source_name="broken.json")


def test_audit_bundle_contains_manifest_report_and_input_package():
    package = load_demo_scenario("missing_information")
    run = run_single_transaction_package(package)
    bundle = build_audit_bundle_bytes(run, package=package)

    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        names = set(archive.namelist())
        assert {
            "input_package.json",
            "updated_case.json",
            "updated_case_canonical.json",
            "assessment_result.json",
            "decision_brief.json",
            "decision_brief.md",
            "stage_trace.json",
            "audit_summary.json",
            "artifact_manifest.json",
        } <= names
        manifest = json.loads(archive.read("artifact_manifest.json"))
        assert manifest["input_package_hash"] == run.input_package_hash
        assert manifest["output_case_hash"] == run.output_case_hash
        assert "거래 승인·거절" in archive.read("decision_brief.md").decode("utf-8")
