from pathlib import Path

import pandas as pd

from src.cashflow import calculate_monthly_cashflow

SAMPLE_PATH = Path(__file__).parents[1] / "data" / "sample_transactions.csv"


def test_default_horizon_starts_at_earliest_transaction_without_august():
    transactions = pd.read_csv(SAMPLE_PATH)
    cashflow = calculate_monthly_cashflow(
        transactions=transactions,
        exchange_rate=1_350,
        monthly_fixed_krw_costs=80_000_000,
        beginning_krw_cash=100_000_000,
    )

    assert cashflow["year_month"].tolist() == ["2026-09", "2026-10", "2026-11"]
    assert cashflow.iloc[0]["year_month"] == "2026-09"
    assert "2026-08" not in cashflow["year_month"].tolist()


def test_thirty_day_delay_moves_export_and_changes_november_and_december():
    transactions = pd.read_csv(SAMPLE_PATH)
    common = {
        "transactions": transactions,
        "exchange_rate": 1_350,
        "monthly_fixed_krw_costs": 80_000_000,
        "beginning_krw_cash": 100_000_000,
    }

    baseline = calculate_monthly_cashflow(**common).set_index("year_month")
    delayed = calculate_monthly_cashflow(
        **common, delay_transaction_id="EXP-001", delay_days=30
    ).set_index("year_month")

    assert baseline.loc["2026-11", "export_inflows_krw"] == 641_250_000
    assert delayed.loc["2026-11", "export_inflows_krw"] == 0
    assert delayed.loc["2026-12", "export_inflows_krw"] == 641_250_000
    assert baseline.loc["2026-11", "ending_cash_krw"] == 163_750_000
    assert delayed.loc["2026-11", "ending_cash_krw"] == -477_500_000
    assert delayed.loc["2026-12", "ending_cash_krw"] == 83_750_000
