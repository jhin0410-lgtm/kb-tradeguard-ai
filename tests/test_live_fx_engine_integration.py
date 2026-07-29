import pandas as pd
import pytest

from src.cashflow import calculate_monthly_cashflow
from src.exposure import calculate_exposure
from src.fx_source_selection import select_fx_inputs
from src.portfolio_hedging import calculate_transaction_level_portfolio_hedge


def test_kexim_spot_propagates_to_exposure_cashflow_and_hedge_engine():
    base_rates = pd.DataFrame(
        [
            {
                "currency": "USD",
                "spot_rate_krw": 1350.0,
                "krw_interest_rate": 0.025,
                "foreign_interest_rate": 0.045,
            }
        ]
    )
    snapshot = {
        "observation_date": "20260724",
        "retrieved_at": "2026-07-25T16:02:23+00:00",
        "response_hash": "a" * 64,
        "results": [
            {
                "currency_unit": "USD",
                "currency_name": "미국 달러",
                "deal_base_rate": 1380.0,
                "telegraphic_transfer_buy": 1365.0,
                "telegraphic_transfer_sell": 1395.0,
            }
        ],
    }
    transactions = pd.DataFrame(
        [
            {
                "transaction_id": "EXP-1",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 100.0,
                "probability": 1.0,
                "status": "confirmed",
                "expected_date": "2026-11-30",
            }
        ]
    )

    selection = select_fx_inputs(
        base_rates,
        ["USD"],
        source="kexim",
        as_of_date="2026-07-25",
        kexim_snapshot=snapshot,
    )

    exposure = calculate_exposure(transactions, {}, selection.rates)
    assert exposure.by_currency.iloc[0]["spot_rate_krw"] == pytest.approx(1380.0)
    assert exposure.by_currency.iloc[0][
        "expected_transaction_exposure_krw"
    ] == pytest.approx(138000.0)

    cashflow = calculate_monthly_cashflow(
        transactions,
        {"USD": 1380.0},
        monthly_fixed_krw_costs=1000.0,
        beginning_krw_cash=10000.0,
        cash_flow_view="expected",
    )
    assert cashflow.iloc[0]["export_inflows_krw"] == pytest.approx(138000.0)
    assert cashflow.iloc[0]["ending_cash_krw"] == pytest.approx(147000.0)

    hedge = calculate_transaction_level_portfolio_hedge(
        transactions,
        selection.rates,
        "2026-07-25",
        hedge_ratios={"USD": 0.5},
        scenario_percentages=(0.0,),
        exposure_measure="expected",
    )
    row = hedge.transaction_results.iloc[0]
    assert row["terminal_spot_rate"] == pytest.approx(1380.0)
    assert row["hedged_amount_fc"] == pytest.approx(50.0)
    assert row["theoretical_forward_rate"] != pytest.approx(1380.0)
    assert selection.rates.iloc[0]["interest_rate_source"] == (
        "bundled sample interest-rate assumptions"
    )
