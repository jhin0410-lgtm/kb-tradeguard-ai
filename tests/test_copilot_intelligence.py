from datetime import date

from src.copilot_case import (
    CaseEvidenceItem,
    CaseIdentity,
    UnifiedCopilotCase,
)
from src.copilot_intelligence import (
    build_bank_consultation_brief,
    get_consultation_questions,
    get_cross_document_conflicts,
    get_document_readiness,
    get_information_gaps,
)


def _case(**updates):
    base = UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-001",
            company_name="Demo Exporter",
            analysis_as_of_date=date(2026, 8, 1),
        ),
        evidence=[
            CaseEvidenceItem(
                evidence_id="EVD-001",
                evidence_type="commercial_invoice",
                source_name="invoice.pdf",
                status="approved",
                linked_transaction_ids=["EXP-001"],
            )
        ],
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "expected_date": "2026-11-30",
                "source_filename": "invoice.pdf",
            }
        ],
    )
    return base.model_copy(update=updates)


def test_document_readiness_is_ready_for_approved_evidence_and_transactions():
    report = get_document_readiness(_case())

    assert report.status == "ready"
    assert report.readiness_percent == 100
    assert report.approved_evidence_count == 1
    assert not report.issues


def test_document_readiness_blocks_without_approved_transactions():
    report = get_document_readiness(_case(approved_transactions=[]))

    assert report.status == "blocked"
    assert report.readiness_percent == 60
    assert any(issue.issue_type == "missing_approved_transactions" for issue in report.issues)


def test_unresolved_evidence_produces_ready_with_review():
    evidence = [
        CaseEvidenceItem(
            evidence_id="EVD-002",
            evidence_type="purchase_order",
            source_name="po.pdf",
            status="review_required",
            linked_transaction_ids=["EXP-001"],
            warnings=["Payment date mismatch requires review"],
        )
    ]
    report = get_document_readiness(_case(evidence=evidence))

    assert report.status == "ready_with_review"
    assert report.unresolved_evidence_count == 1
    assert report.readiness_percent == 40


def test_cross_document_conflict_detects_repeated_transaction_amount_difference():
    transactions = [
        {
            "transaction_id": "EXP-001",
            "currency": "USD",
            "amount_fc": 500000,
            "expected_date": "2026-11-30",
            "source_filename": "invoice.pdf",
        },
        {
            "transaction_id": "EXP-001",
            "currency": "USD",
            "amount_fc": 480000,
            "expected_date": "2026-11-30",
            "source_filename": "po.xlsx",
        },
    ]
    conflicts = get_cross_document_conflicts(_case(approved_transactions=transactions))

    amount_conflict = next(item for item in conflicts if item.field_name == "amount_fc")
    assert amount_conflict.severity == "high"
    assert amount_conflict.transaction_id == "EXP-001"
    assert amount_conflict.observed_values == ["480000", "500000"]
    assert amount_conflict.evidence_ids == ["EVD-001"]


def test_warning_based_conflict_is_reported():
    evidence = [
        CaseEvidenceItem(
            evidence_id="EVD-003",
            evidence_type="contract",
            source_name="contract.pdf",
            status="approved",
            warnings=["Payment terms conflict with invoice"],
        )
    ]
    conflicts = get_cross_document_conflicts(_case(evidence=evidence))

    assert len(conflicts) == 1
    assert conflicts[0].field_name == "document_warning"
    assert conflicts[0].evidence_ids == ["EVD-003"]


def test_information_gaps_are_capability_derived_without_duplicates():
    report = get_information_gaps(_case())
    names = [gap.input_name for gap in report.gaps]

    assert "monthly cost assumptions" in names
    assert "official or disclosed FX reference" in names
    assert "financial context" in names
    assert "policy corpus" in names
    assert names.count("monthly cost assumptions") == 1
    assert report.can_continue_partial_review is True


def test_consultation_questions_cover_conflicts_and_missing_inputs():
    transactions = [
        {"transaction_id": "EXP-001", "currency": "USD", "amount_fc": 500000},
        {"transaction_id": "EXP-001", "currency": "EUR", "amount_fc": 500000},
    ]
    case = _case(approved_transactions=transactions)
    questions = get_consultation_questions(case)

    assert any("authoritative currency" in item.question for item in questions)
    assert any("minimum monthly operating-cash" in item.question for item in questions)
    assert any("foreign-currency cash balances" in item.question for item in questions)


def test_consultation_brief_preserves_governance_boundary_and_disclaimer():
    brief = build_bank_consultation_brief(_case())

    assert brief.case_id == "CASE-001"
    assert brief.company_name == "Demo Exporter"
    assert "official credit rating" in brief.authority_boundary
    assert "executable KB quote" in brief.authority_boundary
    assert "결정론적 fallback" in brief.disclaimer
    assert brief.readiness.status == "ready"


def test_consultation_tools_do_not_mutate_case():
    case = _case()
    before = case.case_hash

    build_bank_consultation_brief(case)

    assert case.case_hash == before
