from datetime import date, datetime, timezone

import pytest

from src.copilot_case import (
    CaseEvidenceItem,
    CaseIdentity,
    FindingReviewDecision,
    UnifiedCopilotCase,
)
from src.intelligence.finding_review import (
    apply_finding_review_decision,
    finding_review_summary,
    latest_finding_review_decisions,
)
from src.trade_finance_domain import (
    ContractClauseFinding,
    SourceReference,
    TradeFinanceDomainState,
)


def _source():
    return SourceReference(
        source_id="SRC-RULES",
        source_name="Synthetic rule fixture",
        source_tier="derived",
        source_kind="project_rule",
        source_locator="fixture://rules",
        as_of_date=date(2026, 7, 27),
        effective_date_verified=True,
    )


def _finding():
    return ContractClauseFinding(
        clause_finding_id="CLAUSE-LC-DEFERRED-TENOR-MISSING-DOC-LC-001",
        document_id="DOC-LC-001",
        evidence_ids=["EVID-LC-001"],
        clause_locator="Usance tenor",
        clause_excerpt="availability_type=usance; tenor_days=None",
        issue_type="payment_risk",
        severity="high",
        failure_path="Maturity cannot be calculated.",
        suggested_clarification_or_revision="Confirm exact tenor.",
        specialist_review=["bank"],
        source=_source(),
        record_status="verified",
    )


def _case():
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-REVIEW-001",
            analysis_as_of_date=date(2026, 7, 27),
        ),
        evidence=[
            CaseEvidenceItem(
                evidence_id="EVID-LC-001",
                evidence_type="letter_of_credit",
                source_name="lc.pdf",
                status="approved",
            ),
            CaseEvidenceItem(
                evidence_id="EVID-BANK-EMAIL-001",
                evidence_type="bank_confirmation",
                source_name="bank-email.eml",
                status="approved",
            ),
        ],
        trade_finance=TradeFinanceDomainState(clause_findings=[_finding()]),
    )


def _decision(**updates):
    payload = {
        "review_id": "REVIEW-001",
        "finding_id": _finding().clause_finding_id,
        "decision": "confirmed",
        "reviewer_role": "bank",
        "reviewer_id": "bank-reviewer-01",
        "reviewed_at": datetime(2026, 7, 27, 9, 0, tzinfo=timezone.utc),
        "review_note": "Tenor is not stated in the reviewed credit fields.",
    }
    payload.update(updates)
    return FindingReviewDecision(**payload)


def test_review_decision_changes_case_hash_without_mutating_original_case():
    case = _case()
    before = case.case_hash

    updated, outcome = apply_finding_review_decision(case, _decision())

    assert case.finding_reviews == []
    assert case.case_hash == before
    assert updated.case_hash != before
    assert outcome.case_before_hash == before
    assert outcome.case_after_hash == updated.case_hash
    assert finding_review_summary(updated, _finding().clause_finding_id).review_status == (
        "confirmed"
    )


def test_dismissed_or_needs_more_information_requires_note():
    with pytest.raises(ValueError, match="require a review_note"):
        _decision(decision="dismissed", review_note=None)
    with pytest.raises(ValueError, match="require a review_note"):
        _decision(decision="needs_more_information", review_note=None)


def test_later_review_must_explicitly_supersede_latest_decision():
    first, _ = apply_finding_review_decision(_case(), _decision())
    later = _decision(
        review_id="REVIEW-002",
        decision="dismissed",
        review_note="The issuing bank supplied an amendment stating 90 days after B/L date.",
        supporting_evidence_ids=["EVID-BANK-EMAIL-001"],
        reviewed_at=datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="explicitly supersede"):
        apply_finding_review_decision(first, later)

    corrected = later.model_copy(update={"supersedes_review_id": "REVIEW-001"})
    updated, outcome = apply_finding_review_decision(first, corrected)

    assert outcome.superseded_review_id == "REVIEW-001"
    latest = latest_finding_review_decisions(updated)[_finding().clause_finding_id]
    assert latest.review_id == "REVIEW-002"
    assert latest.decision == "dismissed"
    assert finding_review_summary(updated, _finding().clause_finding_id).supporting_evidence_ids == [
        "EVID-BANK-EMAIL-001"
    ]


def test_review_rejects_unknown_finding_and_supporting_evidence():
    with pytest.raises(ValueError, match="Clause finding not found"):
        apply_finding_review_decision(
            _case(),
            _decision(finding_id="CLAUSE-UNKNOWN"),
        )

    with pytest.raises(ValueError, match="unknown case evidence"):
        apply_finding_review_decision(
            _case(),
            _decision(supporting_evidence_ids=["EVID-UNKNOWN"]),
        )


def test_duplicate_review_id_and_ambiguous_unsuperseded_ledger_are_rejected():
    first, _ = apply_finding_review_decision(_case(), _decision())
    with pytest.raises(ValueError, match="already exists"):
        apply_finding_review_decision(first, _decision())

    ambiguous = first.model_copy(
        update={
            "finding_reviews": [
                *first.finding_reviews,
                _decision(
                    review_id="REVIEW-OTHER",
                    reviewer_id="reviewer-02",
                    reviewed_at=datetime(2026, 7, 27, 9, 30, tzinfo=timezone.utc),
                ),
            ]
        }
    )
    with pytest.raises(ValueError, match="multiple unsuperseded"):
        latest_finding_review_decisions(ambiguous)


def test_imported_ledger_rejects_cross_finding_supersession():
    case = _case()
    other_finding = _finding().model_copy(
        update={
            "clause_finding_id": "CLAUSE-OTHER-DOC-LC-001",
            "clause_locator": "Other clause",
        }
    )
    domain = case.trade_finance.model_copy(
        update={"clause_findings": [*case.trade_finance.clause_findings, other_finding]}
    )
    first = _decision()
    cross_finding = _decision(
        review_id="REVIEW-002",
        finding_id=other_finding.clause_finding_id,
        supersedes_review_id="REVIEW-001",
        reviewer_id="reviewer-02",
        reviewed_at=datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
    )
    malformed = case.model_copy(
        update={
            "trade_finance": domain,
            "finding_reviews": [first, cross_finding],
        }
    )

    with pytest.raises(ValueError, match="different finding"):
        latest_finding_review_decisions(malformed)


def test_imported_ledger_rejects_nonlatest_same_finding_supersession():
    first = _decision()
    second = _decision(
        review_id="REVIEW-002",
        supersedes_review_id="REVIEW-001",
        reviewer_id="reviewer-02",
        reviewed_at=datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
    )
    stale_branch = _decision(
        review_id="REVIEW-003",
        supersedes_review_id="REVIEW-001",
        reviewer_id="reviewer-03",
        reviewed_at=datetime(2026, 7, 27, 11, 0, tzinfo=timezone.utc),
    )
    malformed = _case().model_copy(
        update={"finding_reviews": [first, second, stale_branch]}
    )

    with pytest.raises(ValueError, match="latest review"):
        latest_finding_review_decisions(malformed)


def test_imported_ledger_rejects_cycles_and_forward_references():
    first = _decision(supersedes_review_id="REVIEW-002")
    second = _decision(
        review_id="REVIEW-002",
        supersedes_review_id="REVIEW-001",
        reviewer_id="reviewer-02",
        reviewed_at=datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
    )
    cyclic = _case().model_copy(update={"finding_reviews": [first, second]})

    with pytest.raises(ValueError, match="prior review ID"):
        latest_finding_review_decisions(cyclic)
