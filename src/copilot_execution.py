"""Governed routing from approved Copilot scenarios to deterministic tools.

This module is the execution boundary between scenario intelligence and the existing
financial engine. It never approves a scenario implicitly and never recalculates a
financial result outside ``ReadOnlyAdvisorTools``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .advisor_models import CalculationResult
from .advisor_tools import ReadOnlyAdvisorTools
from .copilot_case import CaseScenario, UnifiedCopilotCase
from .copilot_scenarios import (
    ScenarioCandidate,
    ScenarioExecutionRequest,
    build_execution_request,
)

ExecutionStatus = Literal["executed", "unsupported"]


class ScenarioExecutionOutcome(BaseModel):
    scenario_id: str
    status: ExecutionStatus
    execution_tool: str
    calculation_ids: list[str] = Field(default_factory=list)
    case_before_hash: str
    case_after_hash: str
    limitations: list[str] = Field(default_factory=list)


def _replace_scenario(
    case: UnifiedCopilotCase,
    candidate: ScenarioCandidate,
    calculation_ids: list[str],
) -> UnifiedCopilotCase:
    scenarios = {item.scenario_id: item for item in case.scenarios}
    scenarios[candidate.scenario_id] = CaseScenario(
        scenario_id=candidate.scenario_id,
        name=candidate.name,
        rationale=candidate.rationale,
        status="executed",
        parameter_changes=candidate.parameter_changes,
        parameter_sources=candidate.parameter_sources,
        required_inputs=candidate.required_inputs,
        missing_inputs=[],
        calculation_ids=calculation_ids,
        limitations=candidate.limitations,
    )
    return case.model_copy(update={"scenarios": list(scenarios.values())})


def _attach_results(
    case: UnifiedCopilotCase,
    results: list[CalculationResult],
) -> UnifiedCopilotCase:
    updated = case
    for result in results:
        updated = updated.add_calculation(result)
    return updated


class GovernedScenarioExecutor:
    """Route only explicitly approved, supported scenarios to deterministic tools."""

    def __init__(self, tools: ReadOnlyAdvisorTools):
        self._tools = tools

    def execute(
        self,
        case: UnifiedCopilotCase,
        candidate: ScenarioCandidate,
        *,
        human_approved: bool,
    ) -> tuple[UnifiedCopilotCase, ScenarioExecutionOutcome]:
        request = build_execution_request(
            case,
            candidate,
            human_approved=human_approved,
        )
        before_hash = case.case_hash
        results = self._dispatch(request)
        updated = _attach_results(case, results)
        updated = _replace_scenario(
            updated,
            candidate,
            [result.calculation_id for result in results],
        )
        outcome = ScenarioExecutionOutcome(
            scenario_id=candidate.scenario_id,
            status="executed",
            execution_tool=request.execution_tool,
            calculation_ids=[result.calculation_id for result in results],
            case_before_hash=before_hash,
            case_after_hash=updated.case_hash,
            limitations=[
                "Execution used the existing deterministic engine; the Copilot did not perform financial arithmetic.",
                *candidate.limitations,
            ],
        )
        return updated, outcome

    def _dispatch(self, request: ScenarioExecutionRequest) -> list[CalculationResult]:
        if request.execution_tool == "run_cashflow_delay_scenario":
            if len(request.target_transaction_ids) != 1:
                raise ValueError(
                    "Settlement-delay execution requires exactly one target transaction."
                )
            delay_days = int(request.parameter_changes["delay_days"])
            return [
                self._tools.run_cashflow_delay_scenario(
                    request.target_transaction_ids[0],
                    delay_days,
                    view="expected",
                )
            ]

        raise NotImplementedError(
            f"No governed deterministic executor is registered for {request.execution_tool}."
        )
