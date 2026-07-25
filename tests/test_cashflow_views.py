from pathlib import Path

import pandas as pd

from src.cashflow import calculate_monthly_cashflow

SAMPLE_PATH = Path(__file__).parents[1] / "data" / "sample_transactions.csv"
COMMON = {
    "exchange_rate": 1_350,
    "monthly_fixed_krw_costs": 80_000_000,
    "beginning_krw_cash": 100_000_000,
}


def _cashflow(view: str, delay: bool = False) -> pd.DataFrame:
    transactions = pd.read_csv(SAMPLE_PATH)
    return calculate_monthly_cashflow(
        transactions,
        **COMMON,
        delay_transaction_id="EXP-001" if delay else None,
        delay_days=30 if delay else 0,
        cash_flow_view=view,
    ).set_index("year_month")


def test_committed_excludes_expected_export():
    result = _cashflow("committed")
    assert result.loc["2026-11", "export_inflows_krw"] == 0
    assert result["cash_flow_view"].unique().tolist() == ["committed"]


def test_expected_applies_probability_once():
    result = _cashflow("expected")
    assert result.loc["2026-11", "export_inflows_krw"] == 641_250_000


def test_realization_includes_full_expected_export():
    result = _cashflow("realization")
    assert result.loc["2026-11", "export_inflows_krw"] == 675_000_000


def test_downside_excludes_expected_export_inflow():
    result = _cashflow("downside")
    assert result.loc["2026-11", "export_inflows_krw"] == 0
    assert result.loc["2026-10", "import_outflows_krw"] == 297_000_000


def test_delay_moves_expected_export_only_from_november_to_december():
    baseline = _cashflow("expected")
    delayed = _cashflow("expected", delay=True)
    assert baseline.loc["2026-11", "export_inflows_krw"] == 641_250_000
    assert delayed.loc["2026-11", "export_inflows_krw"] == 0
    assert delayed.loc["2026-12", "export_inflows_krw"] == 641_250_000
    assert delayed.loc["2026-09", "transaction_cash_flow_krw"] == -40_500_000
    assert delayed.loc["2026-10", "transaction_cash_flow_krw"] == -297_000_000
