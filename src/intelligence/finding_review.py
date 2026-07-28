"""Human-in-the-loop review ledger for deterministic clause findings.

Review decisions are append-only overlays. They do not mutate or delete the original
finding, risk signal, rule metadata, or evidence. A later decision must explicitly
supersede the latest decision for the same finding.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..copilot_case import FindingReviewDecision, UnifiedCopilotCase


class FindingReviewOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_before_hash: str
    case_after_hash: str
    review_id: str
    finding_id: str
    decision: str
    superseded_review_id: str | None = None


class FindingReviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    review_status: str
    latest_review_id: str | None = None
    reviewer_role: str | None = None
    review_note: str | None = None
    supporting_evidence_ids: list[str] = Field(default_factory=list)


def latest_finding_review_decisions(
    case: UnifiedCopilotCase,
) -> dict[str, FindingReviewDecision]:
    """Validate each append-only review chain and return its latest decision."""

    by_id: dict[str, FindingReviewDecision] = {}
    latest: dict[str, FindingReviewDecision] = {}
    for decision in case.finding_reviews:
        if decision.review_id in by_id:
            raise ValueError(f"Finding review ID is duplicated: {decision.review_id}")

        current = latest.get(decision.finding_id)
        superseded_id = decision.supersedes_review_id
        if superseded_id is None:
            if current is not None:
                raise ValueError(
                    "Finding review ledger has multiple unsuperseded decisions for "
                    f"{decision.finding_id}: {current.review_id}, {decision.review_id}"
                )
        else:
            superseded = by_id.get(superseded_id)
            if superseded is None:
                raise ValueError(
                    "Finding review supersession must reference a prior review ID: "
                    f"{superseded_id}"
                )
            if superseded.finding_id != decision.finding_id:
                raise ValueError(
                    "Finding review cannot supersede a review for a different finding: "
                    f"{superseded_id} belongs to {superseded.finding_id}, "
                    f"not {decision.finding_id}"
                )
            if current is None or current.review_id != superseded_id:
                expected = current.review_id if current is not None else "none"
                raise ValueError(
                    "Finding review must supersede the latest review for the same finding; "
                    f"expected {expected}, received {superseded_id}"
                )

        by_id[decision.review_id] = decision
        latest[decision.finding_id] = decision
    return latest


def finding_review_summary(
    case: UnifiedCopilotCase,
    finding_id: str,
) -> FindingReviewSummary:
    """Return the effective human-review status without changing the finding."""

    latest = latest_finding_review_decisions(case).get(finding_id)
    if latest is None:
        return FindingReviewSummary(
            finding_id=finding_id,
            review_status="unreviewed",
        )
    return FindingReviewSummary(
        finding_id=finding_id,
        review_status=latest.decision,
        latest_review_id=latest.review_id,
        reviewer_role=latest.reviewer_role,
        review_note=latest.review_note,
        supporting_evidence_ids=list(latest.supporting_evidence_ids),
    )


def apply_finding_review_decision(
    case: UnifiedCopilotCase,
    decision: FindingReviewDecision,
) -> tuple[UnifiedCopilotCase, FindingReviewOutcome]:
    """Append one validated review decision and return a new immutable case snapshot."""

    findings = {
        item.clause_finding_id: item
        for item in case.trade_finance.clause_findings
    }
    if decision.finding_id not in findings:
        raise ValueError(f"Clause finding not found: {decision.finding_id}")
    if any(item.review_id == decision.review_id for item in case.finding_reviews):
        raise ValueError(f"Finding review ID already exists: {decision.review_id}")

    evidence_ids = {item.evidence_id for item in case.evidence}
    unknown_evidence = sorted(
        identifier
        for identifier in decision.supporting_evidence_ids
        if identifier not in evidence_ids
    )
    if unknown_evidence:
        raise ValueError(
            "Finding review cites unknown case evidence IDs: "
            + ", ".join(unknown_evidence)
        )

    latest = latest_finding_review_decisions(case).get(decision.finding_id)
    if latest is None:
        if decision.supersedes_review_id is not None:
            raise ValueError(
                "First review decision for a finding cannot supersede another review"
            )
    else:
        if decision.supersedes_review_id != latest.review_id:
            raise ValueError(
                "A later finding review must explicitly supersede the latest review "
                f"{latest.review_id}"
            )

    updated_case = case.model_copy(
        update={"finding_reviews": [*case.finding_reviews, decision]}
    )
    outcome = FindingReviewOutcome(
        case_before_hash=case.case_hash,
        case_after_hash=updated_case.case_hash,
        review_id=decision.review_id,
        finding_id=decision.finding_id,
        decision=decision.decision,
        superseded_review_id=decision.supersedes_review_id,
    )
    return updated_case, outcome
