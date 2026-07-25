"""Governed read-only intelligence over a :class:`UnifiedCopilotCase`.

These helpers do not perform financial arithmetic and do not mutate case state. They
turn reviewed case metadata into structured readiness, conflict, information-gap,
and consultation outputs that can be shown to a human before deterministic analysis.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field

from .copilot_case import MissingInput, UnifiedCopilotCase

ReadinessStatus = Literal["ready", "ready_with_review", "blocked"]
ConflictSeverity = Literal["high", "medium", "low"]


class ReadinessIssue(BaseModel):
    issue_type: str
    message: str
    evidence_ids: list[str] = Field(default_factory=list)
    transaction_ids: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)


class DocumentReadinessReport(BaseModel):
    status: ReadinessStatus
    readiness_percent: int = Field(ge=0, le=100)
    evidence_count: int
    approved_evidence_count: int
    unresolved_evidence_count: int
    approved_transaction_count: int
    issues: list[ReadinessIssue] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CrossDocumentConflict(BaseModel):
    conflict_id: str
    severity: ConflictSeverity
    field_name: str
    transaction_id: str | None = None
    observed_values: list[str]
    source_labels: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    requires_human_review: bool = True


class InformationGapReport(BaseModel):
    gaps: list[MissingInput]
    blocked_capabilities: list[str] = Field(default_factory=list)
    can_continue_partial_review: bool


class ConsultationQuestion(BaseModel):
    question_id: str
    question: str
    rationale: str
    priority: Literal["high", "medium", "low"]
    related_inputs: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ConsultationBrief(BaseModel):
    case_id: str
    company_name: str | None
    analysis_as_of_date: str | None
    readiness: DocumentReadinessReport
    conflicts: list[CrossDocumentConflict]
    information_gaps: InformationGapReport
    questions: list[ConsultationQuestion]
    finding_ids: list[str]
    calculation_ids: list[str]
    review_priorities: list[str]
    authority_boundary: str
    disclaimer: str


def _transaction_id(row: dict[str, Any], index: int) -> str:
    return str(row.get("transaction_id") or row.get("id") or f"ROW-{index + 1}")


def get_document_readiness(case: UnifiedCopilotCase) -> DocumentReadinessReport:
    """Assess whether reviewed evidence is sufficient for deterministic analysis."""

    total = len(case.evidence)
    approved = sum(item.status == "approved" for item in case.evidence)
    unresolved = total - approved
    issues: list[ReadinessIssue] = []

    if total == 0:
        issues.append(
            ReadinessIssue(
                issue_type="missing_document_evidence",
                message="No reviewed document evidence is attached to the case.",
                blocks=["document-grounded analysis", "cross-document reconciliation"],
            )
        )
    for item in case.evidence:
        if item.status != "approved":
            issues.append(
                ReadinessIssue(
                    issue_type=f"evidence_{item.status}",
                    message=f"Evidence {item.evidence_id} requires review before it is authoritative.",
                    evidence_ids=[item.evidence_id],
                    transaction_ids=item.linked_transaction_ids,
                    blocks=["automatic reliance on extracted fields"],
                )
            )
        if item.warnings:
            issues.append(
                ReadinessIssue(
                    issue_type="evidence_warning",
                    message="; ".join(item.warnings),
                    evidence_ids=[item.evidence_id],
                    transaction_ids=item.linked_transaction_ids,
                    blocks=["unqualified interpretation"],
                )
            )

    if not case.approved_transactions:
        issues.append(
            ReadinessIssue(
                issue_type="missing_approved_transactions",
                message="No human-approved transactions are available for deterministic calculation.",
                blocks=["exposure", "maturity", "cash-flow", "hedge analysis"],
            )
        )

    evidence_component = 0 if total == 0 else round(60 * approved / total)
    transaction_component = 40 if case.approved_transactions else 0
    score = evidence_component + transaction_component

    if not case.approved_transactions:
        status: ReadinessStatus = "blocked"
    elif unresolved or any(item.warnings for item in case.evidence):
        status = "ready_with_review"
    else:
        status = "ready"

    return DocumentReadinessReport(
        status=status,
        readiness_percent=score,
        evidence_count=total,
        approved_evidence_count=approved,
        unresolved_evidence_count=unresolved,
        approved_transaction_count=len(case.approved_transactions),
        issues=issues,
        limitations=[
            "Readiness is a workflow-control indicator, not a probability that the documents are correct.",
            "Only human-approved transactions may enter deterministic financial calculations.",
        ],
    )


def get_cross_document_conflicts(case: UnifiedCopilotCase) -> list[CrossDocumentConflict]:
    """Report inconsistent values for repeated transaction IDs and explicit warnings."""

    comparable_fields = (
        "transaction_type",
        "currency",
        "amount_fc",
        "expected_date",
        "counterparty_name",
        "payment_terms",
        "document_reference",
    )
    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for index, row in enumerate(case.approved_transactions):
        grouped[_transaction_id(row, index)].append((index, row))

    conflicts: list[CrossDocumentConflict] = []
    counter = 1
    for transaction_id, rows in sorted(grouped.items()):
        if len(rows) < 2:
            continue
        for field in comparable_fields:
            values: dict[str, list[str]] = defaultdict(list)
            for index, row in rows:
                value = row.get(field)
                if value not in (None, ""):
                    label = str(row.get("source_filename") or row.get("source_name") or f"row:{index + 1}")
                    values[str(value)].append(label)
            if len(values) > 1:
                severity: ConflictSeverity = "high" if field in {"currency", "amount_fc", "expected_date"} else "medium"
                linked_evidence = sorted(
                    {
                        item.evidence_id
                        for item in case.evidence
                        if transaction_id in item.linked_transaction_ids
                    }
                )
                conflicts.append(
                    CrossDocumentConflict(
                        conflict_id=f"CONFLICT-{counter:03d}",
                        severity=severity,
                        field_name=field,
                        transaction_id=transaction_id,
                        observed_values=sorted(values),
                        source_labels=sorted({label for labels in values.values() for label in labels}),
                        evidence_ids=linked_evidence,
                    )
                )
                counter += 1

    for item in case.evidence:
        for warning in item.warnings:
            lower = warning.lower()
            if any(token in lower for token in ("conflict", "mismatch", "불일치", "상충")):
                conflicts.append(
                    CrossDocumentConflict(
                        conflict_id=f"CONFLICT-{counter:03d}",
                        severity="medium",
                        field_name="document_warning",
                        transaction_id=item.linked_transaction_ids[0] if len(item.linked_transaction_ids) == 1 else None,
                        observed_values=[warning],
                        source_labels=[item.source_name],
                        evidence_ids=[item.evidence_id],
                    )
                )
                counter += 1
    return conflicts


def get_information_gaps(case: UnifiedCopilotCase) -> InformationGapReport:
    """Combine explicit case gaps with capability-derived missing inputs."""

    gaps = list(case.missing_inputs)
    existing = {gap.input_name for gap in gaps}

    derived = [
        ("approved transactions", not case.approved_transactions, ["exposure", "maturity", "cash-flow", "hedge"]),
        ("document evidence", not case.evidence, ["provenance", "document reconciliation"]),
        ("monthly cost assumptions", not case.monthly_cost_assumptions, ["cash-flow", "settlement-delay stress"]),
        ("official or disclosed FX reference", not case.capabilities.official_fx_reference, ["hedge comparison", "forward reference"]),
        ("financial context", not case.capabilities.financial_context, ["financial-buffer context"]),
        ("policy corpus", not case.capabilities.policy_corpus, ["policy-grounded consultation brief"]),
    ]
    for name, missing, blocks in derived:
        if missing and name not in existing:
            gaps.append(
                MissingInput(
                    input_name=name,
                    reason="The unified case does not currently contain an available reviewed source.",
                    blocks=blocks,
                    requested_from="customer or reviewed official source",
                    can_use_disclosed_assumption=name in {"monthly cost assumptions"},
                )
            )

    blocked = sorted({block for gap in gaps for block in gap.blocks})
    return InformationGapReport(
        gaps=gaps,
        blocked_capabilities=blocked,
        can_continue_partial_review=bool(case.approved_transactions or case.evidence),
    )


def get_consultation_questions(
    case: UnifiedCopilotCase,
    *,
    conflicts: list[CrossDocumentConflict] | None = None,
    gaps: InformationGapReport | None = None,
) -> list[ConsultationQuestion]:
    """Generate deterministic, review-oriented questions from known gaps and conflicts."""

    conflicts = conflicts if conflicts is not None else get_cross_document_conflicts(case)
    gaps = gaps if gaps is not None else get_information_gaps(case)
    questions: list[ConsultationQuestion] = []
    counter = 1

    for conflict in conflicts:
        questions.append(
            ConsultationQuestion(
                question_id=f"QUESTION-{counter:03d}",
                question=(
                    f"Please confirm the authoritative {conflict.field_name}"
                    + (f" for transaction {conflict.transaction_id}" if conflict.transaction_id else "")
                    + f"; the reviewed sources contain: {', '.join(conflict.observed_values)}."
                ),
                rationale="Conflicting source values must be resolved before relying on the affected field.",
                priority="high" if conflict.severity == "high" else "medium",
                related_inputs=[conflict.field_name],
                evidence_ids=conflict.evidence_ids,
            )
        )
        counter += 1

    templates = {
        "monthly cost assumptions": "What is the minimum monthly operating-cash requirement for the analysis horizon?",
        "official or disclosed FX reference": "Which dated public reference rate or explicitly disclosed scenario rate should be used?",
        "financial context": "May the latest reviewed financial statements be used for 재무건전성 사전 스크리닝?",
        "policy corpus": "Which current official guidance should be reviewed during the consultation?",
        "document evidence": "Which trade documents can be provided to support the transaction terms and dates?",
        "approved transactions": "Which extracted transactions have been reviewed and approved for analysis?",
    }
    for gap in gaps.gaps:
        question = templates.get(gap.input_name, f"Can you provide or confirm: {gap.input_name}?")
        questions.append(
            ConsultationQuestion(
                question_id=f"QUESTION-{counter:03d}",
                question=question,
                rationale=gap.reason,
                priority="high" if any(item in gap.blocks for item in ("exposure", "cash-flow", "maturity")) else "medium",
                related_inputs=[gap.input_name],
            )
        )
        counter += 1

    if case.approved_transactions and not case.foreign_cash_positions:
        questions.append(
            ConsultationQuestion(
                question_id=f"QUESTION-{counter:03d}",
                question="Are there existing foreign-currency cash balances or hedge contracts that should be included?",
                rationale="Balance-sheet foreign currency and existing contracts materially affect consultation context.",
                priority="high",
                related_inputs=["foreign cash positions", "existing hedge contracts"],
            )
        )
    return questions


def build_bank_consultation_brief(case: UnifiedCopilotCase) -> ConsultationBrief:
    """Build a cited pre-consultation package without approval or suitability claims."""

    readiness = get_document_readiness(case)
    conflicts = get_cross_document_conflicts(case)
    gaps = get_information_gaps(case)
    questions = get_consultation_questions(case, conflicts=conflicts, gaps=gaps)

    priorities: list[str] = []
    if conflicts:
        priorities.append("Resolve high-impact document and transaction-field conflicts before final analysis.")
    if readiness.status != "ready":
        priorities.append("Complete human review of unresolved evidence and extracted transactions.")
    if any("cash-flow" in gap.blocks for gap in gaps.gaps):
        priorities.append("Obtain cash-flow assumptions before interpreting settlement-timing shortfalls.")
    if case.findings:
        priorities.append("Review grounded case findings in priority order with their calculation and evidence IDs.")
    if not priorities:
        priorities.append("Proceed with the reviewable deterministic analysis plan and preserve all citations.")

    return ConsultationBrief(
        case_id=case.identity.case_id,
        company_name=case.identity.company_name,
        analysis_as_of_date=(case.identity.analysis_as_of_date.isoformat() if case.identity.analysis_as_of_date else None),
        readiness=readiness,
        conflicts=conflicts,
        information_gaps=gaps,
        questions=questions,
        finding_ids=[finding.finding_id for finding in case.findings],
        calculation_ids=sorted(case.calculations),
        review_priorities=priorities,
        authority_boundary=(
            "This brief supports pre-consultation review only. It does not issue an official credit rating, "
            "approve a loan, determine product suitability, or provide an executable KB quote."
        ),
        disclaimer=(
            "현재 데모는 외부 생성형 AI가 연결되지 않은 결정론적 fallback 모드이며, "
            "구조화 AI 공급자 연동 인터페이스는 구현되어 있다."
        ),
    )
