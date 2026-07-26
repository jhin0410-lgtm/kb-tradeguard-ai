"""Deterministic import-cost stress execution for approved Copilot scenarios.

The module applies a disclosed percentage increase only to explicitly targeted,
human-approved import transactions, then delegates all cash-flow arithmetic to the
existing deterministic cash-flow engine. It does not estimate prices or occurrence
probabilities.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import BaseModel, Field, model_validator

from .advisor_models import CalculationResult
from .advisor_tools import _calculation_result
from .cashflow import calculate_monthly_cashflow
from .copilot_case import UnifiedCopilotCase
from .copilot_scenarios import ScenarioExecutionRequest


class ImportCostExecutionContract(BaseModel):
    target_transaction_ids: list[str] = Field(min_length=1)
    increase_percent: float = Field(ge=0)
    cash_flow_view: str = "expected"

    @model_validator(mode="after")
    def unique_targets(self):
        if len(set(self.target_transaction_ids)) != len(self.target_transaction_ids):
            raise ValueError("Import-cost targets must be unique.")
        return self

    @property
    def increase_multiplier(self) -> float:
        return 1.0 + self.increase_percent / 100.0


def build_import_cost_execution_contract(
    request: ScenarioExecutionRequest,
) -> ImportCostExecutionContract:
    if request.execution_tool != "run_import_cost_scenario":
        raise ValueError("Execution request is not an import-cost scenario.")
    return ImportCostExecutionContract(
        target_transaction_ids=request.target_transaction_ids,
        increase_percent=float(
            request.parameter_changes["import_amount_increase_percent"]
        ),
    )


def _rate_map(case: UnifiedCopilotCase) -> dict[str, float]:
    asset = case.official_fx_reference
    if asset is None or asset.payload is None:
        raise ValueError("Import-cost execution requires an FX reference table.")
    payload: Any = asset.payload
    if isinstance(payload, dict):
        if all(isinstance(value, (int, float)) for value in payload.values()):
            return {str(key).upper(): float(value) for key, value in payload.items()}
        payload = [payload]
    rates: dict[str, float] = {}
    for row in payload:
        currency = str(row.get("currency") or "").upper()
        value = row.get("spot_rate_krw", row.get("rate"))
        if currency and value is not None:
            rates[currency] = float(value)
    if not rates:
        raise ValueError("FX reference payload contains no usable spot rates.")
    return rates


def execute_import_cost_scenario(
    case: UnifiedCopilotCase,
    request: ScenarioExecutionRequest,
) -> CalculationResult:
    """Run baseline and stressed cash flow through the deterministic engine."""

    contract = build_import_cost_execution_contract(request)
    transactions = pd.DataFrame(case.approved_transactions)
    if transactions.empty:
        raise ValueError("Import-cost execution requires approved transactions.")

    target_mask = transactions["transaction_id"].astype(str).isin(
        contract.target_transaction_ids
    )
    found = set(transactions.loc[target_mask, "transaction_id"].astype(str))
    missing = sorted(set(contract.target_transaction_ids) - found)
    if missing:
        raise ValueError("Import-cost target transactions were not found: " + ", ".join(missing))
    if (transactions.loc[target_mask, "transaction_type"] != "import").any():
        raise ValueError("Import-cost stress may target only approved import transactions.")

    assumptions = case.monthly_cost_assumptions
    if "monthly_fixed_cost_krw" not in assumptions or "current_cash_krw" not in assumptions:
        raise ValueError(
            "Import-cost execution requires monthly_fixed_cost_krw and current_cash_krw."
        )

    rates = _rate_map(case)
    baseline = calculate_monthly_cashflow(
        transactions,
        rates,
        float(assumptions["monthly_fixed_cost_krw"]),
        float(assumptions["current_cash_krw"]),
        cash_flow_view=contract.cash_flow_view,
    )
    stressed_transactions = transactions.copy(deep=True)
    stressed_transactions.loc[target_mask, "amount_fc"] = (
        stressed_transactions.loc[target_mask, "amount_fc"].astype(float)
        * contract.increase_multiplier
    )
    stressed = calculate_monthly_cashflow(
        stressed_transactions,
        rates,
        float(assumptions["monthly_fixed_cost_krw"]),
        float(assumptions["current_cash_krw"]),
        cash_flow_view=contract.cash_flow_view,
    )

    baseline_by_month = baseline.set_index("year_month")
    stressed_by_month = stressed.set_index("year_month")
    changed_months = []
    for month in sorted(set(baseline_by_month.index) | set(stressed_by_month.index)):
        baseline_outflow = float(
            baseline_by_month.loc[month, "import_outflows_krw"]
            if month in baseline_by_month.index
            else 0.0
        )
        stressed_outflow = float(
            stressed_by_month.loc[month, "import_outflows_krw"]
            if month in stressed_by_month.index
            else 0.0
        )
        if baseline_outflow != stressed_outflow:
            changed_months.append(
                {
                    "year_month": month,
                    "baseline_import_outflows_krw": baseline_outflow,
                    "stressed_import_outflows_krw": stressed_outflow,
                    "incremental_import_outflow_krw": stressed_outflow - baseline_outflow,
                }
            )

    return _calculation_result(
        "Import payment amount increase scenario",
        {
            "target_transaction_ids": contract.target_transaction_ids,
            "import_amount_increase_percent": contract.increase_percent,
            "cash_flow_view": contract.cash_flow_view,
            "spot_rates": rates,
        },
        {
            "baseline": baseline,
            "stressed": stressed,
            "changed_months": changed_months,
            "baseline_max_shortfall_krw": float(baseline["cash_shortfall_krw"].max()),
            "stressed_max_shortfall_krw": float(stressed["cash_shortfall_krw"].max()),
        },
        "KRW",
        (
            case.identity.analysis_as_of_date.isoformat()
            if case.identity.analysis_as_of_date
            else None
        ),
        "Approved case transactions, disclosed FX reference, and deterministic cash-flow engine",
        [
            "The percentage increase is a disclosed stress assumption, not a forecast.",
            "Only targeted import amounts are changed; dates, currencies, and probabilities remain unchanged.",
            "Reference FX inputs are not executable KB quotes.",
        ],
    )
