import pandas as pd
import pytest

from src.exposure import calculate_exposure
from src.validators import validate_transactions


def _transactions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["U-E", "export", "USD", 100, 0.5, "expected", "2026-09-01"],
            ["U-I", "import", "USD", 40, 1.0, "confirmed", "2026-09-02"],
            ["E-E", "export", "EUR", 50, 1.0, "confirmed", "2026-09-03"],
            ["E-I", "import", "EUR", 20, 1.0, "confirmed", "2026-09-04"],
        ],
        columns=[
            "transaction_id",
            "transaction_type",
            "currency",
            "amount_fc",
            "probability",
            "status",
            "expected_date",
        ],
    )


def _rates() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["USD", 1_350.0, 0.025, 0.045],
            ["EUR", 1_580.0, 0.025, 0.030],
        ],
        columns=[
            "currency",
            "spot_rate_krw",
            "krw_interest_rate",
            "foreign_interest_rate",
        ],
    )


def test_currencies_stay_separate_and_cash_matches_currency():
    result = calculate_exposure(
        _transactions(), {"USD": 10, "EUR": 5}, _rates()
    ).by_currency.set_index("currency")

    assert result.loc["USD", "expected_export_exposure"] == 50
    assert result.loc["USD", "expected_import_exposure"] == 40
    assert result.loc["USD", "foreign_cash_position"] == 10
    assert result.loc["USD", "expected_transaction_exposure"] == 10
    assert result.loc["USD", "expected_total_economic_position"] == 20
    assert result.loc["EUR", "expected_export_exposure"] == 50
    assert result.loc["EUR", "expected_import_exposure"] == 20
    assert result.loc["EUR", "foreign_cash_position"] == 5
    assert result.loc["EUR", "expected_transaction_exposure"] == 30
    assert result.loc["EUR", "expected_total_economic_position"] == 35
    assert result.loc["USD", "expected_total_economic_position_krw"] == 27_000
    assert result.loc["EUR", "expected_total_economic_position_krw"] == 55_300


def test_import_funding_allocation_is_optional_and_separate():
    unallocated = calculate_exposure(
        _transactions(), {"USD": 10, "EUR": 5}, _rates()
    ).by_currency.set_index("currency")
    allocated = calculate_exposure(
        _transactions(),
        {"USD": 10, "EUR": 5},
        _rates(),
        allocated_foreign_cash={"USD": 10},
    ).by_currency.set_index("currency")

    assert unallocated.loc["USD", "import_funding_gap_fc"] == 40
    assert allocated.loc["USD", "import_funding_gap_fc"] == 30
    assert (
        allocated.loc["USD", "expected_total_economic_position"]
        == unallocated.loc["USD", "expected_total_economic_position"]
        == 20
    )


def test_unsupported_currency_fails_clearly():
    transactions = _transactions()
    transactions.loc[0, "currency"] = "JPY"
    with pytest.raises(ValueError, match="no FX rate provided for: JPY"):
        validate_transactions(transactions, _rates())
