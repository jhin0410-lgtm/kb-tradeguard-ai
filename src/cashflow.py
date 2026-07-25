"""Monthly probability-weighted cash-flow simulation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import pandas as pd

from .validators import validate_transactions

CashFlowView = Literal["committed", "expected", "realization", "downside"]
CASH_FLOW_VIEWS: tuple[CashFlowView, ...] = (
    "committed",
    "expected",
    "realization",
    "downside",
)


def calculate_monthly_cashflow(
    transactions: pd.DataFrame,
    exchange_rate: float | Mapping[str, float],
    monthly_fixed_krw_costs: float,
    beginning_krw_cash: float,
    delay_transaction_id: str | None = None,
    delay_days: int = 0,
    cash_flow_view: CashFlowView = "expected",
) -> pd.DataFrame:
    """Aggregate transactions and roll forward monthly KRW cash.

    The view determines inclusion and weighting. Every row identifies its view.
    By default, the horizon spans the earliest through latest transaction month
    after any requested delay, with fixed costs only in displayed months.
    """

    if cash_flow_view not in CASH_FLOW_VIEWS:
        raise ValueError(
            f"cash_flow_view must be one of: {', '.join(CASH_FLOW_VIEWS)}"
        )
    if monthly_fixed_krw_costs < 0:
        raise ValueError("monthly_fixed_krw_costs must be non-negative")
    if delay_days < 0:
        raise ValueError("delay_days must be non-negative")

    validated = validate_transactions(transactions)
    working = validated.copy()

    if isinstance(exchange_rate, Mapping):
        rates = {str(key).upper(): float(value) for key, value in exchange_rate.items()}
        missing = sorted(set(working["currency"]) - set(rates))
        if missing:
            raise ValueError(f"No exchange rate provided for: {', '.join(missing)}")
        if any(value <= 0 for value in rates.values()):
            raise ValueError("exchange rates must be positive")
        working["exchange_rate"] = working["currency"].map(rates)
    else:
        if float(exchange_rate) <= 0:
            raise ValueError("exchange_rate must be positive")
        if working["currency"].nunique() > 1:
            raise ValueError(
                "A currency-to-rate mapping is required for multi-currency cash flow"
            )
        working["exchange_rate"] = float(exchange_rate)

    if delay_transaction_id is not None:
        matching = working["transaction_id"] == delay_transaction_id
        if not matching.any():
            raise ValueError(f"Transaction not found: {delay_transaction_id}")
        if (working.loc[matching, "transaction_type"] != "export").any():
            raise ValueError("Only export transactions can be delayed")
        working.loc[matching, "expected_date"] += pd.to_timedelta(delay_days, unit="D")

    if cash_flow_view == "committed":
        included = working["status"] == "confirmed"
        factor = included.astype(float)
    elif cash_flow_view == "expected":
        factor = working["probability"]
    elif cash_flow_view == "realization":
        factor = pd.Series(1.0, index=working.index)
    else:
        confirmed = working["status"] == "confirmed"
        expected_import = (
            (working["status"] == "expected")
            & (working["transaction_type"] == "import")
        )
        factor = (confirmed | expected_import).astype(float)

    working["view_cash_flow_krw"] = (
        working["amount_fc"] * factor * working["exchange_rate"]
    )
    working["year_month"] = working["expected_date"].dt.to_period("M")

    first_month = working["year_month"].min()
    last_month = working["year_month"].max()
    all_months = pd.period_range(first_month, last_month, freq="M")
    export_totals = (
        working.loc[working["transaction_type"] == "export"]
        .groupby("year_month")["view_cash_flow_krw"]
        .sum()
    )
    import_totals = (
        working.loc[working["transaction_type"] == "import"]
        .groupby("year_month")["view_cash_flow_krw"]
        .sum()
    )

    rows = []
    opening_cash = float(beginning_krw_cash)
    for month in all_months:
        export_inflows = float(export_totals.get(month, 0.0))
        import_outflows = float(import_totals.get(month, 0.0))
        transaction_flow = export_inflows - import_outflows
        fixed_cost = float(monthly_fixed_krw_costs)
        monthly_net = transaction_flow - fixed_cost
        ending_cash = opening_cash + monthly_net
        rows.append(
            {
                "cash_flow_view": cash_flow_view,
                "year_month": str(month),
                "beginning_cash_krw": opening_cash,
                "export_inflows_krw": export_inflows,
                "import_outflows_krw": import_outflows,
                "transaction_cash_flow_krw": transaction_flow,
                "fixed_costs_krw": fixed_cost,
                "monthly_net_cash_flow_krw": monthly_net,
                "ending_cash_krw": ending_cash,
                "cash_shortfall_krw": max(0.0, -ending_cash),
            }
        )
        opening_cash = ending_cash

    return pd.DataFrame(rows)
