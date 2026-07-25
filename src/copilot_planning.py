"""Grounded multi-step planning for the trade-finance copilot.

The planner never performs financial arithmetic and never grants the language model
write access to the portfolio.  It converts a user objective and declared case
capabilities into a reviewable sequence of read-only deterministic tool calls.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field


PlanObjective = Literal[
    "integrated_trade_risk_review",
    "liquidity_stress_review",
    "fx_and_hedge_review",
    "document_readiness_review",
    "bank_consultation_preparation",
    "unsupported_or_sensitive_request",
]

PlanStepStatus = Literal["ready", "blocked", "optional"]


class CaseCapabilities(BaseModel):
    """Facts about data and deterministic engines available for one case."""

    approved_transactions: bool = False
    document_evidence: bool = False
    foreign_cash_positions: bool = False
    monthly_cost_assumptions: bool = False
    official_fx_reference: bool = False
    financial_context: bool = False
    policy_corpus: bool = False


class AnalysisPlanStep(BaseModel):
    sequence: int = Field(ge=1)
    tool_name: str
    purpose: str
    status: PlanStepStatus
    required_inputs: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    depends_on: list[int] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CopilotAnalysisPlan(BaseModel):
    objective: PlanObjective
    user_request: str
    steps: list[AnalysisPlanStep]
    missing_inputs: list[str] = Field(default_factory=list)
    clarification_required: bool = False
    can_execute_partial_plan: bool = True
    planning_basis: str = "Deterministic capability-aware planner"
    authority_boundary: str = (
        "The planner selects read-only tools only. Deterministic engines remain "
        "authoritative for financial calculations, and all outputs require human review."
    )

    @property
    def executable_tools(self) -> list[str]:
        return [step.tool_name for step in self.steps if step.status == "ready"]


_SENSITIVE = re.compile(
    r"(대출\s*(?:승인|확정)|공식\s*신용등급|적합한\s*상품\s*확정|"
    r"guaranteed\s*approval|official\s*credit\s*rating|evade\s*sanctions)",
    re.IGNORECASE,
)


def classify_plan_objective(request: str) -> PlanObjective:
    """Classify broad workflow intent without calculating or inventing values."""

    text = request.lower()
    if _SENSITIVE.search(request):
        return "unsupported_or_sensitive_request"
    if re.search(r"(문서|증빙|누락|불일치|추출|document|evidence|readiness)", text):
        return "document_readiness_review"
    if re.search(r"(상담|준비자료|필요\s*서류|consultation|brief)", text):
        return "bank_consultation_preparation"
    if re.search(r"(현금|유동성|수금|결제\s*지연|cash.?flow|liquidity|delay)", text):
        return "liquidity_stress_review"
    if re.search(r"(환노출|환율|헤지|선물환|fx|hedge|forward)", text):
        return "fx_and_hedge_review"
    return "integrated_trade_risk_review"


def build_copilot_analysis_plan(
    request: str,
    capabilities: CaseCapabilities,
) -> CopilotAnalysisPlan:
    """Build a reviewable read-only plan from objective and case readiness.

    Missing data blocks only the dependent step.  Independent steps remain ready so
    the copilot can provide a partial, explicitly limited review instead of silently
    fabricating inputs.
    """

    objective = classify_plan_objective(request)
    if objective == "unsupported_or_sensitive_request":
        return CopilotAnalysisPlan(
            objective=objective,
            user_request=request,
            steps=[],
            missing_inputs=[],
            clarification_required=False,
            can_execute_partial_plan=False,
        )

    steps: list[AnalysisPlanStep] = []

    def add_step(
        tool_name: str,
        purpose: str,
        *,
        required: list[tuple[str, bool]] | None = None,
        depends_on: list[int] | None = None,
        optional: bool = False,
        limitations: list[str] | None = None,
    ) -> int:
        missing = [name for name, available in (required or []) if not available]
        status: PlanStepStatus
        if missing:
            status = "blocked"
        elif optional:
            status = "optional"
        else:
            status = "ready"
        sequence = len(steps) + 1
        steps.append(
            AnalysisPlanStep(
                sequence=sequence,
                tool_name=tool_name,
                purpose=purpose,
                status=status,
                required_inputs=[name for name, _ in (required or [])],
                missing_inputs=missing,
                depends_on=depends_on or [],
                limitations=limitations or [],
            )
        )
        return sequence

    document_step = add_step(
        "get_document_readiness",
        "Check evidence coverage, validation state, duplicates, and unresolved document conflicts.",
        required=[("document evidence", capabilities.document_evidence)],
    )

    transaction_step = add_step(
        "get_portfolio_summary",
        "Establish the approved transaction population and analysis horizon.",
        required=[("approved transactions", capabilities.approved_transactions)],
    )

    exposure_step = add_step(
        "get_exposure_by_currency",
        "Calculate transaction exposure by currency using the authoritative deterministic engine.",
        required=[("approved transactions", capabilities.approved_transactions)],
        depends_on=[transaction_step],
    )

    maturity_step = add_step(
        "get_maturity_mismatch_summary",
        "Distinguish gross same-currency offset from maturity-matched natural offset.",
        required=[("approved transactions", capabilities.approved_transactions)],
        depends_on=[transaction_step],
    )

    cashflow_step = add_step(
        "get_cashflow_view",
        "Project settlement-timed cash flow and identify shortfall periods.",
        required=[
            ("approved transactions", capabilities.approved_transactions),
            ("monthly cost assumptions", capabilities.monthly_cost_assumptions),
        ],
        depends_on=[transaction_step],
    )

    delay_step = add_step(
        "run_cashflow_delay_scenario",
        "Stress material receivables for settlement delay and compare shortfall timing.",
        required=[
            ("approved transactions", capabilities.approved_transactions),
            ("monthly cost assumptions", capabilities.monthly_cost_assumptions),
        ],
        depends_on=[cashflow_step],
    )

    hedge_step = add_step(
        "compare_hedge_ratios",
        "Compare deterministic downside protection and opportunity cost scenarios.",
        required=[
            ("approved transactions", capabilities.approved_transactions),
            ("official or disclosed FX reference", capabilities.official_fx_reference),
        ],
        depends_on=[exposure_step],
        limitations=[
            "Configured forward assumptions are theoretical and are not executable KB quotes."
        ],
    )

    financial_step = add_step(
        "get_financial_context",
        "Add non-rating financial capacity context without issuing an official credit assessment.",
        required=[("financial context", capabilities.financial_context)],
        optional=True,
        limitations=["This is 재무건전성 사전 스크리닝, not an official credit rating."],
    )

    consultation_dependencies = [document_step, maturity_step, cashflow_step, hedge_step]
    add_step(
        "build_bank_consultation_brief",
        "Synthesize findings, evidence gaps, customer questions, and review priorities with citations.",
        required=[("policy corpus", capabilities.policy_corpus)],
        depends_on=consultation_dependencies,
    )

    if objective == "document_readiness_review":
        preferred = {"get_document_readiness", "get_portfolio_summary", "build_bank_consultation_brief"}
    elif objective == "liquidity_stress_review":
        preferred = {
            "get_portfolio_summary",
            "get_maturity_mismatch_summary",
            "get_cashflow_view",
            "run_cashflow_delay_scenario",
            "get_financial_context",
            "build_bank_consultation_brief",
        }
    elif objective == "fx_and_hedge_review":
        preferred = {
            "get_portfolio_summary",
            "get_exposure_by_currency",
            "get_maturity_mismatch_summary",
            "compare_hedge_ratios",
            "build_bank_consultation_brief",
        }
    elif objective == "bank_consultation_preparation":
        preferred = {step.tool_name for step in steps}
    else:
        preferred = {step.tool_name for step in steps}

    filtered_steps = [step for step in steps if step.tool_name in preferred]
    remap = {old.sequence: index + 1 for index, old in enumerate(filtered_steps)}
    normalized_steps = []
    for index, step in enumerate(filtered_steps, start=1):
        normalized_steps.append(
            step.model_copy(
                update={
                    "sequence": index,
                    "depends_on": [remap[item] for item in step.depends_on if item in remap],
                }
            )
        )

    all_missing = sorted(
        {item for step in normalized_steps for item in step.missing_inputs}
    )
    return CopilotAnalysisPlan(
        objective=objective,
        user_request=request,
        steps=normalized_steps,
        missing_inputs=all_missing,
        clarification_required=bool(all_missing),
        can_execute_partial_plan=any(step.status == "ready" for step in normalized_steps),
    )
