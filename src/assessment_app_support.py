"""Pure helpers used by the assessment Streamlit entrypoint.

Keeping package parsing, summary derivation, and ZIP generation outside Streamlit makes the
presentation layer independently testable and preserves the deterministic assessment boundary.
"""

from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .intelligence.single_transaction_package import (
    SingleTransactionAssessmentPackage,
    SingleTransactionPackageRun,
    export_single_transaction_package_run,
)

_DISPOSITION_LABELS = {
    "specialist_clearance_required": "전문가 확인 선행 필요",
    "conditions_required_before_commitment": "거래 확정 전 조건 보완 필요",
    "additional_information_required": "추가 정보 필요",
    "review_required": "검토 필요",
    "no_material_screening_flags": "현재 검토자료상 중대한 경보 없음",
}


def disposition_label(disposition: str) -> str:
    return _DISPOSITION_LABELS.get(disposition, disposition)


def parse_package_json_bytes(
    payload: bytes,
    *,
    source_name: str = "uploaded assessment package",
) -> SingleTransactionAssessmentPackage:
    """Decode and validate one uploaded UTF-8 package without writing it to disk."""

    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to decode {source_name} as UTF-8 JSON") from exc
    try:
        return SingleTransactionAssessmentPackage.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"Invalid {source_name}: {exc}") from exc


def package_json_bytes(package: SingleTransactionAssessmentPackage) -> bytes:
    """Return a reviewable pretty-printed package snapshot."""

    return (
        json.dumps(
            package.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def assessment_summary(run: SingleTransactionPackageRun) -> dict[str, Any]:
    """Build stable top-level metrics from one completed deterministic run."""

    concerns = run.assessment_result.brief.ranked_concerns
    severity_counts = {
        severity: sum(item.severity == severity for item in concerns)
        for severity in ("critical", "high", "medium", "low", "informational")
    }
    return {
        "disposition": run.assessment_result.brief.disposition,
        "disposition_label": disposition_label(run.assessment_result.brief.disposition),
        "critical_high_concerns": severity_counts["critical"] + severity_counts["high"],
        "missing_information_count": len(run.assessment_result.brief.missing_information),
        "product_candidate_count": len(run.assessment_result.brief.product_candidate_ids),
        "completed_stage_count": sum(
            item.status == "completed" for item in run.assessment_result.stage_traces
        ),
        "stage_count": len(run.assessment_result.stage_traces),
        "output_case_hash": run.output_case_hash,
        "severity_counts": severity_counts,
    }


def stage_rows(run: SingleTransactionPackageRun) -> list[dict[str, Any]]:
    return [
        {
            "순서": item.sequence,
            "단계": item.stage_name,
            "상태": item.status,
            "생성 레코드 수": len(item.generated_record_ids),
            "입력 Case hash": item.case_before_hash,
            "출력 Case hash": item.case_after_hash,
        }
        for item in run.assessment_result.stage_traces
    ]


def concern_rows(run: SingleTransactionPackageRun) -> list[dict[str, Any]]:
    return [
        {
            "순위": item.rank,
            "심각도": item.severity,
            "범주": item.category,
            "확인사항": item.title,
            "확인된 근거": item.factual_basis,
            "미해결 사실": "; ".join(item.unresolved_facts),
            "근거 ID": ", ".join(item.source_ids),
        }
        for item in run.assessment_result.brief.ranked_concerns
    ]


def build_audit_bundle_bytes(
    run: SingleTransactionPackageRun,
    *,
    package: SingleTransactionAssessmentPackage | None = None,
) -> bytes:
    """Create a ZIP containing the existing hashed export and optional input package."""

    with tempfile.TemporaryDirectory(prefix="kb-tradeguard-assessment-") as directory:
        export = export_single_transaction_package_run(run, Path(directory) / "artifacts")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for filename, path_text in sorted(export.artifact_paths.items()):
                archive.write(path_text, arcname=filename)
            archive.write(export.manifest_path, arcname="artifact_manifest.json")
            if package is not None:
                archive.writestr("input_package.json", package_json_bytes(package))
        return buffer.getvalue()
