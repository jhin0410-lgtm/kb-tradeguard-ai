"""Deterministic reconciliation across reviewed trade documents.

The module compares only human-reviewed structured fields from documents linked to the
same transaction.  Differences become review flags, never automatic findings of fraud,
legal invalidity, documentary non-compliance, or bank refusal.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..copilot_case import UnifiedCopilotCase
from ..trade_finance_domain import (
    ContractClauseFinding,
    SourceReference,
    TradeDocumentProfile,
    TradeRiskSignal,
)

ComparisonOperator = Literal[
    "exact", "normalized_text", "decimal_tolerance", "date_not_after"
]
ComparisonStatus = Literal["match", "within_tolerance", "mismatch", "skipped"]
DocumentType = Literal["contract", "commercial_invoice", "letter_of_credit"]
ToleranceReference = Literal["left", "right", "larger"]


class ReconciliationRule(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rule_id: str
    left_document_type: DocumentType
    right_document_type: DocumentType
    left_field: str
    right_field: str
    comparison: ComparisonOperator
    alias_group: Literal["parties", "places"] | None = None
    field_label: str
    severity: Literal["critical", "high", "medium", "low", "informational"]
    failure_path: str
    suggested_resolution: str
    specialist_review: list[
        Literal["legal", "bank", "insurer", "logistics", "customs", "none"]
    ] = Field(default_factory=list)

    @model_validator(mode="after")
    def alias_group_matches_operator(self):
        if self.alias_group and self.comparison != "normalized_text":
            raise ValueError("alias_group is valid only for normalized_text comparisons")
        return self


class ReconciliationRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    registry_name: str
    registry_version: str
    effective_date: date
    authority_boundary: str
    rules: list[ReconciliationRule]

    @model_validator(mode="after")
    def rule_ids_are_unique(self):
        identifiers = [rule.rule_id for rule in self.rules]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Reconciliation rule IDs must be unique")
        return self


class ReconciliationPolicy(BaseModel):
    """Explicit case-level exceptions; no tolerance or alias is inferred silently."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    amount_tolerance_percent_by_rule: dict[str, Decimal] = Field(default_factory=dict)
    tolerance_basis_by_rule: dict[str, str] = Field(default_factory=dict)
    tolerance_reference_by_rule: dict[str, ToleranceReference] = Field(default_factory=dict)
    party_aliases: dict[str, str] = Field(default_factory=dict)
    place_aliases: dict[str, str] = Field(default_factory=dict)
    excluded_document_ids: list[str] = Field(default_factory=list)
    exclusion_reasons: dict[str, str] = Field(default_factory=dict)

    @field_validator("amount_tolerance_percent_by_rule")
    @classmethod
    def tolerances_are_bounded(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        for rule_id, percent in value.items():
            parsed = Decimal(str(percent))
            if parsed < 0 or parsed > 100:
                raise ValueError(f"Amount tolerance for {rule_id} must be between 0 and 100")
        return value

    @model_validator(mode="after")
    def exceptions_are_fully_sourced(self):
        nonzero_rules = {
            rule_id
            for rule_id, percent in self.amount_tolerance_percent_by_rule.items()
            if Decimal(str(percent)) > 0
        }
        missing_basis = sorted(nonzero_rules - set(self.tolerance_basis_by_rule))
        missing_reference = sorted(nonzero_rules - set(self.tolerance_reference_by_rule))
        if missing_basis:
            raise ValueError(
                "Non-zero amount tolerances require a reviewed basis: "
                + ", ".join(missing_basis)
            )
        if missing_reference:
            raise ValueError(
                "Non-zero amount tolerances require an explicit reference side: "
                + ", ".join(missing_reference)
            )
        excluded = set(self.excluded_document_ids)
        if len(excluded) != len(self.excluded_document_ids):
            raise ValueError("Excluded document IDs must be unique")
        missing_reasons = sorted(excluded - set(self.exclusion_reasons))
        if missing_reasons:
            raise ValueError(
                "Excluded documents require an amendment or supersession reason: "
                + ", ".join(missing_reasons)
            )
        return self


class DocumentComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    comparison_id: str
    rule_id: str
    status: ComparisonStatus
    field_label: str
    left_document_id: str
    right_document_id: str
    left_document_type: str
    right_document_type: str
    transaction_ids: list[str] = Field(default_factory=list)
    left_value: Any | None = None
    right_value: Any | None = None
    normalized_left_value: str | None = None
    normalized_right_value: str | None = None
    absolute_difference: Decimal | None = None
    allowed_difference: Decimal | None = None
    tolerance_percent: Decimal | None = None
    tolerance_basis: str | None = None
    rationale: str


class DocumentReconciliationResult(BaseModel):
    registry_version: str
    comparisons: list[DocumentComparisonResult] = Field(default_factory=list)
    findings: list[ContractClauseFinding] = Field(default_factory=list)
    risk_signals: list[TradeRiskSignal] = Field(default_factory=list)


class DocumentReconciliationOutcome(BaseModel):
    case_before_hash: str
    case_after_hash: str
    compared_document_ids: list[str] = Field(default_factory=list)
    comparison_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    risk_signal_ids: list[str] = Field(default_factory=list)
    skipped_comparison_ids: list[str] = Field(default_factory=list)


def default_reconciliation_registry_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "reference"
        / "trade_document_reconciliation_rules_v1.json"
    )


def load_reconciliation_registry(
    path: str | Path | None = None,
) -> ReconciliationRegistry:
    registry_path = Path(path) if path is not None else default_reconciliation_registry_path()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load reconciliation registry: {registry_path}") from exc
    return ReconciliationRegistry.model_validate(payload)


def _registry_source(registry: ReconciliationRegistry, path: Path) -> SourceReference:
    return SourceReference(
        source_id=f"DOCUMENT-RECONCILIATION-{registry.registry_version}",
        source_name=registry.registry_name,
        source_tier="derived",
        source_kind="project_rule",
        source_locator=path.as_posix(),
        as_of_date=registry.effective_date,
        content_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
        effective_date_verified=True,
    )


def _get_field(document: TradeDocumentProfile, field_path: str) -> Any:
    if field_path.startswith("reviewed_fields."):
        return document.reviewed_fields.get(field_path.split(".", 1)[1])
    if not hasattr(document, field_path):
        raise ValueError(f"Unknown trade-document field path: {field_path}")
    return getattr(document, field_path)


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return not value
    return False


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).split())


def _canonical_alias(value: Any, aliases: dict[str, str]) -> str:
    normalized = _normalize_text(value)
    normalized_aliases = {
        _normalize_text(key): _normalize_text(canonical) for key, canonical in aliases.items()
    }
    return normalized_aliases.get(normalized, normalized)


def _as_decimal(value: Any, field_label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_label} must contain numeric reviewed values") from exc


def _as_date(value: Any, field_label: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field_label} must contain ISO date reviewed values") from exc


def _comparison_id(rule: ReconciliationRule, left: str, right: str) -> str:
    return f"RECON-{rule.rule_id}-{left}-{right}"


def _compare_values(
    rule: ReconciliationRule,
    left_value: Any,
    right_value: Any,
    policy: ReconciliationPolicy,
) -> tuple[ComparisonStatus, dict[str, Any], str]:
    details: dict[str, Any] = {}
    if _missing(left_value) or _missing(right_value):
        return (
            "skipped",
            details,
            "At least one reviewed comparison field is missing; no mismatch is inferred.",
        )

    if rule.comparison == "exact":
        matched = left_value == right_value
        return (
            "match" if matched else "mismatch",
            details,
            "Reviewed values are identical." if matched else "Reviewed values differ.",
        )

    if rule.comparison == "normalized_text":
        aliases = (
            policy.party_aliases if rule.alias_group == "parties" else policy.place_aliases
        )
        left_normalized = _canonical_alias(left_value, aliases)
        right_normalized = _canonical_alias(right_value, aliases)
        details.update(
            normalized_left_value=left_normalized,
            normalized_right_value=right_normalized,
        )
        matched = left_normalized == right_normalized
        return (
            "match" if matched else "mismatch",
            details,
            (
                "Reviewed text values match after deterministic normalization and explicit aliases."
                if matched
                else "Reviewed text values differ after deterministic normalization and explicit aliases."
            ),
        )

    if rule.comparison == "decimal_tolerance":
        left_decimal = _as_decimal(left_value, rule.field_label)
        right_decimal = _as_decimal(right_value, rule.field_label)
        difference = abs(left_decimal - right_decimal)
        tolerance_percent = Decimal(
            str(policy.amount_tolerance_percent_by_rule.get(rule.rule_id, Decimal("0")))
        )
        reference = policy.tolerance_reference_by_rule.get(rule.rule_id, "left")
        if reference == "left":
            reference_amount = abs(left_decimal)
        elif reference == "right":
            reference_amount = abs(right_decimal)
        else:
            reference_amount = max(abs(left_decimal), abs(right_decimal))
        allowed = reference_amount * tolerance_percent / Decimal("100")
        details.update(
            absolute_difference=difference,
            allowed_difference=allowed,
            tolerance_percent=tolerance_percent,
            tolerance_basis=policy.tolerance_basis_by_rule.get(rule.rule_id),
        )
        if difference == 0:
            return "match", details, "Reviewed monetary values are identical."
        if difference <= allowed:
            return (
                "within_tolerance",
                details,
                "Difference falls within the explicitly reviewed tolerance for this rule.",
            )
        return (
            "mismatch",
            details,
            "Difference exceeds the explicitly reviewed tolerance; no implicit tolerance is applied.",
        )

    if rule.comparison == "date_not_after":
        left_date = _as_date(left_value, rule.field_label)
        right_date = _as_date(right_value, rule.field_label)
        matched = left_date <= right_date
        return (
            "match" if matched else "mismatch",
            details,
            (
                "The left document date does not exceed the right document deadline."
                if matched
                else "The left document date exceeds the right document deadline."
            ),
        )

    raise ValueError(f"Unsupported reconciliation operator: {rule.comparison}")


def reconcile_trade_documents(
    documents: list[TradeDocumentProfile],
    policy: ReconciliationPolicy | None = None,
    *,
    registry_path: str | Path | None = None,
) -> DocumentReconciliationResult:
    """Compare active reviewed documents linked to the same transaction."""

    policy = policy or ReconciliationPolicy()
    resolved_path = (
        Path(registry_path) if registry_path is not None else default_reconciliation_registry_path()
    )
    registry = load_reconciliation_registry(resolved_path)
    source = _registry_source(registry, resolved_path)
    excluded = set(policy.excluded_document_ids)
    active_documents = [item for item in documents if item.document_id not in excluded]
    active_by_type: dict[str, list[TradeDocumentProfile]] = {}
    for document in sorted(active_documents, key=lambda item: item.document_id):
        active_by_type.setdefault(document.document_type, []).append(document)

    comparisons: list[DocumentComparisonResult] = []
    findings: list[ContractClauseFinding] = []
    signals: list[TradeRiskSignal] = []

    for rule in registry.rules:
        left_documents = active_by_type.get(rule.left_document_type, [])
        right_documents = active_by_type.get(rule.right_document_type, [])
        for left in left_documents:
            for right in right_documents:
                transaction_ids = sorted(
                    set(left.linked_transaction_ids) & set(right.linked_transaction_ids)
                )
                if not transaction_ids:
                    continue
                left_value = _get_field(left, rule.left_field)
                right_value = _get_field(right, rule.right_field)
                status, details, rationale = _compare_values(
                    rule, left_value, right_value, policy
                )
                comparison_id = _comparison_id(rule, left.document_id, right.document_id)
                comparison = DocumentComparisonResult(
                    comparison_id=comparison_id,
                    rule_id=rule.rule_id,
                    status=status,
                    field_label=rule.field_label,
                    left_document_id=left.document_id,
                    right_document_id=right.document_id,
                    left_document_type=left.document_type,
                    right_document_type=right.document_type,
                    transaction_ids=transaction_ids,
                    left_value=left_value,
                    right_value=right_value,
                    rationale=rationale,
                    **details,
                )
                comparisons.append(comparison)
                if status != "mismatch":
                    continue

                evidence_ids = list(dict.fromkeys([left.evidence_id, right.evidence_id]))
                finding_id = f"CLAUSE-{comparison_id}"
                tolerance_note = (
                    f"Tolerance basis: {comparison.tolerance_basis}; allowed difference: "
                    f"{comparison.allowed_difference}."
                    if comparison.tolerance_percent and comparison.tolerance_percent > 0
                    else "No non-zero amount tolerance was applied unless explicitly supplied in the case policy."
                )
                finding = ContractClauseFinding(
                    clause_finding_id=finding_id,
                    document_id=left.document_id,
                    evidence_ids=evidence_ids,
                    clause_locator=f"Cross-document reconciliation / {rule.field_label}",
                    clause_excerpt=(
                        f"{left.document_id}={left_value}; {right.document_id}={right_value}"
                    ),
                    issue_type="document_discrepancy_risk",
                    severity=rule.severity,
                    failure_path=rule.failure_path,
                    suggested_clarification_or_revision=rule.suggested_resolution,
                    specialist_review=rule.specialist_review,
                    source=source,
                    record_status=(
                        "verified"
                        if left.record_status == "verified" and right.record_status == "verified"
                        else "partial"
                    ),
                    limitations=[
                        registry.authority_boundary,
                        "Only human-reviewed structured fields from documents linked to the same transaction were compared.",
                        tolerance_note,
                    ],
                )
                findings.append(finding)
                signals.append(
                    TradeRiskSignal(
                        signal_id=f"RISK-DOC-{finding_id}",
                        category=(
                            "payment_instrument"
                            if "letter_of_credit"
                            in {left.document_type, right.document_type}
                            else "contract_document"
                        ),
                        severity=rule.severity,
                        title=f"Cross-document mismatch: {rule.field_label}",
                        factual_trigger=finding.clause_excerpt,
                        authority_type="screening_flag",
                        affected_transaction_ids=transaction_ids,
                        affected_document_ids=[left.document_id, right.document_id],
                        evidence_ids=evidence_ids,
                        clause_finding_ids=[finding_id],
                        unresolved_facts=[
                            "Confirm whether a valid amendment, permitted tolerance, party alias, partial shipment, or superseded document explains the difference."
                        ],
                        source=source,
                        record_status=finding.record_status,
                        limitations=list(finding.limitations),
                    )
                )

    return DocumentReconciliationResult(
        registry_version=registry.registry_version,
        comparisons=comparisons,
        findings=findings,
        risk_signals=signals,
    )


def apply_document_reconciliation(
    case: UnifiedCopilotCase,
    policy: ReconciliationPolicy | None = None,
    *,
    registry_path: str | Path | None = None,
) -> tuple[UnifiedCopilotCase, DocumentReconciliationOutcome]:
    """Attach current cross-document mismatches and remove stale prior results."""

    policy = policy or ReconciliationPolicy()
    resolved_path = (
        Path(registry_path) if registry_path is not None else default_reconciliation_registry_path()
    )
    registry = load_reconciliation_registry(resolved_path)
    source_id = _registry_source(registry, resolved_path).source_id
    excluded = set(policy.excluded_document_ids)
    supported_documents = [
        item
        for item in case.trade_finance.trade_documents
        if item.document_type in {"contract", "commercial_invoice", "letter_of_credit"}
        and item.document_id not in excluded
    ]
    approved_evidence_ids = {
        item.evidence_id for item in case.evidence if item.status == "approved"
    }
    for document in supported_documents:
        if document.evidence_id not in approved_evidence_ids:
            raise ValueError(
                f"Trade document {document.document_id} must reference approved case evidence"
            )

    result = reconcile_trade_documents(
        supported_documents,
        policy,
        registry_path=resolved_path,
    )
    retained_findings = [
        item
        for item in case.trade_finance.clause_findings
        if item.source.source_id != source_id
    ]
    retained_signals = [
        item for item in case.trade_finance.risk_signals if item.source.source_id != source_id
    ]
    updated_domain = case.trade_finance.model_copy(
        update={
            "clause_findings": retained_findings + result.findings,
            "risk_signals": retained_signals + result.risk_signals,
        }
    )
    updated_case = case.model_copy(update={"trade_finance": updated_domain})
    compared_document_ids = sorted(
        {
            document_id
            for comparison in result.comparisons
            for document_id in (
                comparison.left_document_id,
                comparison.right_document_id,
            )
        }
    )
    outcome = DocumentReconciliationOutcome(
        case_before_hash=case.case_hash,
        case_after_hash=updated_case.case_hash,
        compared_document_ids=compared_document_ids,
        comparison_ids=[item.comparison_id for item in result.comparisons],
        finding_ids=[item.clause_finding_id for item in result.findings],
        risk_signal_ids=[item.signal_id for item in result.risk_signals],
        skipped_comparison_ids=[
            item.comparison_id for item in result.comparisons if item.status == "skipped"
        ],
    )
    return updated_case, outcome
