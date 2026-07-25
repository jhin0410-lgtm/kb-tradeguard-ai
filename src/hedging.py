"""Natural-hedge and deterministic forward-hedge comparisons."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from .validators import validate_transactions

DEFAULT_HEDGE_RATIOS = (0.0, 0.3, 0.5, 0.7, 1.0)
DEFAULT_SPOT_SCENARIOS = (-0.10, -0.05, 0.0, 0.05, 0.10)
TRANSACTION_COST_NOTE = "Transaction costs and customer-specific spreads are excluded."
HEDGE_ANALYSIS_BASES = {
    "Expected transaction exposure": "expected_transaction_exposure",
    "Nominal transaction exposure": "nominal_transaction_exposure",
    "Expected total economic position": "expected_total_economic_position",
    "Nominal total economic position": "nominal_total_economic_position",
}
DEFAULT_HEDGE_ANALYSIS_BASIS = "Expected transaction exposure"


@dataclass(frozen=True)
class NaturalHedgeResult:
    """Gross and maturity-aware offsets plus auditable transaction matches."""

    summary: pd.DataFrame
    matches: pd.DataFrame


def select_hedge_analysis_basis(
    exposure_by_currency: pd.DataFrame,
    basis: str = DEFAULT_HEDGE_ANALYSIS_BASIS,
) -> pd.DataFrame:
    """Select a clearly labeled derivative-analysis amount by currency."""

    if basis not in HEDGE_ANALYSIS_BASES:
        raise ValueError(
            "analysis basis must be one of: " + ", ".join(HEDGE_ANALYSIS_BASES)
        )
    source_column = HEDGE_ANALYSIS_BASES[basis]
    required = {"currency", source_column, "position_classification"}
    missing = sorted(required - set(exposure_by_currency.columns))
    if missing:
        raise ValueError(f"Exposure table missing columns: {', '.join(missing)}")
    result = exposure_by_currency[
        ["currency", source_column, "position_classification"]
    ].copy()
    result = result.rename(columns={source_column: "hedge_analysis_amount_fc"})
    result["analysis_basis"] = basis
    result["automatic_transaction_hedge_candidate"] = (
        (result["hedge_analysis_amount_fc"] != 0)
        & ~result["position_classification"].eq(
            "Balance-sheet foreign-currency asset position"
        )
    )
    return result


def calculate_natural_hedge(
    transactions: pd.DataFrame,
    foreign_cash: dict[str, float],
    matching_window_days: int = 30,
) -> NaturalHedgeResult:
    """Calculate gross and maturity-matched offsets independently by currency.

    Candidate pairs are ordered by smallest absolute date gap, then export date,
    import date, export ID, and import ID. Each pair receives the smaller
    remaining amount, allowing partial matches without exceeding either side.
    """

    validated = validate_transactions(transactions)
    if matching_window_days < 0:
        raise ValueError("matching_window_days must be non-negative")
    cash = {str(key).upper(): float(value) for key, value in foreign_cash.items()}
    if any(value < 0 for value in cash.values()):
        raise ValueError("foreign cash amounts must be non-negative")
    currencies = sorted(set(validated["currency"]) | set(cash))
    summary_rows = []
    match_rows: list[dict[str, float | int | str]] = []
    for currency in currencies:
        subset = validated[validated["currency"] == currency]
        export_rows = subset[subset["transaction_type"] == "export"].copy()
        import_rows = subset[subset["transaction_type"] == "import"].copy()
        exports = float(export_rows["amount_fc"].sum())
        imports = float(import_rows["amount_fc"].sum())
        gross_offset = min(exports, imports)

        export_remaining = dict(
            zip(export_rows["transaction_id"], export_rows["amount_fc"], strict=True)
        )
        import_remaining = dict(
            zip(import_rows["transaction_id"], import_rows["amount_fc"], strict=True)
        )
        candidates = []
        for export in export_rows.itertuples(index=False):
            for import_row in import_rows.itertuples(index=False):
                gap = abs((export.expected_date - import_row.expected_date).days)
                if gap <= matching_window_days:
                    candidates.append(
                        (
                            gap,
                            export.expected_date,
                            import_row.expected_date,
                            export.transaction_id,
                            import_row.transaction_id,
                        )
                    )
        candidates.sort()
        for gap, export_date, import_date, export_id, import_id in candidates:
            amount = min(export_remaining[export_id], import_remaining[import_id])
            if amount <= 0:
                continue
            export_remaining[export_id] -= amount
            import_remaining[import_id] -= amount
            match_rows.append(
                {
                    "currency": currency,
                    "export_transaction_id": export_id,
                    "import_transaction_id": import_id,
                    "export_expected_date": export_date,
                    "import_expected_date": import_date,
                    "timing_gap_days": gap,
                    "matched_amount_fc": float(amount),
                }
            )
        maturity_offset = float(
            sum(
                row["matched_amount_fc"]
                for row in match_rows
                if row["currency"] == currency
            )
        )
        summary_rows.append(
            {
                "currency": currency,
                "export_inflows": exports,
                "import_outflows": imports,
                "foreign_cash": cash.get(currency, 0.0),
                "gross_currency_offset": gross_offset,
                "gross_currency_offset_ratio": (
                    gross_offset / exports if exports else 0.0
                ),
                "maturity_matched_offset": maturity_offset,
                "maturity_matched_offset_ratio": (
                    maturity_offset / exports if exports else 0.0
                ),
                "unmatched_exports": exports - maturity_offset,
                "unmatched_imports": imports - maturity_offset,
                "matching_window_days": matching_window_days,
            }
        )
    match_columns = [
        "currency",
        "export_transaction_id",
        "import_transaction_id",
        "export_expected_date",
        "import_expected_date",
        "timing_gap_days",
        "matched_amount_fc",
    ]
    return NaturalHedgeResult(
        summary=pd.DataFrame(summary_rows),
        matches=pd.DataFrame(match_rows, columns=match_columns),
    )


def adjusted_forward_rate(
    forward_rate: float,
    spread: float,
    exposure_type: Literal["export", "import"],
) -> float:
    """Apply a per-unit spread in the direction adverse to the customer."""

    if forward_rate <= 0:
        raise ValueError("forward_rate must be positive")
    if spread < 0:
        raise ValueError("spread must be non-negative")
    if exposure_type == "export":
        adjusted = forward_rate - spread
    elif exposure_type == "import":
        adjusted = forward_rate + spread
    else:
        raise ValueError("exposure_type must be export or import")
    if adjusted <= 0:
        raise ValueError("spread produces a non-positive adjusted forward rate")
    return adjusted


def compare_hedge_ratios(
    currency: str,
    exposure_amount_fc: float,
    exposure_type: Literal["export", "import"],
    spot_rate: float,
    forward_rate: float,
    spread: float = 0.0,
    hedge_ratios: Iterable[float] = DEFAULT_HEDGE_RATIOS,
    scenario_percentages: Iterable[float] = DEFAULT_SPOT_SCENARIOS,
) -> pd.DataFrame:
    """Compare forward hedge ratios across deterministic terminal spot shocks."""

    if exposure_amount_fc < 0:
        raise ValueError("exposure_amount_fc must be non-negative")
    if spot_rate <= 0:
        raise ValueError("spot_rate must be positive")
    adjusted = adjusted_forward_rate(forward_rate, spread, exposure_type)
    ratios = [float(value) for value in hedge_ratios]
    if any(value < 0 or value > 1 for value in ratios):
        raise ValueError("hedge ratios must be between 0 and 1")

    rows = []
    direction = 1.0 if exposure_type == "export" else -1.0
    for scenario in scenario_percentages:
        scenario = float(scenario)
        scenario_spot = float(spot_rate) * (1 + scenario)
        unhedged_baseline = float(exposure_amount_fc) * scenario_spot
        for ratio in ratios:
            hedged_amount = float(exposure_amount_fc) * ratio
            unhedged_amount = float(exposure_amount_fc) - hedged_amount
            locked = hedged_amount * adjusted
            unhedged_value = unhedged_amount * scenario_spot
            total = locked + unhedged_value
            if exposure_type == "export":
                change = total - unhedged_baseline
                protection = max(change, 0.0)
                opportunity_cost = max(-change, 0.0)
            else:
                change = unhedged_baseline - total
                protection = max(change, 0.0)
                opportunity_cost = max(-change, 0.0)
            rows.append(
                {
                    "currency": currency.upper(),
                    "exposure_type": exposure_type,
                    "scenario_pct": scenario,
                    "scenario_spot_rate": scenario_spot,
                    "hedge_ratio": ratio,
                    "hedged_amount_fc": hedged_amount,
                    "unhedged_amount_fc": unhedged_amount,
                    "adjusted_forward_rate": adjusted,
                    "forward_locked_krw": locked,
                    "unhedged_krw_value": unhedged_value,
                    "total_krw_value": total,
                    "signed_total_krw": direction * total,
                    "change_vs_no_hedge_krw": change,
                    "downside_protection_krw": protection,
                    "upside_opportunity_cost_krw": opportunity_cost,
                    "cost_limitation": (
                        TRANSACTION_COST_NOTE
                        if spread == 0
                        else "User-entered spread included; other transaction costs are excluded."
                    ),
                }
            )
    return pd.DataFrame(rows)
