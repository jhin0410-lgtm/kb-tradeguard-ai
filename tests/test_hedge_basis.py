import json
from pathlib import Path

import pandas as pd

from src.exposure import calculate_exposure
from src.hedging import (
    DEFAULT_HEDGE_ANALYSIS_BASIS,
    select_hedge_analysis_basis,
)


def _sample_exposure():
    company = json.loads(
        Path("data/sample_company.json").read_text(encoding="utf-8")
    )
    return calculate_exposure(
        pd.read_csv("data/sample_transactions.csv"),
        company["foreign_cash"],
        pd.read_csv("data/sample_fx_rates.csv"),
    )


def test_default_basis_is_expected_transaction_exposure_without_cash():
    result = select_hedge_analysis_basis(_sample_exposure().by_currency)
    rows = result.set_index("currency")
    assert DEFAULT_HEDGE_ANALYSIS_BASIS == "Expected transaction exposure"
    assert rows.loc["USD", "hedge_analysis_amount_fc"] == 225_000
    assert rows.loc["EUR", "hedge_analysis_amount_fc"] == 0
    assert not rows.loc["EUR", "automatic_transaction_hedge_candidate"]


def test_total_economic_basis_requires_explicit_selection_and_includes_cash():
    result = select_hedge_analysis_basis(
        _sample_exposure().by_currency, "Expected total economic position"
    ).set_index("currency")
    assert result.loc["USD", "hedge_analysis_amount_fc"] == 265_000
    assert result.loc["EUR", "hedge_analysis_amount_fc"] == 10_000
    assert (
        result.loc["EUR", "position_classification"]
        == "Balance-sheet foreign-currency asset position"
    )
    assert not result.loc["EUR", "automatic_transaction_hedge_candidate"]
