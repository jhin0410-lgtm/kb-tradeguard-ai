import json
from pathlib import Path

import pandas as pd
import pytest

from src.exposure import calculate_exposure
from src.validators import validate_transactions

SAMPLE_PATH = Path(__file__).parents[1] / "data" / "sample_transactions.csv"
FX_PATH = Path(__file__).parents[1] / "data" / "sample_fx_rates.csv"
COMPANY_PATH = Path(__file__).parents[1] / "data" / "sample_company.json"


def test_exact_nominal_and_expected_exposure_for_intended_sample():
    transactions = pd.read_csv(SAMPLE_PATH)
    fx_rates = pd.read_csv(FX_PATH)
    company = json.loads(COMPANY_PATH.read_text(encoding="utf-8"))

    result = calculate_exposure(
        transactions, foreign_cash_held=company["foreign_cash"], fx_rates=fx_rates
    )
    rows = result.by_currency.set_index("currency")

    assert rows.loc["USD", "nominal_transaction_exposure"] == 250_000
    assert rows.loc["USD", "expected_transaction_exposure"] == 225_000
    assert rows.loc["USD", "foreign_cash_position"] == 40_000
    assert rows.loc["USD", "nominal_total_economic_position"] == 290_000
    assert rows.loc["USD", "expected_total_economic_position"] == 265_000
    assert rows.loc["EUR", "foreign_cash_position"] == 10_000
    assert rows.loc["EUR", "expected_total_economic_position"] == 10_000
    assert result.consolidated_expected_total_economic_position_krw == 373_550_000


@pytest.mark.parametrize("invalid_type", ["sale", "EXPORT", ""])
def test_invalid_transaction_type_is_rejected(invalid_type):
    transactions = pd.read_csv(SAMPLE_PATH)
    transactions.loc[0, "transaction_type"] = invalid_type

    with pytest.raises(ValueError, match="transaction_type"):
        validate_transactions(transactions)


def test_negative_amount_is_rejected():
    transactions = pd.read_csv(SAMPLE_PATH)
    transactions.loc[0, "amount_fc"] = -1

    with pytest.raises(ValueError, match="amount_fc"):
        validate_transactions(transactions)


def test_invalid_status_is_rejected():
    transactions = pd.read_csv(SAMPLE_PATH)
    transactions.loc[0, "status"] = "pending"

    with pytest.raises(ValueError, match="status"):
        validate_transactions(transactions)
