"""Deterministic maturity bucket assignment and exposure aggregation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .forward_rates import build_settlement_forward_table
from .hedging import calculate_natural_hedge
from .validators import validate_fx_rates, validate_transactions

DEFAULT_MATURITY_BUCKETS = (
    (0, 30, "0-30 days"),
    (31, 90, "31-90 days"),
    (91, 180, "91-180 days"),
    (181, 365, "181-365 days"),
    (366, None, "over 365 days"),
)


def assign_maturity_bucket(tenor_days: int) -> str:
    """Assign a positive ACT/365 tenor to one inclusive default bucket."""

    if tenor_days <= 0:
        raise ValueError("tenor_days must be positive")
    for lower, upper, label in DEFAULT_MATURITY_BUCKETS:
        if tenor_days >= lower and (upper is None or tenor_days <= upper):
            return label
    raise RuntimeError("No maturity bucket configured")


@dataclass(frozen=True)
class MaturityBucketResult:
    summary: pd.DataFrame
    transaction_tenors: pd.DataFrame
    natural_hedge_matches: pd.DataFrame


def build_maturity_bucket_exposure(
    transactions: pd.DataFrame,
    fx_rates: pd.DataFrame,
    as_of_date: str | pd.Timestamp,
    matching_window_days: int = 30,
) -> MaturityBucketResult:
    """Aggregate exposure by currency and maturity without cross-currency netting."""

    rates = validate_fx_rates(fx_rates)
    validated = validate_transactions(transactions, rates)
    tenors = build_settlement_forward_table(validated, rates, as_of_date)
    working = validated.merge(
        tenors[
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
    working["maturity_bucket"] = working["tenor_days"].map(assign_maturity_bucket)
    working["expected_amount_fc"] = working["amount_fc"] * working["probability"]

    natural = calculate_natural_hedge(
        validated, {}, matching_window_days=matching_window_days
    )
    matches = natural.matches.copy()
    if not matches.empty:
        bucket_lookup = working.set_index("transaction_id")["maturity_bucket"]
        matches["export_bucket"] = matches["export_transaction_id"].map(bucket_lookup)
        matches["import_bucket"] = matches["import_transaction_id"].map(bucket_lookup)
        # Attribute a cross-bucket eligible match to the later settlement
        # bucket, when the liquidity offset is fully effective.
        matches["matched_bucket"] = matches.apply(
            lambda row: (
                row["export_bucket"]
                if row["export_expected_date"] >= row["import_expected_date"]
                else row["import_bucket"]
            ),
            axis=1,
        )

    rows = []
    bucket_order = {label: index for index, (_, _, label) in enumerate(DEFAULT_MATURITY_BUCKETS)}
    for (currency, bucket), subset in working.groupby(
        ["currency", "maturity_bucket"], sort=False
    ):
        exports = subset["transaction_type"] == "export"
        imports = subset["transaction_type"] == "import"
        nominal_exports = float(subset.loc[exports, "amount_fc"].sum())
        expected_exports = float(subset.loc[exports, "expected_amount_fc"].sum())
        nominal_imports = float(subset.loc[imports, "amount_fc"].sum())
        expected_imports = float(subset.loc[imports, "expected_amount_fc"].sum())
        total_expected = float(subset["expected_amount_fc"].sum())
        weighted_tenor = (
            float(
                (subset["tenor_years"] * subset["expected_amount_fc"]).sum()
                / total_expected
            )
            if total_expected
            else 0.0
        )
        weighted_forward = (
            float(
                (
                    subset["theoretical_forward_rate"]
                    * subset["expected_amount_fc"]
                ).sum()
                / total_expected
            )
            if total_expected
            else 0.0
        )
        maturity_offset = 0.0
        if not matches.empty:
            maturity_offset = float(
                matches.loc[
                    (matches["currency"] == currency)
                    & (matches["matched_bucket"] == bucket),
                    "matched_amount_fc",
                ].sum()
            )
        rows.append(
            {
                "currency": currency,
                "maturity_bucket": bucket,
                "nominal_export_exposure": nominal_exports,
                "expected_export_exposure": expected_exports,
                "nominal_import_exposure": nominal_imports,
                "expected_import_exposure": expected_imports,
                "nominal_transaction_exposure": nominal_exports - nominal_imports,
                "expected_transaction_exposure": expected_exports - expected_imports,
                "maturity_matched_natural_offset": maturity_offset,
                "remaining_hedgeable_exposure": expected_exports - expected_imports,
                "weighted_average_tenor_years": weighted_tenor,
                "indicative_theoretical_forward_rate": weighted_forward,
                "_bucket_order": bucket_order[bucket],
            }
        )
    summary = pd.DataFrame(rows).sort_values(
        ["currency", "_bucket_order"]
    ).drop(columns="_bucket_order")
    return MaturityBucketResult(summary, working, matches)
