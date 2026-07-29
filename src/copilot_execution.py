"""Governed routing from approved Copilot scenarios to deterministic tools.

This module is the execution boundary between scenario intelligence and the existing
financial engine. It never approves a scenario implicitly and never recalculates a
financial result outside governed deterministic executors.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

from .advisor_models import CalculationResult
from .advisor_tools import ReadOnlyAdvisorTools
from .copilot_case import CaseScenario, UnifiedCopilotCase
from .copilot_fx_execution import build_fx_shock_execution_contract
from .copilot_import_cost_execution import execute_import_cost_scenario
from .copilot_scenarios import (
    ScenarioCandidate,
    ScenarioExecutionRequest,
    build_execution_request,
)
from .validators import validate_fx_rates, validate_transactions

ExecutionStatus = Literal["executed", "unsupported"]

_DELAY_TRANSACTION_COLUMNS = [
    "transaction_id",
    "transaction_type",
    "currency",
    "amount_fc",
    "probability",
    "status",
    "expected_date",
]
_FX_TRANSACTION_COLUMNS = [
    "transaction_id",
    "transaction_type",
    "currency",
    "amount_fc",
    "probability",
    "status",
]
_DELAY_FX_COLUMNS = ["currency", "spot_rate_krw"]
_HEDGE_FX_COLUMNS = [
    "currency",
    "spot_rate_krw",
    "krw_interest_rate",
    "foreign_interest_rate",
]


class ScenarioExecutionOutcome(BaseModel):
    scenario_id: str
    status: ExecutionStatus
    execution_tool: str
    calculation_ids: list[str] = Field(default_factory=list)
    case_before_hash: str
    case_after_hash: str
    limitations: list[str] = Field(default_factory=list)


def _normalized_scalar(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return float(value)
    return value


def _normalized_records(
    frame: pd.DataFrame,
    columns: list[str],
    *,
    sort_by: list[str],
) -> list[dict[str, Any]]:
    normalized = frame.copy(deep=True)
    for column in columns:
        if column not in normalized.columns:
            normalized[column] = None
    normalized = normalized.loc[:, columns].sort_values(sort_by).reset_index(drop=True)
    return [
        {key: _normalized_scalar(value) for key, value in row.items()}
        for row in normalized.to_dict("records")
    ]


def _normalized_company(
    company: dict[str, Any],
    *,
    execution_tool: str,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "as_of_date": (
            str(company.get("as_of_date"))[:10]
            if company.get("as_of_date") not in (None, "")
            else None
        )
    }
    if execution_tool == "compare_hedge_ratios":
        foreign_cash = company.get("foreign_cash") or {}
        if not isinstance(foreign_cash, dict):
            raise ValueError(
                "Advisor-tool foreign_cash must be a currency-to-amount mapping."
            )
        normalized["foreign_cash"] = {
            str(currency).strip().upper(): float(amount)
            for currency, amount in sorted(foreign_cash.items())
        }
    elif execution_tool == "run_cashflow_delay_scenario":
        normalized["monthly_fixed_cost_krw"] = (
            float(company["monthly_fixed_cost_krw"])
            if company.get("monthly_fixed_cost_krw") is not None
            else None
        )
        normalized["current_cash_krw"] = (
            float(company["current_cash_krw"])
            if company.get("current_cash_krw") is not None
            else None
        )
    else:
        raise ValueError(
            f"No advisor-tool snapshot contract is defined for {execution_tool}."
        )
    return normalized


def _snapshot_columns(execution_tool: str) -> tuple[list[str], list[str]]:
    if execution_tool == "run_cashflow_delay_scenario":
        return _DELAY_TRANSACTION_COLUMNS, _DELAY_FX_COLUMNS
    if execution_tool == "compare_hedge_ratios":
        return _FX_TRANSACTION_COLUMNS, _HEDGE_FX_COLUMNS
    raise ValueError(f"No advisor-tool snapshot contract is defined for {execution_tool}.")


def _financial_input_fingerprint(
    transactions: pd.DataFrame,
    fx_rates: pd.DataFrame,
    company: dict[str, Any],
    *,
    execution_tool: str,
) -> str:
    validated_fx = validate_fx_rates(fx_rates.copy(deep=True))
    validated_transactions = validate_transactions(
        transactions.copy(deep=True), validated_fx
    )
    transaction_columns, fx_columns = _snapshot_columns(execution_tool)
    payload = {
        "execution_tool": execution_tool,
        "transactions": _normalized_records(
            validated_transactions,
            transaction_columns,
            sort_by=["transaction_id"],
        ),
        "fx_rates": _normalized_records(
            validated_fx,
            fx_columns,
            sort_by=["currency"],
        ),
        "company": _normalized_company(company, execution_tool=execution_tool),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _case_financial_inputs(
    case: UnifiedCopilotCase,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if case.official_fx_reference is None or case.official_fx_reference.payload is None:
        raise ValueError(
            "Execution case must include the FX-reference payload used by advisor tools."
        )
    fx_payload = case.official_fx_reference.payload
    if isinstance(fx_payload, dict):
        fx_records = [fx_payload]
    else:
        fx_records = fx_payload

    foreign_cash: dict[str, float] = {}
    for row in case.foreign_cash_positions:
        currency = str(row.get("currency") or "").strip().upper()
        if not currency:
            raise ValueError("Execution case contains a foreign-cash row without currency.")
        if currency in foreign_cash:
            raise ValueError(
                f"Execution case contains duplicate foreign-cash currency: {currency}"
            )
        amount = row.get("amount_fc")
        if amount is None:
            raise ValueError(
                f"Execution case foreign-cash amount is missing for currency: {currency}"
            )
        foreign_cash[currency] = float(amount)

    company = {
        "as_of_date": (
            case.identity.analysis_as_of_date.isoformat()
            if case.identity.analysis_as_of_date
            else None
        ),
        "foreign_cash": foreign_cash,
        "monthly_fixed_cost_krw": case.monthly_cost_assumptions.get(
            "monthly_fixed_cost_krw"
        ),
        "current_cash_krw": case.monthly_cost_assumptions.get("current_cash_krw"),
    }
    return (
        pd.DataFrame(case.approved_transactions),
        pd.DataFrame(fx_records),
        company,
    )


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
        results = self._dispatch(case, request)
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
                "Execution used governed deterministic engines; the Copilot did not perform financial arithmetic.",
                *candidate.limitations,
            ],
        )
        return updated, outcome

    def _assert_tools_match_case(
        self,
        case: UnifiedCopilotCase,
        execution_tool: str,
    ) -> None:
        case_transactions, case_fx_rates, case_company = _case_financial_inputs(case)
        case_fingerprint = _financial_input_fingerprint(
            case_transactions,
            case_fx_rates,
            case_company,
            execution_tool=execution_tool,
        )
        tool_fingerprint = _financial_input_fingerprint(
            self._tools._transactions,
            self._tools._fx_rates,
            self._tools._company,
            execution_tool=execution_tool,
        )
        if case_fingerprint != tool_fingerprint:
            raise ValueError(
                "Advisor-tool input snapshot does not match the execution case; "
                "rebuild ReadOnlyAdvisorTools from the current case before execution."
            )

    def _dispatch(
        self,
        case: UnifiedCopilotCase,
        request: ScenarioExecutionRequest,
    ) -> list[CalculationResult]:
        if request.execution_tool in {
            "run_cashflow_delay_scenario",
            "compare_hedge_ratios",
        }:
            self._assert_tools_match_case(case, request.execution_tool)

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

        if request.execution_tool == "compare_hedge_ratios":
            contract = build_fx_shock_execution_contract(request)
            active = set(self._tools.active_transaction_currencies)
            unsupported = sorted(set(contract.currencies) - active)
            if unsupported:
                raise ValueError(
                    "FX-shock request contains currencies absent from the approved portfolio: "
                    + ", ".join(unsupported)
                )
            return [
                self._tools.compare_hedge_ratios(
                    currency=currency,
                    basis=contract.analysis_basis,
                    scenarios=contract.scenario_percentages,
                    hedge_ratios=contract.hedge_ratios,
                    tenor_months=contract.tenor_months,
                    spread=contract.spread,
                )
                for currency in contract.currencies
            ]

        if request.execution_tool == "run_import_cost_scenario":
            return [execute_import_cost_scenario(case, request)]

        raise NotImplementedError(
            f"No governed deterministic executor is registered for {request.execution_tool}."
        )
