"""JSON package boundary for the governed single-transaction assessment pipeline.

The package format makes the vertical slice usable without constructing Pydantic objects
inside application code. It validates one reviewed case and one pipeline request,
runs the deterministic orchestration, and exports auditable JSON and Markdown artifacts
with hashes. It does not fetch missing data, approve a transaction, or convert unreviewed
documents into approved evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..copilot_case import UnifiedCopilotCase
from .decision_brief_report import render_single_transaction_assessment_markdown
from .single_transaction_pipeline import (
    SingleTransactionAssessmentRequest,
    SingleTransactionAssessmentResult,
    run_single_transaction_assessment,
)

PackageVersion = Literal["single-transaction-package/1.0"]


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _pretty_json_text(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _positive_transaction_amount(transaction: dict[str, Any]) -> Decimal:
    raw = transaction.get("amount_fc")
    try:
        amount = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Package transaction amount_fc must be numeric") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Package transaction amount_fc must be finite and greater than zero")
    return amount


class SingleTransactionAssessmentPackage(BaseModel):
    """Portable reviewed input package for one deterministic assessment run."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    package_version: PackageVersion = "single-transaction-package/1.0"
    case: UnifiedCopilotCase
    request: SingleTransactionAssessmentRequest
    expected_input_case_hash: str | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("expected_input_case_hash")
    @classmethod
    def expected_hash_is_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lower()
        if not _is_sha256(normalized):
            raise ValueError("expected_input_case_hash must be a lowercase SHA-256 digest")
        return normalized

    @model_validator(mode="after")
    def package_links_are_consistent(self):
        transaction_ids = [
            str(item.get("transaction_id") or "")
            for item in self.case.approved_transactions
        ]
        if transaction_ids != [self.request.transaction_id]:
            raise ValueError(
                "Package case must contain exactly the pipeline request transaction"
            )
        _positive_transaction_amount(self.case.approved_transactions[0])
        if (
            self.expected_input_case_hash is not None
            and self.expected_input_case_hash != self.case.case_hash
        ):
            raise ValueError(
                "expected_input_case_hash does not match the supplied case snapshot"
            )
        return self

    def canonical_payload(self) -> dict[str, Any]:
        """Timestamp-stable package payload used for hashing and audit manifests."""

        return {
            "package_version": self.package_version,
            "case": self.case.canonical_snapshot(),
            "request": self.request.model_dump(mode="json"),
            "expected_input_case_hash": self.expected_input_case_hash,
            "notes": list(self.notes),
        }

    @property
    def package_hash(self) -> str:
        return _sha256_bytes(_canonical_json_bytes(self.canonical_payload()))


class SingleTransactionPackageRun(BaseModel):
    """Complete in-memory result before artifact export."""

    model_config = ConfigDict(extra="forbid")

    package_version: PackageVersion
    input_package_hash: str
    input_case_hash: str
    output_case_hash: str
    updated_case: UnifiedCopilotCase
    assessment_result: SingleTransactionAssessmentResult
    audit_summary: dict[str, Any]

    @model_validator(mode="after")
    def hashes_match_embedded_records(self):
        if self.output_case_hash != self.updated_case.case_hash:
            raise ValueError("output_case_hash does not match updated_case")
        if self.assessment_result.case_before_hash != self.input_case_hash:
            raise ValueError("assessment_result input hash does not match package input case")
        if self.assessment_result.case_after_hash != self.output_case_hash:
            raise ValueError("assessment_result output hash does not match updated case")
        return self


class SingleTransactionPackageExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_directory: str
    artifact_paths: dict[str, str]
    artifact_sha256: dict[str, str]
    manifest_path: str


def load_single_transaction_package(
    path: str | Path,
) -> SingleTransactionAssessmentPackage:
    """Load and validate one UTF-8 JSON package from disk."""

    package_path = Path(path)
    try:
        raw = package_path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load assessment package: {package_path}") from exc
    try:
        return SingleTransactionAssessmentPackage.model_validate(payload)
    except Exception as exc:
        raise ValueError(f"Invalid assessment package: {package_path}: {exc}") from exc


def run_single_transaction_package(
    package: SingleTransactionAssessmentPackage,
    *,
    manifest_path: str | Path | None = None,
) -> SingleTransactionPackageRun:
    """Run the governed pipeline using only the supplied reviewed package records."""

    updated_case, result = run_single_transaction_assessment(
        package.case,
        package.request,
        manifest_path=manifest_path,
    )
    return SingleTransactionPackageRun(
        package_version=package.package_version,
        input_package_hash=package.package_hash,
        input_case_hash=package.case.case_hash,
        output_case_hash=updated_case.case_hash,
        updated_case=updated_case,
        assessment_result=result,
        audit_summary=updated_case.audit_summary(),
    )


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def export_single_transaction_package_run(
    run: SingleTransactionPackageRun,
    output_directory: str | Path,
) -> SingleTransactionPackageExport:
    """Write canonical audit artifacts and a content-hash manifest atomically."""

    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_payloads: dict[str, Any] = {
        "updated_case.json": run.updated_case.model_dump(mode="json"),
        "updated_case_canonical.json": run.updated_case.canonical_snapshot(),
        "assessment_result.json": run.assessment_result.model_dump(mode="json"),
        "decision_brief.json": run.assessment_result.brief.model_dump(mode="json"),
        "stage_trace.json": [
            item.model_dump(mode="json") for item in run.assessment_result.stage_traces
        ],
        "audit_summary.json": run.audit_summary,
    }
    text_payloads = {
        "decision_brief.md": render_single_transaction_assessment_markdown(
            run.updated_case,
            run.assessment_result,
        )
    }
    artifact_paths: dict[str, str] = {}
    artifact_hashes: dict[str, str] = {}

    for filename, payload in json_payloads.items():
        text = _pretty_json_text(payload)
        path = output_dir / filename
        _atomic_write_text(path, text)
        artifact_paths[filename] = str(path)
        artifact_hashes[filename] = _sha256_bytes(text.encode("utf-8"))

    for filename, text in text_payloads.items():
        path = output_dir / filename
        _atomic_write_text(path, text)
        artifact_paths[filename] = str(path)
        artifact_hashes[filename] = _sha256_bytes(text.encode("utf-8"))

    manifest_payload = {
        "package_version": run.package_version,
        "input_package_hash": run.input_package_hash,
        "input_case_hash": run.input_case_hash,
        "output_case_hash": run.output_case_hash,
        "pipeline_id": run.assessment_result.pipeline_id,
        "pipeline_version": run.assessment_result.pipeline_version,
        "transaction_id": run.assessment_result.transaction_id,
        "artifacts": [
            {
                "filename": filename,
                "sha256": artifact_hashes[filename],
            }
            for filename in sorted(artifact_hashes)
        ],
        "authority_boundary": run.assessment_result.authority_boundary,
        "limitations": run.assessment_result.limitations,
    }
    manifest_path = output_dir / "artifact_manifest.json"
    _atomic_write_text(manifest_path, _pretty_json_text(manifest_payload))
    return SingleTransactionPackageExport(
        output_directory=str(output_dir),
        artifact_paths=artifact_paths,
        artifact_sha256=artifact_hashes,
        manifest_path=str(manifest_path),
    )
