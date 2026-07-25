import pandas as pd

from src.hedging import calculate_natural_hedge

COLUMNS = [
    "transaction_id",
    "transaction_type",
    "currency",
    "amount_fc",
    "probability",
    "status",
    "expected_date",
]


def test_bundled_gross_offset_is_not_maturity_matched_at_30_days():
    transactions = pd.read_csv("data/sample_transactions.csv")
    result = calculate_natural_hedge(
        transactions, {"USD": 40_000, "EUR": 10_000}, matching_window_days=30
    )
    usd = result.summary.set_index("currency").loc["USD"]
    assert usd["gross_currency_offset"] == 250_000
    assert usd["gross_currency_offset_ratio"] == 0.5
    assert usd["maturity_matched_offset"] == 0
    assert usd["maturity_matched_offset_ratio"] == 0
    assert result.matches.empty


def test_boundary_is_inclusive_and_partial_matching_reconciles():
    transactions = pd.DataFrame(
        [
            ["EXP-A", "export", "USD", 100, 1.0, "confirmed", "2026-10-31"],
            ["IMP-A", "import", "USD", 60, 1.0, "confirmed", "2026-10-01"],
            ["IMP-B", "import", "USD", 70, 1.0, "confirmed", "2026-11-01"],
        ],
        columns=COLUMNS,
    )
    result = calculate_natural_hedge(
        transactions, {"USD": 0}, matching_window_days=30
    )
    usd = result.summary.set_index("currency").loc["USD"]
    assert usd["gross_currency_offset"] == 100
    assert usd["maturity_matched_offset"] == 100
    assert usd["unmatched_exports"] == 0
    assert usd["unmatched_imports"] == 30
    assert result.matches["matched_amount_fc"].sum() == 100
    assert set(result.matches["timing_gap_days"]) == {1, 30}
    assert (result.matches["matched_amount_fc"] <= 70).all()


def test_one_day_outside_boundary_is_not_matched():
    transactions = pd.DataFrame(
        [
            ["EXP-A", "export", "USD", 100, 1.0, "confirmed", "2026-11-01"],
            ["IMP-A", "import", "USD", 100, 1.0, "confirmed", "2026-10-01"],
        ],
        columns=COLUMNS,
    )
    result = calculate_natural_hedge(
        transactions, {"USD": 0}, matching_window_days=30
    )
    assert result.summary.iloc[0]["maturity_matched_offset"] == 0
    assert result.matches.empty


def test_no_cross_currency_matching():
    transactions = pd.DataFrame(
        [
            ["EXP-U", "export", "USD", 100, 1.0, "confirmed", "2026-10-01"],
            ["IMP-E", "import", "EUR", 100, 1.0, "confirmed", "2026-10-01"],
        ],
        columns=COLUMNS,
    )
    result = calculate_natural_hedge(
        transactions, {"USD": 0, "EUR": 0}, matching_window_days=30
    )
    assert result.summary["maturity_matched_offset"].sum() == 0
    assert result.matches.empty
