from datetime import date

from src.copilot_case import CaseEvidenceItem, CaseIdentity, UnifiedCopilotCase
from src.copilot_workspace import CopilotWorkspace, build_copilot_workspace


def _case() -> UnifiedCopilotCase:
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-WS-001",
            company_name="Example Exporter",
            analysis_as_of_date=date(2026, 7, 26),
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
                "amount_fc": 100000,
                "expected_date": "2026-09-30",
                "status": "confirmed",
            }
        ],
        monthly_cost_assumptions={"monthly_fixed_cost_krw": 10000000},
    )


def test_workspace_contains_all_primary_sections():
    workspace = build_copilot_workspace(_case(), "통합 무역위험과 상담 준비자료를 검토해줘")

    assert [section.section_id for section in workspace.sections] == [
        "objective_and_plan",
        "data_readiness",
        "scenario_candidates",
        "integrated_risk_chains",
        "consultation_brief",
        "citations_and_audit",
    ]


def test_workspace_uses_one_case_snapshot():
    case = _case()
    workspace = build_copilot_workspace(case, "유동성 위험을 검토해줘")

    assert workspace.case_hash == case.case_hash
    assert workspace.scenarios.case_hash == case.case_hash
    assert workspace.reasoning.case_hash == case.case_hash


def test_workspace_trace_is_contiguous_and_reviewable():
    workspace = build_copilot_workspace(_case(), "환율 및 헤지 검토")

    assert [step.sequence for step in workspace.trace] == list(
        range(1, len(workspace.trace) + 1)
    )
    assert workspace.trace[0].authority == "case_state"
    assert all(step.authority != "deterministic_engine" for step in workspace.trace)


def test_workspace_discloses_blocked_scenarios():
    workspace = build_copilot_workspace(_case(), "통합 검토")

    scenario_section = next(
        section for section in workspace.sections if section.section_id == "scenario_candidates"
    )
    assert scenario_section.payload is not None
    assert any(
        candidate["readiness"] == "blocked"
        for candidate in scenario_section.payload["candidates"]
    )


def test_workspace_audit_export_contains_ids_and_human_review_boundary():
    case = _case()
    workspace = build_copilot_workspace(case, "상담 준비")

    assert workspace.audit_export["workspace_id"] == workspace.workspace_id
    assert workspace.audit_export["case_audit"]["case_hash"] == case.case_hash
    assert workspace.audit_export["human_review_required"] is True
    assert workspace.audit_export["evidence_ids"] == ["EVD-001"]


def test_workspace_id_is_stable_for_same_snapshot_and_objective():
    first = build_copilot_workspace(_case(), "통합 검토")
    second = build_copilot_workspace(_case(), "통합 검토")

    assert first.workspace_id == second.workspace_id


def test_workspace_generation_does_not_mutate_case():
    case = _case()
    before = case.case_hash

    build_copilot_workspace(case, "통합 검토")

    assert case.case_hash == before
    assert case.scenarios == []


def test_workspace_keeps_required_demo_disclaimer():
    workspace = build_copilot_workspace(_case(), "상담 준비")

    assert "결정론적 fallback 모드" in workspace.disclaimer
    assert "구조화 AI 공급자 연동 인터페이스" in workspace.disclaimer
    assert "official credit rating" in workspace.authority_boundary


def test_workspace_rejects_mixed_case_snapshots():
    workspace = build_copilot_workspace(_case(), "통합 검토")
    payload = workspace.model_dump()
    payload["scenarios"]["case_hash"] = "different"

    try:
        CopilotWorkspace.model_validate(payload)
    except ValueError as exc:
        assert "same case snapshot" in str(exc)
    else:
        raise AssertionError("Mixed case snapshots must be rejected")
