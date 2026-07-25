"""Controlled read-only tools wrapping the deterministic financial engine."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from .advisor_models import CalculationResult
from .cash_allocation import allocate_foreign_cash
from .cashflow import calculate_monthly_cashflow
from .exposure import calculate_exposure
from .forward_rates import (
    build_settlement_forward_table,
    calculate_theoretical_forward_rate,
)
from .hedging import calculate_natural_hedge, compare_hedge_ratios
from .policy_retrieval import BundledPolicyRetriever, PolicyExcerpt
from .portfolio_hedging import (
    calculate_maturity_bucket_portfolio_hedge,
    calculate_transaction_level_portfolio_hedge,
)
from .validators import validate_fx_rates, validate_transactions

CALCULATION_ENGINE_VERSION = "kb-tradeguard-deterministic-engine/1.0"


def _serializable(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return _serializable(value.to_dict("records"))
    if isinstance(value, pd.Series):
        return _serializable(value.to_dict())
    if isinstance(value, (pd.Timestamp, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def _calculation_result(
    name: str,
    assumptions: dict[str, Any],
    result: Any,
    unit: str,
    as_of_date: str | None,
    source: str,
    limitations: list[str],
) -> CalculationResult:
    serialized_assumptions = _serializable(assumptions)
    normalized_input = {
        "assumptions": serialized_assumptions,
        "as_of_date": as_of_date,
        "source": source,
    }
    normalized_input_hash = hashlib.sha256(
        json.dumps(
            normalized_input, sort_keys=True, ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    normalized = {
        "name": name,
        "assumptions": serialized_assumptions,
        "result": _serializable(result),
        "as_of_date": as_of_date,
        "source": source,
    }
    digest = hashlib.sha256(
        json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12].upper()
    prefix = "".join(part[0] for part in name.upper().split() if part)[:5]
    return CalculationResult(
        calculation_name=name,
        input_assumptions=normalized["assumptions"],
        result=normalized["result"],
        unit=unit,
        as_of_date=as_of_date,
        data_source=source,
        limitations=limitations,
        calculation_id=f"CALC-{prefix}-{digest}",
        calculation_engine_version=CALCULATION_ENGINE_VERSION,
        normalized_input_hash=normalized_input_hash,
        calculation_timestamp=datetime.now(timezone.utc).isoformat(),
        source_data_identifiers=[
            f"data-source:{source}",
            f"as-of:{as_of_date or 'not-applicable'}",
        ],
        selected_analysis_basis=str(
            serialized_assumptions.get(
                "analysis_basis",
                serialized_assumptions.get(
                    "cash_flow_view",
                    serialized_assumptions.get(
                        "view",
                        serialized_assumptions.get(
                            "exposure_measure",
                            serialized_assumptions.get(
                                "amount_basis", "deterministic tool-defined basis"
                            ),
                        ),
                    ),
                ),
            )
        ),
    )


class ReadOnlyAdvisorTools:
    """Immutable-input façade; deliberately exposes no mutation operations."""

    def __init__(
        self,
        transactions: pd.DataFrame,
        fx_rates: pd.DataFrame,
        company: dict[str, Any],
        allocations: pd.DataFrame | None = None,
        audit_events: list[dict[str, Any]] | None = None,
        policy_retriever: BundledPolicyRetriever | None = None,
    ):
        self._transactions = validate_transactions(
            transactions.copy(deep=True), fx_rates
        )
        self._fx_rates = validate_fx_rates(fx_rates.copy(deep=True))
        self._company = deepcopy(company)
        self._allocations = (
            allocations.copy(deep=True)
            if allocations is not None
            else pd.DataFrame()
        )
        self._audit_events = deepcopy(audit_events or [])
        self._policy_retriever = policy_retriever
        self._as_of_date = str(company["as_of_date"])
        self._rate_map = dict(
            zip(
                self._fx_rates["currency"],
                self._fx_rates["spot_rate_krw"],
                strict=True,
            )
        )

    @property
    def active_transaction_currencies(self) -> list[str]:
        return sorted(self._transactions["currency"].unique())

    def get_portfolio_summary(self) -> CalculationResult:
        result = {
            "transaction_count": int(len(self._transactions)),
            "currencies": self.active_transaction_currencies,
            "exports": int(
                (self._transactions["transaction_type"] == "export").sum()
            ),
            "imports": int(
                (self._transactions["transaction_type"] == "import").sum()
            ),
        }
        return _calculation_result(
            "Portfolio summary",
            {"status_scope": ["confirmed", "expected"]},
            result,
            "transactions",
            self._as_of_date,
            "Session portfolio",
            ["Counts describe the current in-memory portfolio only."],
        )

    def get_exposure_by_currency(self) -> CalculationResult:
        exposure = calculate_exposure(
            self._transactions, self._company["foreign_cash"], self._fx_rates
        )
        result = {
            "by_currency": exposure.by_currency.to_dict("records"),
            "consolidated_expected_total_economic_position_krw": (
                exposure.consolidated_expected_total_economic_position_krw
            ),
        }
        return _calculation_result(
            "FX exposure by currency",
            {
                "analysis_basis": "Nominal and expected transaction exposure plus separately identified foreign cash",
                "foreign_cash": self._company["foreign_cash"],
            },
            result,
            "foreign currency and KRW",
            self._as_of_date,
            "Session portfolio, company assumptions, bundled or user-edited FX rates",
            [
                "Currencies are converted separately before KRW consolidation.",
                "Foreign cash is a positive economic position and is not subtracted from transaction exposure.",
            ],
        )

    def get_cashflow_view(self, view: str) -> CalculationResult:
        frame = calculate_monthly_cashflow(
            self._transactions,
            self._rate_map,
            self._company["monthly_fixed_cost_krw"],
            self._company["current_cash_krw"],
            cash_flow_view=view,
        )
        return _calculation_result(
            "Monthly cash-flow view",
            {
                "view": view,
                "beginning_cash_krw": self._company["current_cash_krw"],
                "monthly_fixed_cost_krw": self._company["monthly_fixed_cost_krw"],
                "spot_rates": self._rate_map,
            },
            frame,
            "KRW",
            self._as_of_date,
            "Session portfolio and configured FX assumptions",
            [
                "Monthly aggregation omits intramonth timing.",
                "Expected view is probability-qualified, not an unqualified forecast.",
            ],
        )

    def run_cashflow_delay_scenario(
        self, transaction_id: str, delay_days: int, view: str = "expected"
    ) -> CalculationResult:
        baseline = calculate_monthly_cashflow(
            self._transactions,
            self._rate_map,
            self._company["monthly_fixed_cost_krw"],
            self._company["current_cash_krw"],
            cash_flow_view=view,
        )
        delayed = calculate_monthly_cashflow(
            self._transactions,
            self._rate_map,
            self._company["monthly_fixed_cost_krw"],
            self._company["current_cash_krw"],
            delay_transaction_id=transaction_id,
            delay_days=delay_days,
            cash_flow_view=view,
        )
        months = sorted(set(baseline["year_month"]) | set(delayed["year_month"]))
        baseline_map = baseline.set_index("year_month")
        delayed_map = delayed.set_index("year_month")
        changes = []
        for month in months:
            baseline_flow = (
                float(baseline_map.loc[month, "transaction_cash_flow_krw"])
                if month in baseline_map.index
                else 0.0
            )
            delayed_flow = (
                float(delayed_map.loc[month, "transaction_cash_flow_krw"])
                if month in delayed_map.index
                else 0.0
            )
            if baseline_flow != delayed_flow:
                changes.append(
                    {
                        "year_month": month,
                        "baseline_transaction_cash_flow_krw": baseline_flow,
                        "delayed_transaction_cash_flow_krw": delayed_flow,
                    }
                )
        result = {
            "baseline": baseline.to_dict("records"),
            "delayed": delayed.to_dict("records"),
            "changed_months": changes,
            "baseline_max_shortfall_krw": float(
                baseline["cash_shortfall_krw"].max()
            ),
            "delayed_max_shortfall_krw": float(
                delayed["cash_shortfall_krw"].max()
            ),
        }
        return _calculation_result(
            "Cash-flow settlement delay scenario",
            {
                "transaction_id": transaction_id,
                "delay_days": delay_days,
                "cash_flow_view": view,
                "spot_rates": self._rate_map,
            },
            result,
            "KRW",
            self._as_of_date,
            "Session portfolio and configured cash-flow assumptions",
            ["Delay changes settlement timing only; it does not change probability."],
        )

    def get_liquidity_shortfalls(self, view: str = "expected") -> CalculationResult:
        cashflow = self.get_cashflow_view(view)
        rows = [
            row
            for row in cashflow.result
            if float(row["cash_shortfall_krw"]) > 0
        ]
        return _calculation_result(
            "Liquidity shortfalls",
            {"cash_flow_view": view},
            {
                "shortfall_months": rows,
                "maximum_shortfall_krw": max(
                    [float(row["cash_shortfall_krw"]) for row in rows] or [0.0]
                ),
            },
            "KRW",
            self._as_of_date,
            cashflow.data_source,
            cashflow.limitations,
        )

    def get_natural_offset_summary(
        self, matching_window_days: int = 30
    ) -> CalculationResult:
        natural = calculate_natural_hedge(
            self._transactions,
            self._company["foreign_cash"],
            matching_window_days,
        )
        gaps = []
        for currency, subset in self._transactions.groupby("currency"):
            exports = subset[subset["transaction_type"] == "export"]
            imports = subset[subset["transaction_type"] == "import"]
            for export in exports.itertuples(index=False):
                for import_row in imports.itertuples(index=False):
                    gaps.append(
                        {
                            "currency": currency,
                            "export_transaction_id": export.transaction_id,
                            "import_transaction_id": import_row.transaction_id,
                            "timing_gap_days": abs(
                                (
                                    pd.Timestamp(export.expected_date)
                                    - pd.Timestamp(import_row.expected_date)
                                ).days
                            ),
                        }
                    )
        return _calculation_result(
            "Natural offset and maturity matching",
            {
                "matching_window_days": matching_window_days,
                "amount_basis": "nominal transaction amounts",
            },
            {
                "summary": natural.summary.to_dict("records"),
                "eligible_matches": natural.matches.to_dict("records"),
                "all_same_currency_timing_gaps": gaps,
            },
            "foreign currency and days",
            self._as_of_date,
            "Session portfolio expected settlement dates",
            [
                "Gross offset is amount-only and is not a complete liquidity hedge.",
                "Matching uses the deterministic closest-gap ordering rule.",
            ],
        )

    def get_maturity_mismatch_summary(
        self, matching_window_days: int = 30
    ) -> CalculationResult:
        return self.get_natural_offset_summary(matching_window_days)

    def calculate_transaction_forward_rates(
        self, as_of_date: str
    ) -> CalculationResult:
        table = build_settlement_forward_table(
            self._transactions, self._fx_rates, as_of_date
        )
        return _calculation_result(
            "Transaction indicative theoretical forward rates",
            {
                "day_count": "ACT/365",
                "spot_and_interest_rates": self._fx_rates.to_dict("records"),
            },
            table,
            "KRW per foreign-currency unit",
            str(as_of_date),
            "Configured spot and interest-rate assumptions",
            [
                "Rates are indicative theoretical values, not executable quotes or actual KB prices.",
                "Covered-interest-parity simplifications exclude market basis and customer terms.",
            ],
        )

    def compare_hedge_ratios(
        self,
        currency: str,
        basis: str,
        scenarios: list[float],
        hedge_ratios: list[float] | None = None,
        tenor_months: int = 3,
        spread: float = 0.0,
    ) -> CalculationResult:
        exposure = calculate_exposure(
            self._transactions, self._company["foreign_cash"], self._fx_rates
        ).row_for(currency)
        basis_map = {
            "Expected transaction exposure": "expected_transaction_exposure",
            "Nominal transaction exposure": "nominal_transaction_exposure",
            "Expected total economic position": "expected_total_economic_position",
            "Nominal total economic position": "nominal_total_economic_position",
        }
        if basis not in basis_map:
            raise ValueError("Unsupported hedge analysis basis")
        amount = float(exposure[basis_map[basis]])
        rate = self._fx_rates.set_index("currency").loc[currency]
        forward = calculate_theoretical_forward_rate(
            float(rate["spot_rate_krw"]),
            float(rate["krw_interest_rate"]),
            float(rate["foreign_interest_rate"]),
            tenor_months,
        )
        exposure_type = "export" if amount >= 0 else "import"
        comparison = compare_hedge_ratios(
            currency,
            abs(amount),
            exposure_type,
            float(rate["spot_rate_krw"]),
            forward,
            spread,
            hedge_ratios or [0.0, 0.3, 0.5, 0.7, 1.0],
            scenarios,
        )
        return _calculation_result(
            "Hedge ratio comparison",
            {
                "currency": currency,
                "analysis_basis": basis,
                "exposure_amount_fc": amount,
                "tenor_months": tenor_months,
                "theoretical_forward_rate": forward,
                "spread": spread,
                "scenarios": scenarios,
            },
            comparison,
            "KRW",
            self._as_of_date,
            "Deterministic exposure and covered-interest-parity engines",
            [
                "Theoretical forward is not an executable quote or actual KB price.",
                "Transaction costs are excluded unless represented by the entered spread.",
            ],
        )

    def calculate_portfolio_hedge_plan(
        self,
        mode: str,
        as_of_date: str,
        hedge_ratios: dict[str, float] | float,
        scenarios: list[float],
        exposure_measure: str = "expected",
    ) -> CalculationResult:
        if mode == "transaction-level":
            plan = calculate_transaction_level_portfolio_hedge(
                self._transactions,
                self._fx_rates,
                as_of_date,
                hedge_ratios,
                scenario_percentages=scenarios,
                exposure_measure=exposure_measure,
            )
        elif mode == "maturity-bucket":
            plan = calculate_maturity_bucket_portfolio_hedge(
                self._transactions,
                self._fx_rates,
                as_of_date,
                hedge_ratios,
                scenario_percentages=scenarios,
                exposure_measure=exposure_measure,
            )
        else:
            raise ValueError("mode must be transaction-level or maturity-bucket")
        return _calculation_result(
            "Portfolio maturity-aware hedge plan",
            {
                "mode": mode,
                "hedge_ratios": hedge_ratios,
                "scenarios": scenarios,
                "exposure_measure": exposure_measure,
            },
            {
                "transaction_results": plan.transaction_results.to_dict("records"),
                "currency_totals": plan.currency_scenario_totals.to_dict("records"),
                "portfolio_totals": plan.portfolio_scenario_totals.to_dict("records"),
                "bucket_summary": (
                    plan.bucket_summary.to_dict("records")
                    if plan.bucket_summary is not None
                    else None
                ),
            },
            "KRW",
            str(as_of_date),
            "Session portfolio and deterministic maturity-aware hedge engine",
            ["Portfolio output is a simulation and not an executable hedge plan."],
        )

    def get_cash_allocation_summary(self) -> CalculationResult:
        allocation = allocate_foreign_cash(
            self._transactions, self._company["foreign_cash"], self._allocations
        )
        return _calculation_result(
            "Foreign-cash allocation and import funding gaps",
            {"allocation_schedule": self._allocations.to_dict("records")},
            {
                "allocation_table": allocation.allocation_table.to_dict("records"),
                "unallocated_foreign_cash": allocation.unallocated_foreign_cash.to_dict(
                    "records"
                ),
                "funding_gap_by_transaction": (
                    allocation.import_funding_gap_by_transaction.to_dict("records")
                ),
                "funding_gap_by_currency": (
                    allocation.import_funding_gap_by_currency.to_dict("records")
                ),
                "funding_gap_timing": allocation.funding_gap_timing.to_dict("records"),
            },
            "foreign currency",
            self._as_of_date,
            "Session allocation schedule and portfolio",
            [
                "Allocation changes import funding only, not transaction or economic FX exposure."
            ],
        )

    def get_document_provenance(self, transaction_id: str) -> CalculationResult:
        relevant = [
            event
            for event in self._audit_events
            if event.get("transaction_id") == transaction_id
            or event.get("approved_values", {}).get("transaction_id")
            == transaction_id
        ]
        return _calculation_result(
            "Document provenance",
            {"transaction_id": transaction_id},
            {"events": relevant},
            "audit records",
            self._as_of_date,
            "Session audit trail",
            ["Absence of an event does not establish document authenticity."],
        )

    def search_trade_finance_guidance(
        self, query: str, limit: int = 3
    ) -> list[PolicyExcerpt]:
        if self._policy_retriever is None:
            return []
        return self._policy_retriever.search(query, limit=limit)

    def build_bank_consultation_checklist(
        self, context: str
    ) -> dict[str, Any]:
        documents = self.search_trade_finance_guidance(
            context + " required consultation documents invoice payment terms",
            limit=3,
        )
        return {
            "checklist": [
                "거래 계약서 또는 주문서",
                "상업송장과 거래 통화·금액",
                "예상 결제일과 결제조건",
                "운송서류와 원산지 관련 서류(해당 시)",
                "거래상대방 정보",
                "상담 목적: 유동성, 환위험, 보험 또는 보증 검토",
            ],
            "documents": documents,
            "limitation": (
                "실제 필요 서류와 현재 이용 가능 조건은 은행 및 관련 기관에 "
                "확인해야 합니다."
            ),
        }
