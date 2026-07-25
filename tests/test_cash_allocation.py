import pandas as pd
import pytest

from src.cash_allocation import allocate_foreign_cash
from src.exposure import calculate_exposure

TRANSACTIONS = pd.read_csv("data/sample_transactions.csv")
COLUMNS = ["currency", "transaction_id", "allocation_amount", "allocation_date"]


def test_partial_import_funding_and_unallocated_cash():
    allocations = pd.DataFrame(
        [["USD", "IMP-001", 25_000, "2026-09-01"]], columns=COLUMNS
    )
    result = allocate_foreign_cash(
        TRANSACTIONS, {"USD": 40_000, "EUR": 10_000}, allocations
    )
    gaps = result.import_funding_gap_by_transaction.set_index("transaction_id")
    cash = result.unallocated_foreign_cash.set_index("currency")
    assert gaps.loc["IMP-001", "import_funding_gap_fc"] == 195_000
    assert gaps.loc["IMP-002", "import_funding_gap_fc"] == 30_000
    assert cash.loc["USD", "unallocated_foreign_cash"] == 15_000
    assert cash.loc["EUR", "unallocated_foreign_cash"] == 10_000


def test_overallocation_and_duplicate_cash_use_fail():
    allocations = pd.DataFrame(
        [
            ["USD", "IMP-001", 30_000, "2026-09-01"],
            ["USD", "IMP-002", 20_000, "2026-09-02"],
        ],
        columns=COLUMNS,
    )
    with pytest.raises(ValueError, match="exceeds available"):
        allocate_foreign_cash(
            TRANSACTIONS, {"USD": 40_000, "EUR": 10_000}, allocations
        )


def test_cross_currency_and_obligation_overallocation_fail():
    wrong_currency = pd.DataFrame(
        [["EUR", "IMP-001", 1_000, "2026-09-01"]], columns=COLUMNS
    )
    with pytest.raises(ValueError, match="does not match"):
        allocate_foreign_cash(
            TRANSACTIONS, {"USD": 40_000, "EUR": 10_000}, wrong_currency
        )
    too_much = pd.DataFrame(
        [["USD", "IMP-002", 31_000, "2026-09-01"]], columns=COLUMNS
    )
    with pytest.raises(ValueError, match="exceeds import obligation"):
        allocate_foreign_cash(
            TRANSACTIONS, {"USD": 40_000, "EUR": 10_000}, too_much
        )


def test_allocation_does_not_change_transaction_or_economic_exposure():
    rates = pd.read_csv("data/sample_fx_rates.csv")
    before = calculate_exposure(
        TRANSACTIONS, {"USD": 40_000, "EUR": 10_000}, rates
    ).by_currency.set_index("currency")
    allocate_foreign_cash(
        TRANSACTIONS,
        {"USD": 40_000, "EUR": 10_000},
        pd.DataFrame(
            [["USD", "IMP-001", 25_000, "2026-09-01"]], columns=COLUMNS
        ),
    )
    after = calculate_exposure(
        TRANSACTIONS, {"USD": 40_000, "EUR": 10_000}, rates
    ).by_currency.set_index("currency")
    assert before.loc["USD", "expected_transaction_exposure"] == 225_000
    assert after.loc["USD", "expected_transaction_exposure"] == 225_000
    assert before.loc["USD", "expected_total_economic_position"] == 265_000
    assert after.loc["USD", "expected_total_economic_position"] == 265_000
