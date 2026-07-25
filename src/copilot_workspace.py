"""Unified presentation contract for the Global Trade Copilot workspace.

The workspace composes existing governed modules into one immutable, audit-ready
view model. It does not execute financial arithmetic, mutate transactions, or
approve scenarios. Streamlit and future API clients can render the same contract.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .copilot_case import UnifiedCopilotCase
from .copilot_intelligence import (
    ConsultationBrief,
    DocumentReadinessReport,
    build_bank_consultation_brief,
    get_document_readiness,
)
from .copilot_planning import CopilotAnalysisPlan, build_copilot_analysis_plan
from .copilot_reasoning import IntegratedReasoningReport, build_integrated_risk_reasoning
from .copilot_scenarios import ScenarioProposalSet, propose_scenarios

WorkspaceSectionStatus = Literal["ready", "blocked", "empty", "review_required"]
TraceStatus = Literal["completed", "blocked", "not_run"]


class WorkspaceSection(BaseModel):
    section_id: str
    title: str
    status: WorkspaceSectionStatus
    summary: str
    payload: dict[str, Any] | list[Any] | None = None
    related_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class WorkspaceTraceStep(BaseModel):
    sequence: int = Field(ge=1)
    component: str
    action: str
    status: TraceStatus
    output_ids: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    authority: Literal["case_state", "deterministic_engine", "governed_reasoning"]


class CopilotWorkspace(BaseModel):
    workspace_id: str
    case_id: str
    case_hash: str
    user_objective: str
    generated_at: datetime
    plan: CopilotAnalysisPlan
    readiness: DocumentReadinessReport
    scenarios: ScenarioProposalSet
    reasoning: IntegratedReasoningReport
    consultation_brief: ConsultationBrief
    sections: list[WorkspaceSection]
    trace: list[WorkspaceTraceStep]
    audit_export: dict[str, Any]
    disclaimer: str = (
        "현재 데모는 외부 생성형 AI가 연결되지 않은 결정론적 fallback 모드이며, "
        "구조화 AI 공급자 연동 인터페이스는 구현되어 있다."
    )
    authority_boundary: str = (
        "Financial arithmetic remains authoritative only in deterministic engines. "
        "The workspace plans, organizes, reconciles, and explains read-only results; "
        "it does not approve loans, determine product suitability, issue an official "
        "credit rating, or present theoretical rates as executable KB quotes."
    )

    @model_validator(mode="after")
    def validate_snapshot_consistency(self):
        snapshot_hashes = {
            self.case_hash,
            self.scenarios.case_hash,
            self.reasoning.case_hash,
        }
        if len(snapshot_hashes) != 1:
            raise ValueError("Workspace components must reference the same case snapshot.")
        expected = list(range(1, len(self.trace) + 1))
        if [step.sequence for step in self.trace] != expected:
            raise ValueError("Workspace trace sequence must be contiguous and ordered.")
        return self


def _workspace_id(case_hash: str, objective: str) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {"case_hash": case_hash, "objective": objective},
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"WORKSPACE-{digest}"


def _section_status(*, ready: bool = False, blocked: bool = False, empty: bool = False) -> WorkspaceSectionStatus:
    if blocked:
        return "blocked"
    if empty:
        return "empty"
    return "ready" if ready else "review_required"


def build_copilot_workspace(case: UnifiedCopilotCase, user_objective: str) -> CopilotWorkspace:
    """Compose one renderable workspace from a stable unified-case snapshot."""

    plan = build_copilot_analysis_plan(user_objective, case.capabilities)
    readiness = get_document_readiness(case)
    scenarios = propose_scenarios(case)
    reasoning = build_integrated_risk_reasoning(case)
    brief = build_bank_consultation_brief(case)

    ready_plan_steps = [step for step in plan.steps if step.status == "ready"]
    blocked_plan_steps = [step for step in plan.steps if step.status == "blocked"]
    ready_scenarios = scenarios.ready_candidates

    sections = [
        WorkspaceSection(
            section_id="objective_and_plan",
            title="목표 및 분석 계획",
            status=_section_status(ready=bool(ready_plan_steps), blocked=not plan.can_execute_partial_plan),
            summary=(
                f"실행 가능 {len(ready_plan_steps)}개, 차단 {len(blocked_plan_steps)}개 분석 단계"
            ),
            payload=plan.model_dump(mode="json"),
            related_ids=[step.tool_name for step in plan.steps],
        ),
        WorkspaceSection(
            section_id="data_readiness",
            title="데이터 준비도",
            status=(
                "blocked" if readiness.status == "blocked" else
                "review_required" if readiness.status == "ready_with_review" else "ready"
            ),
            summary=f"문서·거래 워크플로 준비도 {readiness.readiness_percent}%",
            payload=readiness.model_dump(mode="json"),
            related_ids=case.unresolved_evidence_ids,
            limitations=readiness.limitations,
        ),
        WorkspaceSection(
            section_id="scenario_candidates",
            title="스트레스 시나리오",
            status=_section_status(ready=bool(ready_scenarios), blocked=not ready_scenarios),
            summary=f"실행 준비 {len(ready_scenarios)}개 / 전체 {len(scenarios.candidates)}개",
            payload=scenarios.model_dump(mode="json"),
            related_ids=[item.scenario_id for item in scenarios.candidates],
            limitations=[scenarios.authority_boundary],
        ),
        WorkspaceSection(
            section_id="integrated_risk_chains",
            title="통합 위험 연결",
            status=_section_status(ready=bool(reasoning.chains), empty=not reasoning.chains),
            summary=f"근거 기반 위험 체인 {len(reasoning.chains)}개",
            payload=reasoning.model_dump(mode="json"),
            related_ids=[item.chain_id for item in reasoning.chains],
            limitations=reasoning.limitations,
        ),
        WorkspaceSection(
            section_id="consultation_brief",
            title="상담 준비자료",
            status=_section_status(ready=True),
            summary=f"상담 질문 {len(brief.questions)}개, 검토 우선순위 {len(brief.review_priorities)}개",
            payload=brief.model_dump(mode="json"),
            related_ids=brief.calculation_ids + brief.finding_ids,
            limitations=[brief.authority_boundary],
        ),
        WorkspaceSection(
            section_id="citations_and_audit",
            title="인용 및 감사 추적",
            status=_section_status(ready=True),
            summary=(
                f"계산 인용 {len(case.calculations)}개, 문서 근거 {len(case.evidence)}개, "
                f"case hash {case.case_hash[:12]}"
            ),
            payload=case.audit_summary(),
            related_ids=sorted(case.calculations) + [item.evidence_id for item in case.evidence],
        ),
    ]

    trace = [
        WorkspaceTraceStep(
            sequence=1,
            component="UnifiedCopilotCase",
            action="Load reviewed case snapshot and derive capabilities",
            status="completed",
            output_ids=[case.identity.case_id, case.case_hash],
            authority="case_state",
        ),
        WorkspaceTraceStep(
            sequence=2,
            component="CopilotAnalysisPlan",
            action="Classify objective and construct dependency-aware read-only plan",
            status="completed" if plan.steps else "blocked",
            output_ids=[step.tool_name for step in plan.steps],
            missing_inputs=plan.missing_inputs,
            authority="governed_reasoning",
        ),
        WorkspaceTraceStep(
            sequence=3,
            component="DocumentReadiness",
            action="Assess evidence coverage and approved transaction readiness",
            status="blocked" if readiness.status == "blocked" else "completed",
            output_ids=case.unresolved_evidence_ids,
            authority="case_state",
        ),
        WorkspaceTraceStep(
            sequence=4,
            component="ScenarioIntelligence",
            action="Propose disclosed stress candidates without calculating outcomes",
            status="completed" if scenarios.candidates else "not_run",
            output_ids=[item.scenario_id for item in scenarios.candidates],
            missing_inputs=sorted({gap for item in scenarios.candidates for gap in item.missing_inputs}),
            authority="governed_reasoning",
        ),
        WorkspaceTraceStep(
            sequence=5,
            component="IntegratedReasoning",
            action="Link evidence and deterministic calculation identifiers into risk chains",
            status="completed" if reasoning.chains else "not_run",
            output_ids=[item.chain_id for item in reasoning.chains],
            authority="governed_reasoning",
        ),
        WorkspaceTraceStep(
            sequence=6,
            component="ConsultationBrief",
            action="Prepare questions, priorities, gaps, citations, and limitations",
            status="completed",
            output_ids=brief.finding_ids + brief.calculation_ids,
            authority="governed_reasoning",
        ),
    ]

    audit_export = {
        "workspace_schema_version": "copilot-workspace/1.0",
        "workspace_id": _workspace_id(case.case_hash, user_objective),
        "case_audit": case.audit_summary(),
        "user_objective": user_objective,
        "plan": plan.model_dump(mode="json"),
        "trace": [step.model_dump(mode="json") for step in trace],
        "scenario_ids": [item.scenario_id for item in scenarios.candidates],
        "risk_chain_ids": [item.chain_id for item in reasoning.chains],
        "calculation_ids": sorted(case.calculations),
        "evidence_ids": [item.evidence_id for item in case.evidence],
        "human_review_required": True,
    }

    return CopilotWorkspace(
        workspace_id=_workspace_id(case.case_hash, user_objective),
        case_id=case.identity.case_id,
        case_hash=case.case_hash,
        user_objective=user_objective,
        generated_at=datetime.now(timezone.utc),
        plan=plan,
        readiness=readiness,
        scenarios=scenarios,
        reasoning=reasoning,
        consultation_brief=brief,
        sections=sections,
        trace=trace,
        audit_export=audit_export,
    )
