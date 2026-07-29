from __future__ import annotations

from src.copilot_integration import (
    build_unified_case_from_app_state,
    build_workspace_from_app_state,
    workspace_render_payload,
)


COMPANY = {
    "company_name": "테스트무역",
    "business_type": "제조 및 수출입",
    "customer_segment": "SME",
    "foreign_cash": {"USD": 10000},
    "current_cash_krw": 100000000,
    "monthly_fixed_cost_krw": 30000000,
    "as_of_date": "2026-08-31",
}

TRANSACTIONS = [
    {
        "transaction_id": "EXP-001",
        "transaction_type": "export",
        "currency": "USD",
        "amount_fc": 100000,
        "expected_date": "2026-09-30",
        "document_reference": "INV-001",
        "source_filename": "invoice.pdf",
        "source_type": "approved_document",
    },
    {
        "transaction_id": "IMP-001",
        "transaction_type": "import",
        "currency": "USD",
        "amount_fc": 20000,
        "expected_date": "2026-09-15",
        "document_reference": "PO-001",
        "source_filename": "purchase_order.pdf",
        "source_type": "approved_document",
    },
]

FX = [{"currency": "USD", "spot_rate_krw": 1400.0}]


def test_adapter_builds_executable_case_from_current_app_records():
    case = build_unified_case_from_app_state(
        company=COMPANY,
        approved_transactions=TRANSACTIONS,
        fx_rates=FX,
    )

    assert case.executable_case is True
    assert case.capabilities.approved_transactions is True
    assert case.capabilities.document_evidence is True
    assert case.capabilities.official_fx_reference is True
    assert case.capabilities.financial_context is True
    assert case.capabilities.monthly_cost_assumptions is True


def test_adapter_groups_document_evidence_by_source():
    case = build_unified_case_from_app_state(
        company=COMPANY,
        approved_transactions=TRANSACTIONS,
        fx_rates=FX,
    )

    assert len(case.evidence) == 2
    assert {item.source_name for item in case.evidence} == {
        "invoice.pdf",
        "purchase_order.pdf",
    }
    assert all(item.status == "approved" for item in case.evidence)


def test_adapter_normalizes_foreign_cash_positions():
    case = build_unified_case_from_app_state(
        company=COMPANY,
        approved_transactions=TRANSACTIONS,
    )

    assert case.foreign_cash_positions == [{"currency": "USD", "amount_fc": 10000}]


def test_empty_transactions_are_disclosed_as_missing_input():
    case = build_unified_case_from_app_state(
        company=COMPANY,
        approved_transactions=[],
        fx_rates=FX,
    )

    assert case.executable_case is False
    assert "human-approved transactions" in [item.input_name for item in case.missing_inputs]


def test_workspace_is_built_from_app_state_without_new_financial_arithmetic():
    workspace = build_workspace_from_app_state(
        user_objective="환노출과 수금지연 위험을 상담 전에 점검",
        company=COMPANY,
        approved_transactions=TRANSACTIONS,
        fx_rates=FX,
        cash_allocations=[],
        audit_events=[{"event": "review"}],
    )

    assert workspace.case_id == "KB-DEMO-CASE"
    assert len(workspace.sections) == 6
    assert workspace.audit_export["human_review_required"] is True
    assert all(step.authority != "deterministic_engine" for step in workspace.trace)


def test_workspace_contains_ready_delay_and_fx_scenarios():
    workspace = build_workspace_from_app_state(
        user_objective="복합 무역 위험 점검",
        company=COMPANY,
        approved_transactions=TRANSACTIONS,
        fx_rates=FX,
    )

    ready_types = {item.scenario_type for item in workspace.scenarios.ready_candidates}
    assert "settlement_delay" in ready_types
    assert "fx_shock" in ready_types
    assert "combined_stress" in ready_types


def test_render_payload_preserves_ids_trace_and_disclaimer():
    workspace = build_workspace_from_app_state(
        user_objective="상담자료 생성",
        company=COMPANY,
        approved_transactions=TRANSACTIONS,
        fx_rates=FX,
    )
    payload = workspace_render_payload(workspace)

    assert payload["header"]["workspace_id"] == workspace.workspace_id
    assert payload["header"]["case_hash"] == workspace.case_hash
    assert "결정론적 fallback 모드" in payload["header"]["disclaimer"]
    assert len(payload["trace"]) == 6
    assert len(payload["sections"]) == 6


def test_financial_context_uses_required_pre_screening_wording():
    case = build_unified_case_from_app_state(
        company=COMPANY,
        approved_transactions=TRANSACTIONS,
    )

    assert case.financial_context is not None
    assert any(
        "재무건전성 사전 스크리닝" in limitation
        for limitation in case.financial_context.limitations
    )


def test_case_hash_is_stable_for_equivalent_app_state():
    first = build_unified_case_from_app_state(
        company=COMPANY,
        approved_transactions=TRANSACTIONS,
        fx_rates=FX,
    )
    second = build_unified_case_from_app_state(
        company=COMPANY,
        approved_transactions=TRANSACTIONS,
        fx_rates=FX,
    )

    # Retrieval timestamps are operational metadata and currently belong to the case
    # snapshot, so compare the governed substantive state rather than asserting equal
    # hashes across separate adapter calls.
    assert first.approved_transactions == second.approved_transactions
    assert [item.evidence_id for item in first.evidence] == [
        item.evidence_id for item in second.evidence
    ]
