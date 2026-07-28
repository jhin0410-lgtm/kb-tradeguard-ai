from datetime import date

import pytest

from src.copilot_case import CaseDataAsset, CaseIdentity, UnifiedCopilotCase
from src.copilot_scenarios import (
    attach_proposed_scenarios,
    build_execution_request,
    propose_scenarios,
)


def _case(**overrides):
    payload = {
        "identity": CaseIdentity(
            case_id="CASE-001",
            company_name="Demo Exporter",
            analysis_as_of_date=date(2026, 8, 1),
        ),
        "approved_transactions": [
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "expected_date": "2026-11-30",
                "status": "expected",
            },
            {
                "transaction_id": "IMP-001",
                "transaction_type": "import",
                "currency": "USD",
                "amount_fc": 220000,
                "expected_date": "2026-10-15",
                "status": "confirmed",
            },
        ],
        "monthly_cost_assumptions": {"monthly_fixed_cost_krw": 50000000},
        "official_fx_reference": CaseDataAsset(
            asset_name="KEXIM public reference FX",
            status="available",
            source="KEXIM",
            as_of_date=date(2026, 8, 1),
            payload={"USD": 1350.0},
        ),
    }
    payload.update(overrides)
    return UnifiedCopilotCase(**payload)


def test_proposes_four_governed_scenarios():
    case = _case()
    proposals = propose_scenarios(case)
    assert [item.scenario_type for item in proposals.candidates] == [
        "settlement_delay",
        "fx_shock",
        "import_cost_increase",
        "combined_stress",
    ]
    assert len(proposals.ready_candidates) == 4
    assert all(
        item.source_case_hash == case.case_hash for item in proposals.candidates
    )


def test_largest_export_receivable_is_delay_target():
    case = _case(
        approved_transactions=[
            {
                "transaction_id": "EXP-SMALL",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 100000,
            },
            {
                "transaction_id": "EXP-LARGE",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 900000,
            },
        ]
    )
    delay = propose_scenarios(case).candidates[0]
    assert delay.target_transaction_ids == ["EXP-LARGE"]


def test_missing_cost_assumptions_block_delay_and_combined_only():
    proposals = propose_scenarios(_case(monthly_cost_assumptions={}))
    statuses = {item.scenario_type: item.readiness for item in proposals.candidates}
    assert statuses["settlement_delay"] == "blocked"
    assert statuses["combined_stress"] == "blocked"
    assert statuses["fx_shock"] == "ready"
    assert "monthly cost assumptions" in proposals.candidates[0].missing_inputs


def test_missing_fx_reference_blocks_fx_and_combined():
    proposals = propose_scenarios(_case(official_fx_reference=None))
    statuses = {item.scenario_type: item.readiness for item in proposals.candidates}
    assert statuses["fx_shock"] == "blocked"
    assert statuses["combined_stress"] == "blocked"
    assert statuses["settlement_delay"] == "ready"


def test_no_import_blocks_import_cost_candidate():
    case = _case(
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
            }
        ]
    )
    candidate = next(
        item
        for item in propose_scenarios(case).candidates
        if item.scenario_type == "import_cost_increase"
    )
    assert candidate.readiness == "blocked"
    assert candidate.missing_inputs == ["approved import transaction"]


def test_scenario_ids_are_stable_for_same_case_snapshot():
    case = _case()
    first = [item.scenario_id for item in propose_scenarios(case).candidates]
    second = [item.scenario_id for item in propose_scenarios(case).candidates]
    assert first == second


def test_execution_requires_human_approval():
    case = _case()
    candidate = propose_scenarios(case).ready_candidates[0]
    with pytest.raises(ValueError, match="explicit human approval"):
        build_execution_request(case, candidate, human_approved=False)


def test_blocked_candidate_cannot_be_executed():
    case = _case(monthly_cost_assumptions={})
    candidate = propose_scenarios(case).candidates[0]
    with pytest.raises(ValueError, match="cannot be executed"):
        build_execution_request(case, candidate, human_approved=True)


def test_ready_candidate_builds_case_bound_execution_request():
    case = _case()
    candidate = propose_scenarios(case).ready_candidates[0]
    request = build_execution_request(case, candidate, human_approved=True)
    assert request.case_hash == case.case_hash
    assert request.scenario_id == candidate.scenario_id
    assert request.execution_tool == "run_cashflow_delay_scenario"


def test_stale_candidate_cannot_be_rebound_to_changed_case():
    case = _case()
    candidate = propose_scenarios(case).ready_candidates[0]
    changed_transactions = [dict(item) for item in case.approved_transactions]
    changed_transactions[0]["amount_fc"] = 750000
    changed = case.model_copy(
        update={"approved_transactions": changed_transactions}
    )

    with pytest.raises(ValueError, match="different case snapshot"):
        build_execution_request(changed, candidate, human_approved=True)


def test_attach_proposals_returns_copy_and_preserves_original():
    case = _case()
    original_hash = case.case_hash
    proposals = propose_scenarios(case)
    updated = attach_proposed_scenarios(case, proposals)
    assert case.scenarios == []
    assert case.case_hash == original_hash
    assert len(updated.scenarios) == 4
    assert all(item.status == "proposed" for item in updated.scenarios)


def test_stale_proposals_are_rejected():
    case = _case()
    proposals = propose_scenarios(case)
    changed = case.model_copy(update={"monthly_cost_assumptions": {"x": 1}})
    with pytest.raises(ValueError, match="different case snapshot"):
        attach_proposed_scenarios(changed, proposals)


def test_fx_candidate_disclaims_executable_kb_quote():
    candidate = next(
        item
        for item in propose_scenarios(_case()).candidates
        if item.scenario_type == "fx_shock"
    )
    assert any("실제 KB 실행 가능 견적이 아닙니다" in text for text in candidate.limitations)
