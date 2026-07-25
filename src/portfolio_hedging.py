"""Transaction-level and maturity-bucket deterministic portfolio hedging."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from .forward_rates import build_settlement_forward_table
from .hedging import adjusted_forward_rate
from .maturity_buckets import (
    MaturityBucketResult,
    assign_maturity_bucket,
    build_maturity_bucket_exposure,
)
from .validators import validate_fx_rates, validate_transactions

ExposureMeasure = Literal["expected", "nominal"]


@dataclass(frozen=True)
class PortfolioHedgeResult:
    mode: str
    transaction_results: pd.DataFrame
    currency_scenario_totals: pd.DataFrame
    portfolio_scenario_totals: pd.DataFrame
    bucket_summary: pd.DataFrame | None = None
    bucket_scenario_totals: pd.DataFrame | None = None


def _value_for(mapping_or_scalar, currency: str, bucket: str | None = None) -> float:
    if isinstance(mapping_or_scalar, Mapping):
        if bucket is not None and (currency, bucket) in mapping_or_scalar:
            return float(mapping_or_scalar[(currency, bucket)])
        return float(mapping_or_scalar.get(currency, 0.0))
    return float(mapping_or_scalar)


def calculate_transaction_level_portfolio_hedge(
    transactions: pd.DataFrame,
    fx_rates: pd.DataFrame,
    as_of_date: str | pd.Timestamp,
    hedge_ratios: Mapping[str, float] | float = 0.5,
    spreads: Mapping[str, float] | float = 0.0,
    scenario_percentages: Sequence[float] = (-0.10, -0.05, 0.0, 0.05, 0.10),
    exposure_measure: ExposureMeasure = "expected",
    manual_forward_quotes: Mapping[str, float] | None = None,
) -> PortfolioHedgeResult:
    """Apply transaction-specific ACT/365 forwards, then aggregate KRW results."""

    if exposure_measure not in ("expected", "nominal"):
        raise ValueError("exposure_measure must be expected or nominal")
    rates = validate_fx_rates(fx_rates)
    validated = validate_transactions(transactions, rates)
    forwards = build_settlement_forward_table(validated, rates, as_of_date)
    working = validated.merge(
        forwards[
            [
                "transaction_id",
                "tenor_days",
                "tenor_years",
                "theoretical_forward_rate",
            ]
        ],
        on="transaction_id",
        how="left",
        validate="one_to_one",
    )
    spot_map = rates.set_index("currency")["spot_rate_krw"].to_dict()
    manual_forward_quotes = manual_forward_quotes or {}
    rows = []
    for transaction in working.itertuples(index=False):
        amount = float(transaction.amount_fc)
        if exposure_measure == "expected":
            amount *= float(transaction.probability)
        ratio = _value_for(hedge_ratios, transaction.currency)
        if ratio < 0 or ratio > 1:
            raise ValueError("hedge ratios must be between 0 and 1")
        spread = _value_for(spreads, transaction.currency)
        selected_forward_rate = float(
            manual_forward_quotes.get(
                transaction.transaction_id, transaction.theoretical_forward_rate
            )
        )
        adjusted = adjusted_forward_rate(
            selected_forward_rate,
            spread,
            transaction.transaction_type,
        )
        hedged = amount * ratio
        unhedged = amount - hedged
        direction = 1.0 if transaction.transaction_type == "export" else -1.0
        for scenario in scenario_percentages:
            terminal_spot = float(spot_map[transaction.currency]) * (
                1 + float(scenario)
            )
            locked = hedged * adjusted
            terminal = unhedged * terminal_spot
            total = locked + terminal
            rows.append(
                {
                    "transaction_id": transaction.transaction_id,
                    "transaction_type": transaction.transaction_type,
                    "currency": transaction.currency,
                    "expected_date": transaction.expected_date,
                    "tenor_days": transaction.tenor_days,
                    "tenor_years": transaction.tenor_years,
                    "maturity_bucket": assign_maturity_bucket(
                        int(transaction.tenor_days)
                    ),
                    "exposure_measure": exposure_measure,
                    "amount_fc": amount,
                    "signed_exposure_fc": direction * amount,
                    "hedge_ratio": ratio,
                    "hedged_amount_fc": hedged,
                    "unhedged_amount_fc": unhedged,
                    "theoretical_forward_rate": transaction.theoretical_forward_rate,
                    "manual_forward_quote": manual_forward_quotes.get(
                        transaction.transaction_id
                    ),
                    "selected_forward_rate": selected_forward_rate,
                    "adjusted_forward_rate": adjusted,
                    "scenario_pct": float(scenario),
                    "terminal_spot_rate": terminal_spot,
                    "forward_locked_krw": locked,
                    "unhedged_terminal_krw": terminal,
                    "total_krw_amount": total,
                    "signed_total_krw": direction * total,
                }
            )
    transaction_results = pd.DataFrame(rows)
    currency_totals = (
        transaction_results.groupby(["currency", "scenario_pct"], as_index=False)
        .agg(
            export_proceeds_krw=(
                "total_krw_amount",
                lambda values: float(
                    values[
                        transaction_results.loc[
                            values.index, "transaction_type"
                        ].eq("export")
                    ].sum()
                ),
            ),
            import_payments_krw=(
                "total_krw_amount",
                lambda values: float(
                    values[
                        transaction_results.loc[
                            values.index, "transaction_type"
                        ].eq("import")
                    ].sum()
                ),
            ),
            signed_total_krw=("signed_total_krw", "sum"),
        )
    )
    portfolio_totals = (
        currency_totals.groupby("scenario_pct", as_index=False)
        .agg(
            export_proceeds_krw=("export_proceeds_krw", "sum"),
            import_payments_krw=("import_payments_krw", "sum"),
            signed_total_krw=("signed_total_krw", "sum"),
        )
    )
    return PortfolioHedgeResult(
        "transaction-level",
        transaction_results,
        currency_totals,
        portfolio_totals,
    )


def calculate_maturity_bucket_portfolio_hedge(
    transactions: pd.DataFrame,
    fx_rates: pd.DataFrame,
    as_of_date: str | pd.Timestamp,
    hedge_ratios: Mapping[str | tuple[str, str], float] | float = 0.5,
    spreads: Mapping[str, float] | float = 0.0,
    scenario_percentages: Sequence[float] = (-0.10, -0.05, 0.0, 0.05, 0.10),
    exposure_measure: ExposureMeasure = "expected",
    matching_window_days: int = 30,
    manual_forward_quotes: Mapping[str, float] | None = None,
) -> PortfolioHedgeResult:
    """Calculate bucket summaries while preserving transaction-rate reconciliation."""

    bucket_data: MaturityBucketResult = build_maturity_bucket_exposure(
        transactions, fx_rates, as_of_date, matching_window_days
    )
    ratio_by_transaction = {}
    for transaction in bucket_data.transaction_tenors.itertuples(index=False):
        ratio_by_transaction[transaction.currency] = _value_for(
            hedge_ratios, transaction.currency, transaction.maturity_bucket
        )
    # Apply bucket-specific ratios without losing transaction-specific forwards.
    base = calculate_transaction_level_portfolio_hedge(
        transactions,
        fx_rates,
        as_of_date,
        hedge_ratios=0.0,
        spreads=spreads,
        scenario_percentages=scenario_percentages,
        exposure_measure=exposure_measure,
        manual_forward_quotes=manual_forward_quotes,
    )
    transaction_results = base.transaction_results.copy()
    ratio_lookup = {
        (row.currency, row.maturity_bucket): _value_for(
            hedge_ratios, row.currency, row.maturity_bucket
        )
        for row in bucket_data.transaction_tenors.itertuples(index=False)
    }
    for index, row in transaction_results.iterrows():
        ratio = ratio_lookup[(row["currency"], row["maturity_bucket"])]
        if ratio < 0 or ratio > 1:
            raise ValueError("hedge ratios must be between 0 and 1")
        hedged = row["amount_fc"] * ratio
        unhedged = row["amount_fc"] - hedged
        selected_forward = float(
            (manual_forward_quotes or {}).get(
                row["transaction_id"], row["theoretical_forward_rate"]
            )
        )
        adjusted = adjusted_forward_rate(
            selected_forward,
            _value_for(spreads, row["currency"]),
            row["transaction_type"],
        )
        locked = hedged * adjusted
        terminal = unhedged * row["terminal_spot_rate"]
        total = locked + terminal
        direction = 1.0 if row["transaction_type"] == "export" else -1.0
        transaction_results.loc[
            index,
            [
                "hedge_ratio",
                "hedged_amount_fc",
                "unhedged_amount_fc",
                "adjusted_forward_rate",
                "manual_forward_quote",
                "selected_forward_rate",
                "forward_locked_krw",
                "unhedged_terminal_krw",
                "total_krw_amount",
                "signed_total_krw",
            ],
        ] = [
            ratio,
            hedged,
            unhedged,
            adjusted,
            (manual_forward_quotes or {}).get(row["transaction_id"]),
            selected_forward,
            locked,
            terminal,
            total,
            direction * total,
        ]

    currency_totals = (
        transaction_results.groupby(["currency", "scenario_pct"], as_index=False)
        .agg(
            export_proceeds_krw=(
                "total_krw_amount",
                lambda values: float(
                    values[
                        transaction_results.loc[
                            values.index, "transaction_type"
                        ].eq("export")
                    ].sum()
                ),
            ),
            import_payments_krw=(
                "total_krw_amount",
                lambda values: float(
                    values[
                        transaction_results.loc[
                            values.index, "transaction_type"
                        ].eq("import")
                    ].sum()
                ),
            ),
            signed_total_krw=("signed_total_krw", "sum"),
        )
    )
    portfolio_totals = (
        currency_totals.groupby("scenario_pct", as_index=False)
        .agg(
            export_proceeds_krw=("export_proceeds_krw", "sum"),
            import_payments_krw=("import_payments_krw", "sum"),
            signed_total_krw=("signed_total_krw", "sum"),
        )
    )
    bucket_scenarios = (
        transaction_results.groupby(
            ["currency", "maturity_bucket", "scenario_pct"], as_index=False
        )
        .agg(
            selected_hedge_amount_fc=("hedged_amount_fc", "sum"),
            unhedged_amount_fc=("unhedged_amount_fc", "sum"),
            signed_total_krw=("signed_total_krw", "sum"),
        )
    )
    static_hedges = (
        transaction_results[
            [
                "transaction_id",
                "currency",
                "maturity_bucket",
                "hedged_amount_fc",
                "unhedged_amount_fc",
            ]
        ]
        .drop_duplicates(subset=["transaction_id"])
        .groupby(["currency", "maturity_bucket"], as_index=False)
        .agg(
            selected_hedge_amount_fc=("hedged_amount_fc", "sum"),
            unhedged_amount_fc=("unhedged_amount_fc", "sum"),
        )
    )
    summary = bucket_data.summary.merge(
        static_hedges, on=["currency", "maturity_bucket"], how="left"
    )
    return PortfolioHedgeResult(
        "maturity-bucket",
        transaction_results,
        currency_totals,
        portfolio_totals,
        summary,
        bucket_scenarios,
    )
