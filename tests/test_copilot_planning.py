from src.copilot_planning import (
    CaseCapabilities,
    build_copilot_analysis_plan,
    classify_plan_objective,
)


def _complete_capabilities() -> CaseCapabilities:
    return CaseCapabilities(
        approved_transactions=True,
        document_evidence=True,
        foreign_cash_positions=True,
        monthly_cost_assumptions=True,
        official_fx_reference=True,
        financial_context=True,
        policy_corpus=True,
    )


def test_integrated_review_builds_ordered_read_only_plan():
    plan = build_copilot_analysis_plan(
        "향후 90일 동안 주요 무역금융 위험을 종합 분석해줘",
        _complete_capabilities(),
    )

    assert plan.objective == "integrated_trade_risk_review"
    assert plan.clarification_required is False
    assert plan.can_execute_partial_plan is True
    assert plan.executable_tools == [
        "get_document_readiness",
        "get_portfolio_summary",
        "get_exposure_by_currency",
        "get_maturity_mismatch_summary",
        "get_cashflow_view",
        "run_cashflow_delay_scenario",
        "compare_hedge_ratios",
        "build_bank_consultation_brief",
    ]
    assert [step.sequence for step in plan.steps] == list(range(1, len(plan.steps) + 1))
    assert "read-only" in plan.authority_boundary


def test_missing_inputs_block_only_dependent_steps():
    plan = build_copilot_analysis_plan(
        "수금이 늦어질 때 유동성 위험을 분석해줘",
        CaseCapabilities(
            approved_transactions=True,
            document_evidence=True,
            monthly_cost_assumptions=False,
            official_fx_reference=True,
            financial_context=False,
            policy_corpus=True,
        ),
    )

    status = {step.tool_name: step.status for step in plan.steps}
    assert plan.objective == "liquidity_stress_review"
    assert status["get_portfolio_summary"] == "ready"
    assert status["get_maturity_mismatch_summary"] == "ready"
    assert status["get_cashflow_view"] == "blocked"
    assert status["run_cashflow_delay_scenario"] == "blocked"
    assert status["get_financial_context"] == "blocked"
    assert "monthly cost assumptions" in plan.missing_inputs
    assert plan.can_execute_partial_plan is True


def test_fx_review_requires_disclosed_fx_reference_for_hedge_comparison():
    plan = build_copilot_analysis_plan(
        "USD 환노출과 헤지 시나리오를 검토해줘",
        CaseCapabilities(
            approved_transactions=True,
            official_fx_reference=False,
            policy_corpus=True,
        ),
    )

    hedge = next(step for step in plan.steps if step.tool_name == "compare_hedge_ratios")
    assert plan.objective == "fx_and_hedge_review"
    assert hedge.status == "blocked"
    assert hedge.missing_inputs == ["official or disclosed FX reference"]
    assert any("not executable KB quotes" in item for item in hedge.limitations)


def test_document_request_uses_narrow_evidence_first_plan():
    plan = build_copilot_analysis_plan(
        "업로드 문서의 누락과 불일치를 확인해줘",
        _complete_capabilities(),
    )

    assert plan.objective == "document_readiness_review"
    assert [step.tool_name for step in plan.steps] == [
        "get_document_readiness",
        "get_portfolio_summary",
        "build_bank_consultation_brief",
    ]


def test_sensitive_request_is_not_planned():
    plan = build_copilot_analysis_plan(
        "이 회사 대출 승인을 확정해줘",
        _complete_capabilities(),
    )

    assert classify_plan_objective("공식 신용등급을 매겨줘") == (
        "unsupported_or_sensitive_request"
    )
    assert plan.objective == "unsupported_or_sensitive_request"
    assert plan.steps == []
    assert plan.can_execute_partial_plan is False
