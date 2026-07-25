"""Indicative theoretical forward rates using covered interest parity."""

from __future__ import annotations

import pandas as pd

from .validators import validate_fx_rates

SUPPORTED_TENORS_MONTHS = (1, 3, 6, 12)
FORWARD_LABEL = "Indicative theoretical forward rate"
DAY_COUNT_CONVENTION = "ACT/365"


def calculate_theoretical_forward_rate_for_years(
    spot_rate: float,
    krw_interest_rate: float,
    foreign_interest_rate: float,
    tenor_years: float,
) -> float:
    """Calculate a theoretical forward for an explicit positive year fraction."""

    if spot_rate <= 0:
        raise ValueError("spot_rate must be positive")
    if tenor_years <= 0:
        raise ValueError("tenor_years must be positive")
    denominator = 1 + float(foreign_interest_rate) * float(tenor_years)
    if denominator <= 0:
        raise ValueError("foreign interest rate produces a non-positive denominator")
    return float(spot_rate) * (
        1 + float(krw_interest_rate) * float(tenor_years)
    ) / denominator


def calculate_theoretical_forward_rate(
    spot_rate: float,
    krw_interest_rate: float,
    foreign_interest_rate: float,
    tenor_months: int,
) -> float:
    """Calculate a simple-interest covered-interest-parity forward rate."""

    if tenor_months not in SUPPORTED_TENORS_MONTHS:
        raise ValueError("tenor_months must be one of: 1, 3, 6, 12")
    tenor_years = tenor_months / 12.0
    return calculate_theoretical_forward_rate_for_years(
        spot_rate, krw_interest_rate, foreign_interest_rate, tenor_years
    )


def build_forward_rate_table(
    fx_rates: pd.DataFrame,
    tenors_months: tuple[int, ...] = SUPPORTED_TENORS_MONTHS,
    manual_quotes: dict[tuple[str, int], float] | None = None,
) -> pd.DataFrame:
    """Build theoretical rates; manual quotes are separate comparison inputs."""

    rates = validate_fx_rates(fx_rates)
    manual_quotes = manual_quotes or {}
    rows = []
    for rate in rates.itertuples(index=False):
        for tenor in tenors_months:
            theoretical = calculate_theoretical_forward_rate(
                rate.spot_rate_krw,
                rate.krw_interest_rate,
                rate.foreign_interest_rate,
                tenor,
            )
            rows.append(
                {
                    "currency": rate.currency,
                    "tenor_months": tenor,
                    "rate_type": FORWARD_LABEL,
                    "theoretical_forward_rate": theoretical,
                    "manual_bank_quote": manual_quotes.get((rate.currency, tenor)),
                }
            )
    return pd.DataFrame(rows)


def build_settlement_forward_table(
    transactions: pd.DataFrame,
    fx_rates: pd.DataFrame,
    as_of_date: str | pd.Timestamp | None,
) -> pd.DataFrame:
    """Calculate a distinct ACT/365 theoretical forward per settlement date."""

    if as_of_date is None:
        raise ValueError("as_of_date is required in settlement-date mode")
    from .validators import validate_transactions

    rates = validate_fx_rates(fx_rates)
    validated = validate_transactions(transactions, rates)
    try:
        as_of = pd.Timestamp(as_of_date).normalize()
    except (TypeError, ValueError) as exc:
        raise ValueError("as_of_date must be a valid date") from exc
    if pd.isna(as_of):
        raise ValueError("as_of_date must be a valid date")

    rate_lookup = rates.set_index("currency")
    rows = []
    for transaction in validated.itertuples(index=False):
        settlement = pd.Timestamp(transaction.expected_date).normalize()
        tenor_days = int((settlement - as_of).days)
        if tenor_days <= 0:
            raise ValueError(
                f"Settlement date for {transaction.transaction_id} must be after as_of_date"
            )
        tenor_years = tenor_days / 365.0
        rate = rate_lookup.loc[transaction.currency]
        theoretical = calculate_theoretical_forward_rate_for_years(
            float(rate["spot_rate_krw"]),
            float(rate["krw_interest_rate"]),
            float(rate["foreign_interest_rate"]),
            tenor_years,
        )
        rows.append(
            {
                "transaction_id": transaction.transaction_id,
                "currency": transaction.currency,
                "expected_date": settlement,
                "as_of_date": as_of,
                "tenor_days": tenor_days,
                "tenor_years": tenor_years,
                "day_count_convention": DAY_COUNT_CONVENTION,
                "rate_type": FORWARD_LABEL,
                "theoretical_forward_rate": theoretical,
            }
        )
    return pd.DataFrame(rows)
