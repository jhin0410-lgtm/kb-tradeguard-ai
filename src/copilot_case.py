"""Unified, evidence-grounded case state for the trade-finance copilot.

The case object is an orchestration boundary, not a new calculation engine. It keeps
reviewed source data, deterministic outputs, scenario definitions, citations, and
known gaps in one immutable-by-convention structure so that multi-step analysis can
be executed and audited without silently inventing inputs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .advisor_models import CalculationResult
from .copilot_planning import CaseCapabilities
from .trade_finance_domain import TradeFinanceDomainState

CaseDataStatus = Literal["available", "partial", "missing", "not_applicable"]
ScenarioStatus = Literal["proposed", "approved", "executed", "rejected"]
EvidenceStatus = Literal["approved", "review_required", "invalid"]


class CaseIdentity(BaseModel):
    case_id: str
    company_name: str | None = None
    business_registration_number: str | None = None
    analysis_as_of_date: date | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CaseEvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: str
    source_name: str
    status: EvidenceStatus = "review_required"
    source_locator: str | None = None
    excerpt: str | None = None
    content_hash: str | None = None
    linked_transaction_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CaseDataAsset(BaseModel):
    asset_name: str
    status: CaseDataStatus
    source: str
    as_of_date: date | None = None
    retrieved_at: datetime | None = None
    source_hash: str | None = None
    payload: dict[str, Any] | list[dict[str, Any]] | None = None
    limitations: list[str] = Field(default_factory=list)


class CaseScenario(BaseModel):
    scenario_id: str
    name: str
    rationale: str
    status: ScenarioStatus = "proposed"
    parameter_changes: dict[str, Any] = Field(default_factory=dict)
    parameter_sources: dict[str, str] = Field(default_factory=dict)
    required_inputs: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def executed_scenario_requires_results(self):
        if self.status == "executed" and not self.calculation_ids:
            raise ValueError("Executed scenarios must reference deterministic calculation IDs.")
        return self


class CaseFinding(BaseModel):
    finding_id: str
    title: str
    summary: str
    priority: Literal["critical", "high", "medium", "low", "informational"]
    category: str
    calculation_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def grounded_finding_requires_reference(self):
        if self.priority != "informational" and not (
            self.calculation_ids or self.evidence_ids
        ):
            raise ValueError(
                "Non-informational findings must reference calculation or evidence IDs."
            )
        return self


class MissingInput(BaseModel):
    input_name: str
    reason: str
    blocks: list[str] = Field(default_factory=list)
    requested_from: str | None = None
    can_use_disclosed_assumption: bool = False


class UnifiedCopilotCase(BaseModel):
    """Single audit-ready state passed between planner, tools, and UI."""

    identity: CaseIdentity
    evidence: list[CaseEvidenceItem] = Field(default_factory=list)
    approved_transactions: list[dict[str, Any]] = Field(default_factory=list)
    foreign_cash_positions: list[dict[str, Any]] = Field(default_factory=list)
    monthly_cost_assumptions: dict[str, Any] = Field(default_factory=dict)
    official_fx_reference: CaseDataAsset | None = None
    financial_context: CaseDataAsset | None = None
    policy_context: CaseDataAsset | None = None
    trade_finance: TradeFinanceDomainState = Field(default_factory=TradeFinanceDomainState)
    calculations: dict[str, CalculationResult] = Field(default_factory=dict)
    scenarios: list[CaseScenario] = Field(default_factory=list)
    findings: list[CaseFinding] = Field(default_factory=list)
    missing_inputs: list[MissingInput] = Field(default_factory=list)
    case_version: str = "copilot-case/1.1"

    @model_validator(mode="after")
    def calculation_keys_must_match_ids(self):
        mismatches = [
            key
            for key, result in self.calculations.items()
            if key != result.calculation_id
        ]
        if mismatches:
            raise ValueError(
                "Calculation dictionary keys must equal their calculation IDs: "
                + ", ".join(mismatches)
            )
        return self

    @property
    def capabilities(self) -> CaseCapabilities:
        return CaseCapabilities(
            approved_transactions=bool(self.approved_transactions),
            document_evidence=any(item.status == "approved" for item in self.evidence),
            foreign_cash_positions=bool(self.foreign_cash_positions),
            monthly_cost_assumptions=bool(self.monthly_cost_assumptions),
            official_fx_reference=(
                self.official_fx_reference is not None
                and self.official_fx_reference.status in {"available", "partial"}
            ),
            financial_context=(
                self.financial_context is not None
                and self.financial_context.status in {"available", "partial"}
            ),
            policy_corpus=(
                self.policy_context is not None
                and self.policy_context.status in {"available", "partial"}
            ),
        )

    @property
    def unresolved_evidence_ids(self) -> list[str]:
        return [item.evidence_id for item in self.evidence if item.status != "approved"]

    @property
    def executable_case(self) -> bool:
        return bool(self.approved_transactions)

    def add_calculation(self, result: CalculationResult) -> "UnifiedCopilotCase":
        """Return a copied case with one deterministic result attached."""

        calculations = dict(self.calculations)
        calculations[result.calculation_id] = result
        return self.model_copy(update={"calculations": calculations})

    def canonical_snapshot(self) -> dict[str, Any]:
        """Return a timestamp-stable snapshot suitable for hashing and audit export."""

        payload = self.model_dump(mode="json")
        payload["identity"].pop("created_at", None)
        for result in payload["calculations"].values():
            result.pop("calculation_timestamp", None)
        return payload

    @property
    def case_hash(self) -> str:
        normalized = json.dumps(
            self.canonical_snapshot(), sort_keys=True, ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()

    def audit_summary(self) -> dict[str, Any]:
        return {
            "case_id": self.identity.case_id,
            "case_version": self.case_version,
            "case_hash": self.case_hash,
            "analysis_as_of_date": (
                self.identity.analysis_as_of_date.isoformat()
                if self.identity.analysis_as_of_date
                else None
            ),
            "approved_transaction_count": len(self.approved_transactions),
            "approved_evidence_count": sum(
                item.status == "approved" for item in self.evidence
            ),
            "unresolved_evidence_ids": self.unresolved_evidence_ids,
            "calculation_ids": sorted(self.calculations),
            "scenario_ids": [item.scenario_id for item in self.scenarios],
            "missing_inputs": [item.input_name for item in self.missing_inputs],
            "capabilities": self.capabilities.model_dump(),
            "trade_finance_domain_version": self.trade_finance.domain_version,
            "trade_finance_record_counts": self.trade_finance.record_counts(),
            "authority_boundary": (
                "Financial arithmetic remains authoritative only in deterministic "
                "engines. AI may plan, reconcile, and explain with cited evidence."
            ),
        }
