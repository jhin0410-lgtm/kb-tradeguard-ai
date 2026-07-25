import pandas as pd

from src.hedging import calculate_natural_hedge


def test_natural_offset_is_currency_specific_and_cash_is_separate():
    transactions = pd.DataFrame(
        [
            ["U-E", "export", "USD", 100, 1.0, "confirmed", "2026-09-01"],
            ["U-I", "import", "USD", 60, 1.0, "confirmed", "2026-09-02"],
            ["E-E", "export", "EUR", 20, 1.0, "confirmed", "2026-09-03"],
            ["E-I", "import", "EUR", 50, 1.0, "confirmed", "2026-09-04"],
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
    natural = calculate_natural_hedge(
        transactions, {"USD": 10, "EUR": 5}
    )
    result = natural.summary.set_index("currency")

    assert result.loc["USD", "gross_currency_offset"] == 60
    assert result.loc["USD", "maturity_matched_offset"] == 60
    assert result.loc["USD", "foreign_cash"] == 10
    assert result.loc["EUR", "gross_currency_offset"] == 20
    assert result.loc["EUR", "maturity_matched_offset"] == 20
    assert result.loc["EUR", "foreign_cash"] == 5
    assert natural.matches.groupby("currency")["matched_amount_fc"].sum().to_dict() == {
        "EUR": 20,
        "USD": 60,
    }
