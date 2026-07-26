import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.copilot_case import CaseIdentity, UnifiedCopilotCase
from src.intelligence.single_transaction_package import (
    SingleTransactionAssessmentPackage,
    export_single_transaction_package_run,
    load_single_transaction_package,
    run_single_transaction_package,
)
from src.intelligence.single_transaction_pipeline import SingleTransactionAssessmentRequest
from src.trade_finance_domain import (
    ComplianceScreeningResult,
    CounterpartyProfile,
    CountryRiskFact,
    SourceReference,
    TradeFinanceDomainState,
)


def _source(source_id, kind="official_api", tier="tier_1"):
    return SourceReference(
        source_id=source_id,
        source_name=f"Synthetic source {source_id}",
        source_tier=tier,
        source_kind=kind,
        source_locator=f"fixture://{source_id}",
        as_of_date=date(2026, 7, 26),
        effective_date_verified=True,
    )


def _case():
    counterparty = CounterpartyProfile(
        counterparty_id="BUYER-VN-001",
        legal_name="Vietnam Buyer Co., Ltd.",
        country_code="VN",
        registration_number="VN-REG-001",
        relationship_status="new",
        due_diligence_status="professional_credit_investigation_completed",
        prior_payment_history="positive",
        source=_source("SRC-BUYER", "user_document", "user_provided"),
        record_status="verified",
    )
    country_fact = CountryRiskFact(
        fact_id="COUNTRY-VN-GDP",
        country_code="VN",
        dimension="macroeconomic",
        metric_name="GDP growth",
        value="7.09",
        unit="% annual growth",
        observation_date=date(2024, 12, 31),
        risk_direction="lower_is_worse",
        interpretation="Macroeconomic context only.",
        source=_source("SRC-WB"),
        record_status="verified",
    )
    screening = ComplianceScreeningResult(
        screening_id="SCREEN-BUYER-VN-001",
        subject_type="counterparty",
        subject_id=counterparty.counterparty_id,
        subject_name=counterparty.legal_name,
        screening_type="sanctions",
        result="clear",
        method="exact",
        source=_source("SRC-SANCTIONS", "official_publication", "tier_1"),
        record_status="verified",
    )
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-PACKAGE-001",
            company_name="Example Exporter Co., Ltd.",
            analysis_as_of_date=date(2026, 7, 26),
        ),
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "expected_date": "2026-10-31",
            }
        ],
        trade_finance=TradeFinanceDomainState(
            counterparties=[counterparty],
            country_risk_facts=[country_fact],
            compliance_screenings=[screening],
        ),
    )


def _request(transaction_id="EXP-001"):
    return SingleTransactionAssessmentRequest(
        pipeline_id="PIPELINE-PACKAGE-001",
        brief_id="BRIEF-PACKAGE-001",
        transaction_id=transaction_id,
        counterparty_id="BUYER-VN-001",
        country_code="VN",
    )


def _package():
    case = _case()
    return SingleTransactionAssessmentPackage(
        case=case,
        request=_request(),
        expected_input_case_hash=case.case_hash,
        notes=["Reviewed synthetic package fixture."],
    )


def test_package_hash_and_expected_case_hash_are_validated():
    package = _package()

    assert package.package_version == "single-transaction-package/1.0"
    assert len(package.package_hash) == 64
    assert package.expected_input_case_hash == package.case.case_hash

    with pytest.raises(ValidationError, match="does not match"):
        SingleTransactionAssessmentPackage(
            case=package.case,
            request=package.request,
            expected_input_case_hash="0" * 64,
        )


def test_package_rejects_transaction_mismatch_before_pipeline_execution():
    case = _case()

    with pytest.raises(ValidationError, match="exactly the pipeline request transaction"):
        SingleTransactionAssessmentPackage(
            case=case,
            request=_request("EXP-OTHER"),
        )


def test_json_package_round_trip_loads_with_stable_hash(tmp_path):
    package = _package()
    package_path = tmp_path / "assessment_package.json"
    package_path.write_text(
        json.dumps(package.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    loaded = load_single_transaction_package(package_path)

    assert loaded.package_hash == package.package_hash
    assert loaded.case.case_hash == package.case.case_hash
    assert loaded.request == package.request


def test_invalid_json_package_is_reported_with_file_context(tmp_path):
    package_path = tmp_path / "broken.json"
    package_path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError, match="Unable to load assessment package"):
        load_single_transaction_package(package_path)


def test_package_runner_executes_pipeline_and_preserves_input_case():
    package = _package()
    before = package.case.case_hash

    run = run_single_transaction_package(package)

    assert package.case.case_hash == before
    assert run.input_case_hash == before
    assert run.output_case_hash == run.updated_case.case_hash
    assert [item.status for item in run.assessment_result.stage_traces[:4]] == [
        "skipped",
        "skipped",
        "skipped",
        "skipped",
    ]
    assert run.assessment_result.stage_traces[-1].status == "completed"
    assert run.assessment_result.brief.disposition == "additional_information_required"
    assert run.audit_summary["case_hash"] == run.output_case_hash


def test_export_writes_hashed_audit_artifacts(tmp_path):
    run = run_single_transaction_package(_package())
    export = export_single_transaction_package_run(run, tmp_path / "output")

    expected = {
        "updated_case.json",
        "updated_case_canonical.json",
        "assessment_result.json",
        "decision_brief.json",
        "stage_trace.json",
        "audit_summary.json",
    }
    assert set(export.artifact_paths) == expected
    assert Path(export.manifest_path).exists()

    for filename, path_text in export.artifact_paths.items():
        path = Path(path_text)
        assert path.exists()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == export.artifact_sha256[filename]

    manifest = json.loads(Path(export.manifest_path).read_text(encoding="utf-8"))
    assert manifest["input_package_hash"] == run.input_package_hash
    assert manifest["input_case_hash"] == run.input_case_hash
    assert manifest["output_case_hash"] == run.output_case_hash
    assert {item["filename"] for item in manifest["artifacts"]} == expected
