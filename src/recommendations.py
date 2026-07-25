"""Explainable deterministic FX and liquidity considerations."""

from __future__ import annotations

import pandas as pd

from .exposure import ExposureResult
from .hedging import DEFAULT_HEDGE_ANALYSIS_BASIS, NaturalHedgeResult
from .validators import validate_transactions

GENERAL_NOTE = (
    "These are planning considerations from a deterministic simulation, "
    "not definitive or personalized financial advice."
)
LIMITATION = (
    "Simulation thresholds do not determine product suitability and exclude "
    "customer-specific terms, transaction costs, and professional review."
)


def generate_recommendations(
    exposure: ExposureResult,
    cashflow: pd.DataFrame,
    transactions: pd.DataFrame,
    natural_hedge: NaturalHedgeResult | None = None,
    theoretical_forward_rate: float | None = None,
    manual_bank_quote: float | None = None,
    full_hedge_opportunity_cost_krw: float | None = None,
    hedge_analysis_basis: str = DEFAULT_HEDGE_ANALYSIS_BASIS,
) -> list[dict[str, str]]:
    """Apply transparent rules with trigger, observation, basis, and limitation."""

    recommendations: list[dict[str, str]] = []
    if (cashflow["ending_cash_krw"] < 0).any():
        shortfall = float(cashflow["cash_shortfall_krw"].max())
        recommendations.append(
            {
                "title": "Review liquidity before hedge-return optimization",
                "trigger_metric": "Maximum simulated cash shortfall",
                "observed_value": f"KRW {shortfall:,.0f}",
                "threshold_or_basis": "Any monthly ending cash below zero",
                "suggested_consideration": (
                    "Review liquidity timing and working-capital alternatives before "
                    "optimizing hedge returns."
                ),
                "limitation": LIMITATION,
            }
        )

    for row in exposure.by_currency.itertuples(index=False):
        exports = float(row.expected_export_exposure)
        transaction_exposure = float(row.expected_transaction_exposure)
        ratio = abs(transaction_exposure) / exports if exports else 0.0
        if exports > 0 and ratio > 0.30:
            recommendations.append(
                {
                    "title": f"Compare partial hedge ratios for {row.currency}",
                    "trigger_metric": "Expected transaction exposure / expected exports",
                    "observed_value": f"{ratio:.1%}",
                    "threshold_or_basis": "Greater than 30%",
                    "suggested_consideration": (
                        "Compare multiple partial hedge ratios rather than treating one "
                        f"ratio as automatically preferable. Analysis basis: "
                        f"{hedge_analysis_basis}."
                    ),
                    "limitation": LIMITATION,
                }
            )
        if (
            row.position_classification
            == "Balance-sheet foreign-currency asset position"
        ):
            recommendations.append(
                {
                    "title": f"Classify {row.currency} cash as an FX asset",
                    "trigger_metric": "Cash-only foreign-currency position",
                    "observed_value": f"{row.currency} {row.foreign_cash_position:,.0f}",
                    "threshold_or_basis": "Cash exists with no transaction exposure",
                    "suggested_consideration": (
                        "Treat this as a balance-sheet foreign-currency asset, not an "
                        "import obligation. Do not initiate a transaction hedge without "
                        "an explicit treasury objective."
                    ),
                    "limitation": LIMITATION,
                }
            )
        elif row.foreign_cash_position > 0 and exports > 0:
            recommendations.append(
                {
                    "title": f"Keep {row.currency} cash separate from export exposure",
                    "trigger_metric": "Foreign cash position",
                    "observed_value": f"{row.currency} {row.foreign_cash_position:,.0f}",
                    "threshold_or_basis": "Positive cash held alongside exports",
                    "suggested_consideration": (
                        "Foreign cash may support import liquidity but does not reduce "
                        "the export transaction exposure automatically."
                    ),
                    "limitation": LIMITATION,
                }
            )
        if row.import_funding_gap_fc > 0:
            recommendations.append(
                {
                    "title": f"Review {row.currency} import funding allocation",
                    "trigger_metric": "Import funding gap",
                    "observed_value": f"{row.currency} {row.import_funding_gap_fc:,.0f}",
                    "threshold_or_basis": (
                        "Nominal imports less explicitly allocated foreign cash"
                    ),
                    "suggested_consideration": (
                        "Review liquidity funding separately from the economic FX position."
                    ),
                    "limitation": (
                        "Available foreign cash is not assumed allocated unless selected. "
                        + LIMITATION
                    ),
                }
            )

    validated = validate_transactions(transactions)
    if "invoice_date" in validated.columns:
        exports = validated[validated["transaction_type"] == "export"].copy()
        settlement_days = (exports["expected_date"] - exports["invoice_date"]).dt.days
        long_ids = exports.loc[settlement_days > 90, "transaction_id"].tolist()
        if long_ids:
            recommendations.append(
                {
                    "title": "Long settlement exposure",
                    "trigger_metric": "Receivable settlement period",
                    "observed_value": ", ".join(long_ids),
                    "threshold_or_basis": "More than 90 days",
                    "suggested_consideration": (
                        "Review collection timing and related currency exposure."
                    ),
                    "limitation": LIMITATION,
                }
            )

    if natural_hedge is not None:
        for row in natural_hedge.summary.itertuples(index=False):
            if (
                row.gross_currency_offset_ratio >= 0.50
                and row.maturity_matched_offset_ratio
                < row.gross_currency_offset_ratio * 0.50
            ):
                recommendations.append(
                    {
                        "title": f"Review {row.currency} maturity mismatch",
                        "trigger_metric": "Gross offset vs maturity-matched offset",
                        "observed_value": (
                            f"{row.gross_currency_offset_ratio:.1%} gross vs "
                            f"{row.maturity_matched_offset_ratio:.1%} maturity-matched"
                        ),
                        "threshold_or_basis": (
                            "Gross ratio at least 50% and maturity ratio below half "
                            "the gross ratio"
                        ),
                        "suggested_consideration": (
                            "Treat the difference as timing and liquidity risk; gross "
                            "amount offset is not a fully effective liquidity hedge."
                        ),
                        "limitation": (
                            f"Matching uses a {row.matching_window_days}-day window. "
                            + LIMITATION
                        ),
                    }
                )

    if (
        theoretical_forward_rate is not None
        and manual_bank_quote is not None
        and theoretical_forward_rate > 0
    ):
        difference_ratio = (
            abs(manual_bank_quote - theoretical_forward_rate)
            / theoretical_forward_rate
        )
        if difference_ratio >= 0.01:
            recommendations.append(
                {
                    "title": "Verify the manually entered bank quote",
                    "trigger_metric": "Absolute difference from theoretical rate",
                    "observed_value": f"{difference_ratio:.2%}",
                    "threshold_or_basis": "At least 1%",
                    "suggested_consideration": (
                        "Verify tenor, spread, credit conditions, and quote timestamp."
                    ),
                    "limitation": (
                        "The theoretical rate is not an executable quote or actual KB price. "
                        + LIMITATION
                    ),
                }
            )

    if full_hedge_opportunity_cost_krw is not None and full_hedge_opportunity_cost_krw > 0:
        recommendations.append(
            {
                "title": "Treat full hedging as a protection/opportunity trade-off",
                "trigger_metric": "100% hedge upside opportunity cost",
                "observed_value": f"KRW {full_hedge_opportunity_cost_krw:,.0f}",
                "threshold_or_basis": "Greater than zero in a favorable spot scenario",
                "suggested_consideration": (
                    "Compare downside protection against foregone favorable spot movement."
                ),
                "limitation": LIMITATION,
            }
        )

    if not recommendations:
        recommendations.append(
            {
                "title": "No rule threshold triggered",
                "trigger_metric": "Configured deterministic rules",
                "observed_value": "No threshold exceeded",
                "threshold_or_basis": "Rules evaluated with supplied assumptions",
                "suggested_consideration": (
                    "Continue reviewing assumptions and scenario sensitivity."
                ),
                "limitation": LIMITATION,
            }
        )
    return recommendations
