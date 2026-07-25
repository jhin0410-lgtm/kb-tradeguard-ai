"""Grounded integrated reasoning over evidence and deterministic outputs.

This module does not calculate financial values. It links already-reviewed evidence,
case findings, scenario state, and deterministic calculation identifiers into an
auditable risk chain. Computed facts, source facts, and interpretive inferences are
kept explicitly separate.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .copilot_case import UnifiedCopilotCase

ReasoningNodeKind = Literal[
    "document_fact",
    "calculated_fact",
    "scenario_assumption",
    "context_fact",
    "inference",
    "consultation_priority",
]
ConfidenceLevel = Literal["high", "medium", "low"]


class RiskChainNode(BaseModel):
    node_id: str
    sequence: int = Field(ge=1)
    kind: ReasoningNodeKind
    statement: str
    calculation_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    derived_from_node_ids: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_grounding(self):
        direct = self.calculation_ids or self.evidence_ids or self.scenario_ids
        if self.kind in {
            "document_fact",
            "calculated_fact",
            "scenario_assumption",
            "context_fact",
        } and not direct:
            raise ValueError(f"{self.kind} nodes require a direct source reference.")
        if self.kind in {"inference", "consultation_priority"} and not (
            direct or self.derived_from_node_ids
        ):
            raise ValueError("Interpretive nodes require direct or upstream grounding.")
        return self


class IntegratedRiskChain(BaseModel):
    chain_id: str
    case_id: str
    case_hash: str
    title: str
    nodes: list[RiskChainNode]
    overall_confidence: ConfidenceLevel
    unresolved_gaps: list[str] = Field(default_factory=list)
    authority_boundary: str = (
        "The chain links reviewed evidence and deterministic results. Interpretive "
        "connections are not new calculations, approvals, ratings, or product advice."
    )

    @model_validator(mode="after")
    def validate_sequence_and_dependencies(self):
        expected = list(range(1, len(self.nodes) + 1))
        if [node.sequence for node in self.nodes] != expected:
            raise ValueError("Risk-chain node sequence must be contiguous and ordered.")
        known: set[str] = set()
        for node in self.nodes:
            unknown = set(node.derived_from_node_ids) - known
            if unknown:
                raise ValueError(
                    "Risk-chain nodes may reference only earlier nodes: "
                    + ", ".join(sorted(unknown))
                )
            known.add(node.node_id)
        return self


class IntegratedReasoningReport(BaseModel):
    case_id: str
    case_hash: str
    chains: list[IntegratedRiskChain]
    uncoupled_finding_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def _stable_id(prefix: str, payload: dict) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def _node(
    chain_key: str,
    sequence: int,
    kind: ReasoningNodeKind,
    statement: str,
    *,
    calculation_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    scenario_ids: list[str] | None = None,
    derived_from: list[str] | None = None,
    confidence: ConfidenceLevel = "medium",
    limitations: list[str] | None = None,
) -> RiskChainNode:
    payload = {
        "chain": chain_key,
        "sequence": sequence,
        "kind": kind,
        "statement": statement,
        "calculation_ids": sorted(calculation_ids or []),
        "evidence_ids": sorted(evidence_ids or []),
        "scenario_ids": sorted(scenario_ids or []),
    }
    return RiskChainNode(
        node_id=_stable_id("NODE", payload),
        sequence=sequence,
        kind=kind,
        statement=statement,
        calculation_ids=calculation_ids or [],
        evidence_ids=evidence_ids or [],
        scenario_ids=scenario_ids or [],
        derived_from_node_ids=derived_from or [],
        confidence=confidence,
        limitations=limitations or [],
    )


def build_integrated_risk_reasoning(case: UnifiedCopilotCase) -> IntegratedReasoningReport:
    """Build cited risk chains without inventing values or recomputing results."""

    chains: list[IntegratedRiskChain] = []
    used_findings: set[str] = set()

    for finding in sorted(
        case.findings,
        key=lambda item: {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}[item.priority],
    ):
        if not (finding.calculation_ids or finding.evidence_ids):
            continue
        used_findings.add(finding.finding_id)
        chain_key = f"{case.identity.case_id}:{finding.finding_id}:{case.case_hash}"
        nodes: list[RiskChainNode] = []

        if finding.evidence_ids:
            nodes.append(
                _node(
                    chain_key,
                    len(nodes) + 1,
                    "document_fact",
                    f"Reviewed source evidence supports the finding: {finding.title}.",
                    evidence_ids=finding.evidence_ids,
                    confidence="high",
                )
            )
        if finding.calculation_ids:
            nodes.append(
                _node(
                    chain_key,
                    len(nodes) + 1,
                    "calculated_fact",
                    f"Deterministic calculations support the finding: {finding.summary}",
                    calculation_ids=finding.calculation_ids,
                    confidence="high",
                )
            )

        upstream = [item.node_id for item in nodes]
        inference = _node(
            chain_key,
            len(nodes) + 1,
            "inference",
            (
                f"Taken together, the cited facts indicate a {finding.category} issue "
                f"that should be reviewed at {finding.priority} priority."
            ),
            derived_from=upstream,
            confidence="medium" if len(nodes) > 1 else "low",
            limitations=[
                "This is an interpretive link between cited facts, not a new financial calculation."
            ],
        )
        nodes.append(inference)
        nodes.append(
            _node(
                chain_key,
                len(nodes) + 1,
                "consultation_priority",
                (
                    "Confirm the underlying evidence and assumptions, then discuss the cited "
                    "risk driver before considering any product or financing response."
                ),
                derived_from=[inference.node_id],
                confidence="medium",
                limitations=[
                    "This is consultation preparation, not loan approval, product suitability, or an official credit rating."
                ],
            )
        )

        chain_payload = {
            "case_hash": case.case_hash,
            "finding_id": finding.finding_id,
            "node_ids": [item.node_id for item in nodes],
        }
        chains.append(
            IntegratedRiskChain(
                chain_id=_stable_id("CHAIN", chain_payload),
                case_id=case.identity.case_id,
                case_hash=case.case_hash,
                title=finding.title,
                nodes=nodes,
                overall_confidence=(
                    "high" if finding.calculation_ids and finding.evidence_ids else "medium"
                ),
                unresolved_gaps=[item.input_name for item in case.missing_inputs],
            )
        )

    return IntegratedReasoningReport(
        case_id=case.identity.case_id,
        case_hash=case.case_hash,
        chains=chains,
        uncoupled_finding_ids=[
            item.finding_id for item in case.findings if item.finding_id not in used_findings
        ],
        limitations=[
            "No financial values are created or recalculated by the reasoning layer.",
            "Causal wording is limited to traceable interpretive links and requires human review.",
            "재무 컨텍스트는 재무건전성 사전 스크리닝이며 공식 신용등급이 아닙니다.",
        ],
    )
