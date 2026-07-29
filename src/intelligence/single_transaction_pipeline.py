"""Governed orchestration for one transaction-level trade-finance assessment.

Version 1 deliberately accepts exactly one approved transaction per case.  This keeps
case-wide refresh operations from overwriting document or product records belonging to
another transaction.  Every stage either completes or is explicitly skipped, and the
final output remains a pre-screening brief rather than an approval or rejection.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..copilot_case import UnifiedCopilotCase
from .document_reconciliation import ReconciliationPolicy, apply_document_reconciliation
from .product_matching import TradeFinanceNeedProfile, apply_product_matching
from .trade_document_assessment import apply_trade_document_screening
from .transaction_capacity import (
    TransactionCapacityRequest,
    apply_transaction_capacity_assessment,
)
from .transaction_decision_brief import (
    TransactionDecisionBrief,
    TransactionDecisionBriefRequest,
    apply_transaction_decision_brief,
)

PipelineStageName = Literal[
    "trade_document_screening",
    "document_reconciliation",
    "transaction_capacity",
    "product_matching",
    "transaction_decision_brief",
]
PipelineStageStatus = Literal["completed", "skipped"]
_EXPECTED_STAGE_ORDER: list[PipelineStageName] = [
    "trade_document_screening",
    "document_reconciliation",
    "transaction_capacity",
    "product_matching",
    "transaction_decision_brief",
]


class SingleTransactionPipelineManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    pipeline_name: str
    pipeline_version: str
    effective_date: date
    single_transaction_case_required: bool
    stage_order: list[PipelineStageName]
    authority_boundary: str
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def stage_contract_is_fixed(self):
        if self.stage_order != _EXPECTED_STAGE_ORDER:
            raise ValueError("Single-transaction pipeline stage order is not governed")
        if not self.single_transaction_case_required:
            raise ValueError("Pipeline version 1 must remain single-transaction only")
        return self


class SingleTransactionAssessmentRequest(BaseModel):
    """Reviewed orchestration inputs for one approved transaction."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    pipeline_id: str
    brief_id: str
    transaction_id: str
    counterparty_id: str | None = None
    country_code: str | None = None
    reconciliation_policy: ReconciliationPolicy = Field(default_factory=ReconciliationPolicy)
    capacity_request: TransactionCapacityRequest | None = None
    product_profiles: list[TradeFinanceNeedProfile] = Field(default_factory=list)
    max_ranked_concerns: int = Field(default=5, ge=1, le=10)

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("country_code must contain two letters")
        return normalized

    @model_validator(mode="after")
    def nested_requests_match_transaction(self):
        if (
            self.capacity_request is not None
            and self.capacity_request.transaction_id != self.transaction_id
        ):
            raise ValueError("Capacity request transaction does not match pipeline transaction")
        mismatched_profiles = sorted(
            profile.profile_id
            for profile in self.product_profiles
            if profile.transaction_id != self.transaction_id
        )
        if mismatched_profiles:
            raise ValueError(
                "Product profiles do not match pipeline transaction: "
                + ", ".join(mismatched_profiles)
            )
        profile_ids = [profile.profile_id for profile in self.product_profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("Pipeline product profile IDs must be unique")
        return self


class PipelineStageTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    stage_name: PipelineStageName
    status: PipelineStageStatus
    case_before_hash: str
    case_after_hash: str
    generated_record_ids: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class SingleTransactionAssessmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline_id: str
    pipeline_version: str
    transaction_id: str
    case_before_hash: str
    case_after_hash: str
    stage_traces: list[PipelineStageTrace]
    brief: TransactionDecisionBrief
    final_record_counts: dict[str, int]
    authority_boundary: str
    limitations: list[str] = Field(default_factory=list)


class TransactionAssessmentPipelineError(RuntimeError):
    """Fail-closed stage error that never returns a partially updated case."""

    def __init__(self, stage_name: str, case_hash: str, cause: Exception):
        self.stage_name = stage_name
        self.case_hash = case_hash
        self.cause = cause
        super().__init__(
            f"Single-transaction pipeline failed at {stage_name} "
            f"for case snapshot {case_hash}: {cause}"
        )


def default_single_transaction_pipeline_manifest_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "reference"
        / "single_transaction_pipeline_v1.json"
    )


def load_single_transaction_pipeline_manifest(
    path: str | Path | None = None,
) -> SingleTransactionPipelineManifest:
    manifest_path = (
        Path(path)
        if path is not None
        else default_single_transaction_pipeline_manifest_path()
    )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Unable to load single-transaction pipeline manifest: {manifest_path}"
        ) from exc
    return SingleTransactionPipelineManifest.model_validate(payload)


def _validate_single_transaction_case(
    case: UnifiedCopilotCase,
    request: SingleTransactionAssessmentRequest,
) -> None:
    transactions = case.approved_transactions
    if len(transactions) != 1:
        raise ValueError(
            "Pipeline version 1 requires exactly one approved transaction per case"
        )
    case_transaction_id = str(transactions[0].get("transaction_id") or "")
    if case_transaction_id != request.transaction_id:
        raise ValueError(
            "Pipeline transaction does not match the case approved transaction"
        )

    foreign_payments = sorted(
        item.payment_structure_id
        for item in case.trade_finance.payment_structures
        if item.transaction_id != request.transaction_id
    )
    if foreign_payments:
        raise ValueError(
            "Single-transaction case contains payment structures for another transaction: "
            + ", ".join(foreign_payments)
        )

    supported_document_types = {
        "contract",
        "purchase_order",
        "commercial_invoice",
        "letter_of_credit",
    }
    unscoped_documents = []
    foreign_documents = []
    for document in case.trade_finance.trade_documents:
        if document.document_type not in supported_document_types:
            continue
        linked = set(document.linked_transaction_ids)
        if not linked:
            unscoped_documents.append(document.document_id)
        elif linked != {request.transaction_id}:
            foreign_documents.append(document.document_id)
    if unscoped_documents:
        raise ValueError(
            "Supported trade documents must be linked to the pipeline transaction: "
            + ", ".join(sorted(unscoped_documents))
        )
    if foreign_documents:
        raise ValueError(
            "Single-transaction case contains documents linked to another transaction: "
            + ", ".join(sorted(foreign_documents))
        )


def _trace(
    sequence: int,
    stage_name: PipelineStageName,
    status: PipelineStageStatus,
    before_hash: str,
    after_hash: str,
    generated_record_ids: list[str] | None = None,
    **details: Any,
) -> PipelineStageTrace:
    return PipelineStageTrace(
        sequence=sequence,
        stage_name=stage_name,
        status=status,
        case_before_hash=before_hash,
        case_after_hash=after_hash,
        generated_record_ids=generated_record_ids or [],
        details=details,
    )


def _clear_transaction_capacity_records(
    case: UnifiedCopilotCase,
    transaction_id: str,
) -> tuple[UnifiedCopilotCase, list[str]]:
    """Remove capacity outputs that are no longer supported by the current run."""

    calculation_ids = {
        calculation_id
        for calculation_id, calculation in case.calculations.items()
        if calculation.calculation_name
        == "Transaction financial capacity assessment"
        and str(calculation.input_assumptions.get("transaction_id"))
        == transaction_id
    }
    removed_signal_ids: list[str] = []
    retained_signals = []
    for signal in case.trade_finance.risk_signals:
        transaction_scoped = transaction_id in signal.affected_transaction_ids
        capacity_derived = (
            signal.source.source_id.startswith("TRANSACTION-CAPACITY-")
            or bool(calculation_ids.intersection(signal.calculation_ids))
        )
        if transaction_scoped and capacity_derived:
            removed_signal_ids.append(signal.signal_id)
        else:
            retained_signals.append(signal)

    if not calculation_ids and not removed_signal_ids:
        return case, []

    calculations = {
        calculation_id: calculation
        for calculation_id, calculation in case.calculations.items()
        if calculation_id not in calculation_ids
    }
    domain = case.trade_finance.model_copy(update={"risk_signals": retained_signals})
    updated = case.model_copy(
        update={
            "calculations": calculations,
            "trade_finance": domain,
        }
    )
    removed_ids = sorted(calculation_ids) + sorted(removed_signal_ids)
    return updated, removed_ids


def run_single_transaction_assessment(
    case: UnifiedCopilotCase,
    request: SingleTransactionAssessmentRequest,
    *,
    manifest_path: str | Path | None = None,
) -> tuple[UnifiedCopilotCase, SingleTransactionAssessmentResult]:
    """Run the governed vertical slice and return a new case plus final brief."""

    manifest = load_single_transaction_pipeline_manifest(manifest_path)
    _validate_single_transaction_case(case, request)
    original_hash = case.case_hash
    working = case
    traces: list[PipelineStageTrace] = []
    product_candidate_ids: list[str] = []
    consultation_requirement_ids: list[str] = []

    supported_screening_documents = [
        item
        for item in working.trade_finance.trade_documents
        if item.document_type in {"contract", "purchase_order", "letter_of_credit"}
        and request.transaction_id in item.linked_transaction_ids
    ]
    before = working.case_hash
    if supported_screening_documents:
        try:
            working, outcome = apply_trade_document_screening(working)
        except Exception as exc:  # fail closed with stage identity
            raise TransactionAssessmentPipelineError(
                "trade_document_screening", before, exc
            ) from exc
        generated = outcome.clause_finding_ids + outcome.risk_signal_ids
        traces.append(
            _trace(
                1,
                "trade_document_screening",
                "completed",
                before,
                working.case_hash,
                generated,
                evaluated_document_ids=outcome.evaluated_document_ids,
                clause_finding_count=len(outcome.clause_finding_ids),
                risk_signal_count=len(outcome.risk_signal_ids),
            )
        )
    else:
        traces.append(
            _trace(
                1,
                "trade_document_screening",
                "skipped",
                before,
                before,
                reason="No supported reviewed contract, purchase order, or letter of credit is linked.",
            )
        )

    reconciliation_documents = [
        item
        for item in working.trade_finance.trade_documents
        if item.document_type in {"contract", "commercial_invoice", "letter_of_credit"}
        and request.transaction_id in item.linked_transaction_ids
    ]
    before = working.case_hash
    if len(reconciliation_documents) >= 2:
        try:
            working, outcome = apply_document_reconciliation(
                working,
                request.reconciliation_policy,
            )
        except Exception as exc:
            raise TransactionAssessmentPipelineError(
                "document_reconciliation", before, exc
            ) from exc
        generated = outcome.finding_ids + outcome.risk_signal_ids
        traces.append(
            _trace(
                2,
                "document_reconciliation",
                "completed",
                before,
                working.case_hash,
                generated,
                compared_document_ids=outcome.compared_document_ids,
                comparison_count=len(outcome.comparison_ids),
                skipped_comparison_count=len(outcome.skipped_comparison_ids),
            )
        )
    else:
        traces.append(
            _trace(
                2,
                "document_reconciliation",
                "skipped",
                before,
                before,
                reason="Fewer than two supported documents are available for cross-document comparison.",
            )
        )

    before = working.case_hash
    if request.capacity_request is not None:
        try:
            working, outcome = apply_transaction_capacity_assessment(
                working,
                request.capacity_request,
            )
        except Exception as exc:
            raise TransactionAssessmentPipelineError(
                "transaction_capacity", before, exc
            ) from exc
        generated = [outcome.calculation_id] + outcome.risk_signal_ids
        traces.append(
            _trace(
                3,
                "transaction_capacity",
                "completed",
                before,
                working.case_hash,
                generated,
                calculation_id=outcome.calculation_id,
                risk_signal_count=len(outcome.risk_signal_ids),
                missing_inputs=outcome.missing_inputs,
            )
        )
    else:
        working, removed_capacity_record_ids = _clear_transaction_capacity_records(
            working,
            request.transaction_id,
        )
        traces.append(
            _trace(
                3,
                "transaction_capacity",
                "skipped",
                before,
                working.case_hash,
                reason="No reviewed transaction-capacity request was supplied.",
                removed_record_ids=removed_capacity_record_ids,
            )
        )

    before = working.case_hash
    if request.product_profiles:
        try:
            working, outcome = apply_product_matching(
                working,
                request.product_profiles,
            )
        except Exception as exc:
            raise TransactionAssessmentPipelineError(
                "product_matching", before, exc
            ) from exc
        generated_candidates = set(outcome.product_candidate_ids)
        product_candidate_ids = [
            item.product_candidate_id
            for item in working.trade_finance.product_candidates
            if item.product_candidate_id in generated_candidates
            and item.candidate_status
            in {"consultation_candidate", "insufficient_information"}
        ]
        consultation_requirement_ids = list(outcome.consultation_requirement_ids)
        generated = outcome.product_candidate_ids + outcome.consultation_requirement_ids
        traces.append(
            _trace(
                4,
                "product_matching",
                "completed",
                before,
                working.case_hash,
                generated,
                profile_ids=outcome.profile_ids,
                status_counts=outcome.status_counts,
            )
        )
    else:
        traces.append(
            _trace(
                4,
                "product_matching",
                "skipped",
                before,
                before,
                reason="No explicit trade-finance need profiles were supplied.",
            )
        )

    before = working.case_hash
    brief_request = TransactionDecisionBriefRequest(
        brief_id=request.brief_id,
        transaction_id=request.transaction_id,
        counterparty_id=request.counterparty_id,
        country_code=request.country_code,
        product_candidate_ids=product_candidate_ids,
        consultation_requirement_ids=consultation_requirement_ids,
        max_ranked_concerns=request.max_ranked_concerns,
    )
    try:
        working, brief, outcome = apply_transaction_decision_brief(
            working,
            brief_request,
        )
    except Exception as exc:
        raise TransactionAssessmentPipelineError(
            "transaction_decision_brief", before, exc
        ) from exc
    traces.append(
        _trace(
            5,
            "transaction_decision_brief",
            "completed",
            before,
            working.case_hash,
            outcome.action_ids,
            brief_id=outcome.brief_id,
            disposition=outcome.disposition,
            missing_information=outcome.missing_information,
            ranked_concern_count=len(brief.ranked_concerns),
        )
    )

    result = SingleTransactionAssessmentResult(
        pipeline_id=request.pipeline_id,
        pipeline_version=manifest.pipeline_version,
        transaction_id=request.transaction_id,
        case_before_hash=original_hash,
        case_after_hash=working.case_hash,
        stage_traces=traces,
        brief=brief,
        final_record_counts=working.trade_finance.record_counts(),
        authority_boundary=manifest.authority_boundary,
        limitations=manifest.limitations,
    )
    return working, result
