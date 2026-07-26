"""Deterministic contract and documentary-credit pre-screening rules.

The evaluator consumes only reviewed structured fields and produces grounded
``ContractClauseFinding`` records.  It does not determine legal enforceability,
documentary compliance, bank acceptance, or insurance eligibility.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..trade_finance_domain import (
    ContractClauseFinding,
    PaymentStructure,
    SourceReference,
    TradeDocumentProfile,
    TradeRiskSignal,
)

RuleOperator = Literal[
    "missing",
    "true",
    "equals",
    "list_not_contains",
    "non_empty_list",
    "date_before_field",
    "buyer_acceptance_without_period",
]
DocumentKind = Literal["contract", "letter_of_credit"]


class TradeDocumentRule(BaseModel):
    """Validated rule metadata loaded from the governed JSON registry."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rule_id: str
    document_kind: DocumentKind
    operator: RuleOperator
    field: str
    comparison_field: str | None = None
    expected_value: Any | None = None
    severity: Literal["critical", "high", "medium", "low", "informational"]
    issue_type: Literal[
        "missing_term",
        "ambiguous_term",
        "buyer_controlled_condition",
        "timing_conflict",
        "document_discrepancy_risk",
        "incoterms_mismatch",
        "payment_risk",
        "broad_liability",
        "unilateral_right",
        "governing_law_or_dispute",
        "sanctions_or_export_control",
        "other",
    ]
    clause_locator: str
    failure_path: str
    suggested_revision: str
    specialist_review: list[
        Literal["legal", "bank", "insurer", "logistics", "customs", "none"]
    ] = Field(default_factory=list)
    official_source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def operator_arguments_are_complete(self):
        if self.operator == "date_before_field" and not self.comparison_field:
            raise ValueError("date_before_field rules require comparison_field")
        if self.operator in {"equals", "list_not_contains"} and self.expected_value is None:
            raise ValueError(f"{self.operator} rules require expected_value")
        return self


class TradeDocumentRuleRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    registry_name: str
    registry_version: str
    effective_date: date
    authority_boundary: str
    official_sources: list[dict[str, str]]
    rules: list[TradeDocumentRule]

    @model_validator(mode="after")
    def identifiers_and_source_links_are_valid(self):
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Trade-document rule IDs must be unique")

        source_ids = [item.get("source_id", "") for item in self.official_sources]
        if not all(source_ids) or len(source_ids) != len(set(source_ids)):
            raise ValueError("Official source IDs must be non-empty and unique")
        known = set(source_ids)
        unknown = sorted(
            {
                source_id
                for rule in self.rules
                for source_id in rule.official_source_ids
                if source_id not in known
            }
        )
        if unknown:
            raise ValueError("Rules cite unknown official source IDs: " + ", ".join(unknown))
        return self


class ReviewedDocumentTerms(BaseModel):
    """Narrow typed view over fields that have already been reviewed by a human."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_kind: DocumentKind
    document_id: str
    evidence_id: str
    fields: dict[str, Any]


def default_trade_document_rule_registry_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "reference"
        / "trade_document_rules_v1.json"
    )


def load_trade_document_rule_registry(
    path: str | Path | None = None,
) -> TradeDocumentRuleRegistry:
    registry_path = Path(path) if path is not None else default_trade_document_rule_registry_path()
    try:
        raw = registry_path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load trade-document rule registry: {registry_path}") from exc
    return TradeDocumentRuleRegistry.model_validate(payload)


def _payment_structure_for_document(
    document: TradeDocumentProfile,
    payment_structure: PaymentStructure | None,
) -> PaymentStructure | None:
    if payment_structure is None:
        return None
    if document.payment_structure_id and (
        payment_structure.payment_structure_id != document.payment_structure_id
    ):
        raise ValueError("Payment structure does not match the reviewed document")
    linked = set(document.linked_transaction_ids)
    if linked and payment_structure.transaction_id not in linked:
        raise ValueError("Payment structure transaction is not linked to the reviewed document")
    return payment_structure


def reviewed_terms_from_document(
    document: TradeDocumentProfile,
    payment_structure: PaymentStructure | None = None,
) -> ReviewedDocumentTerms:
    """Build a typed rule-input view from reviewed domain records."""

    payment = _payment_structure_for_document(document, payment_structure)
    reviewed = dict(document.reviewed_fields)
    if document.document_type in {"contract", "purchase_order"}:
        kind: DocumentKind = "contract"
        fields = {
            "incoterms_rule": document.incoterms_rule,
            "incoterms_year": document.incoterms_year,
            "named_place": document.named_place,
            "payment_trigger": (
                payment.payment_trigger if payment is not None else reviewed.get("payment_trigger")
            ),
            "acceptance_period_days": reviewed.get("acceptance_period_days"),
            "governing_law": reviewed.get("governing_law"),
            "dispute_resolution": reviewed.get("dispute_resolution"),
            "buyer_unilateral_setoff_right": reviewed.get(
                "buyer_unilateral_setoff_right"
            ),
            "buyer_unilateral_amendment_right": reviewed.get(
                "buyer_unilateral_amendment_right"
            ),
        }
    elif document.document_type == "letter_of_credit":
        kind = "letter_of_credit"
        fields = {
            "issuing_bank": (
                payment.issuing_bank if payment is not None else reviewed.get("issuing_bank")
            ),
            "expiry_date": document.expiry_date,
            "latest_shipment_date": reviewed.get("latest_shipment_date"),
            "presentation_period_days": reviewed.get("presentation_period_days"),
            "governing_rules": (
                payment.governing_rules if payment is not None else reviewed.get("governing_rules", [])
            ),
            "buyer_controlled_document_requirements": reviewed.get(
                "buyer_controlled_document_requirements", []
            ),
            "expiry_place": reviewed.get("expiry_place"),
        }
    else:
        raise ValueError(
            "Trade-document rules currently support contracts, purchase orders, and letters of credit"
        )

    return ReviewedDocumentTerms(
        document_kind=kind,
        document_id=document.document_id,
        evidence_id=document.evidence_id,
        fields=fields,
    )


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return not value
    return False


def _normalized_text(value: Any) -> str:
    return " ".join(str(value).casefold().split())


def _rule_triggered(rule: TradeDocumentRule, fields: dict[str, Any]) -> bool:
    value = fields.get(rule.field)
    if rule.operator == "missing":
        return _missing(value)
    if rule.operator == "true":
        return value is True
    if rule.operator == "equals":
        return value == rule.expected_value
    if rule.operator == "non_empty_list":
        return isinstance(value, (list, tuple, set)) and bool(value)
    if rule.operator == "list_not_contains":
        if not isinstance(value, (list, tuple, set)):
            return True
        expected = _normalized_text(rule.expected_value)
        return not any(expected in _normalized_text(item) for item in value)
    if rule.operator == "date_before_field":
        comparison = fields.get(rule.comparison_field or "")
        return value is not None and comparison is not None and value < comparison
    if rule.operator == "buyer_acceptance_without_period":
        trigger = _normalized_text(value) if value is not None else ""
        depends_on_acceptance = "accept" in trigger and (
            "buyer" in trigger or "applicant" in trigger or "customer" in trigger
        )
        return depends_on_acceptance and _missing(fields.get("acceptance_period_days"))
    raise ValueError(f"Unsupported trade-document rule operator: {rule.operator}")


def _display_value(rule: TradeDocumentRule, fields: dict[str, Any]) -> str:
    value = fields.get(rule.field)
    if rule.operator == "missing":
        return f"[missing from reviewed field: {rule.field}]"
    if rule.operator == "date_before_field":
        comparison = fields.get(rule.comparison_field or "")
        return f"{rule.field}={value}; {rule.comparison_field}={comparison}"
    if isinstance(value, (list, tuple, set)):
        return "; ".join(str(item) for item in value)
    return str(value)


def _registry_source(
    registry: TradeDocumentRuleRegistry,
    registry_path: Path,
) -> SourceReference:
    content_hash = hashlib.sha256(registry_path.read_bytes()).hexdigest()
    return SourceReference(
        source_id=f"TRADE-DOCUMENT-RULES-{registry.registry_version}",
        source_name=registry.registry_name,
        source_tier="derived",
        source_kind="project_rule",
        source_locator=str(registry_path.as_posix()),
        as_of_date=registry.effective_date,
        retrieved_at=None,
        content_hash=content_hash,
        effective_date_verified=True,
    )


def evaluate_trade_document(
    document: TradeDocumentProfile,
    payment_structure: PaymentStructure | None = None,
    *,
    registry_path: str | Path | None = None,
) -> list[ContractClauseFinding]:
    """Evaluate one reviewed document using only governed deterministic rules."""

    resolved_path = (
        Path(registry_path)
        if registry_path is not None
        else default_trade_document_rule_registry_path()
    )
    registry = load_trade_document_rule_registry(resolved_path)
    terms = reviewed_terms_from_document(document, payment_structure)
    source = _registry_source(registry, resolved_path)
    findings: list[ContractClauseFinding] = []

    for rule in registry.rules:
        if rule.document_kind != terms.document_kind:
            continue
        if not _rule_triggered(rule, terms.fields):
            continue
        findings.append(
            ContractClauseFinding(
                clause_finding_id=f"CLAUSE-{rule.rule_id}-{document.document_id}",
                document_id=document.document_id,
                evidence_ids=[document.evidence_id],
                clause_locator=rule.clause_locator,
                clause_excerpt=_display_value(rule, terms.fields),
                issue_type=rule.issue_type,
                severity=rule.severity,
                failure_path=rule.failure_path,
                suggested_clarification_or_revision=rule.suggested_revision,
                specialist_review=rule.specialist_review,
                source=source,
                record_status=(
                    "verified" if document.record_status == "verified" else "partial"
                ),
                limitations=[
                    registry.authority_boundary,
                    "The finding is based on reviewed structured fields, not autonomous legal interpretation of the full document.",
                    (
                        "Official reference IDs: " + ", ".join(rule.official_source_ids)
                        if rule.official_source_ids
                        else "No external rulebook conclusion is asserted; this is a project-authored commercial screening rule."
                    ),
                ],
            )
        )
    return findings


def build_document_risk_signals(
    document: TradeDocumentProfile,
    findings: list[ContractClauseFinding],
    *,
    registry_path: str | Path | None = None,
) -> list[TradeRiskSignal]:
    """Convert clause findings to individually grounded screening signals."""

    resolved_path = (
        Path(registry_path)
        if registry_path is not None
        else default_trade_document_rule_registry_path()
    )
    registry = load_trade_document_rule_registry(resolved_path)
    source = _registry_source(registry, resolved_path)
    signals = []
    for finding in findings:
        signals.append(
            TradeRiskSignal(
                signal_id=f"RISK-DOC-{finding.clause_finding_id}",
                category=(
                    "payment_instrument"
                    if document.document_type == "letter_of_credit"
                    else "contract_document"
                ),
                severity=finding.severity,
                title=finding.clause_locator,
                factual_trigger=finding.clause_excerpt,
                authority_type="screening_flag",
                affected_transaction_ids=list(document.linked_transaction_ids),
                affected_document_ids=[document.document_id],
                evidence_ids=[document.evidence_id],
                clause_finding_ids=[finding.clause_finding_id],
                unresolved_facts=[
                    "Full-document review and applicable specialist confirmation remain required."
                ],
                source=source,
                record_status=finding.record_status,
                limitations=list(finding.limitations),
            )
        )
    return signals
