import pandas as pd
import pytest

from src.maturity_buckets import assign_maturity_bucket, build_maturity_bucket_exposure
from src.portfolio_hedging import (
    calculate_maturity_bucket_portfolio_hedge,
    calculate_transaction_level_portfolio_hedge,
)

TRANSACTIONS = pd.read_csv("data/sample_transactions.csv")
RATES = pd.read_csv("data/sample_fx_rates.csv")
AS_OF = "2026-08-31"


@pytest.mark.parametrize(
    ("days", "bucket"),
    [
        (1, "0-30 days"),
        (30, "0-30 days"),
        (31, "31-90 days"),
        (90, "31-90 days"),
        (91, "91-180 days"),
        (180, "91-180 days"),
        (181, "181-365 days"),
        (365, "181-365 days"),
        (366, "over 365 days"),
    ],
)
def test_bucket_boundaries_are_inclusive_and_deterministic(days, bucket):
    assert assign_maturity_bucket(days) == bucket


def test_transaction_level_rates_differ_and_reconcile_exactly():
    result = calculate_transaction_level_portfolio_hedge(
        TRANSACTIONS, RATES, AS_OF, hedge_ratios=0.5, scenario_percentages=[0]
    )
    rows = result.transaction_results
    assert rows["theoretical_forward_rate"].nunique() == 3
    assert rows.loc[
        rows["transaction_id"] == "EXP-001", "theoretical_forward_rate"
    ].iloc[0] == pytest.approx(1343.3431772307943, rel=1e-12)
    assert result.portfolio_scenario_totals.iloc[0]["signed_total_krw"] == pytest.approx(
        rows["signed_total_krw"].sum(), rel=1e-12
    )
    assert result.currency_scenario_totals.iloc[0]["signed_total_krw"] == pytest.approx(
        rows["signed_total_krw"].sum(), rel=1e-12
    )


def test_export_and_import_signs_and_positive_import_payments():
    result = calculate_transaction_level_portfolio_hedge(
        TRANSACTIONS, RATES, AS_OF, hedge_ratios=0, scenario_percentages=[0]
    ).transaction_results.set_index("transaction_id")
    assert result.loc["EXP-001", "signed_exposure_fc"] == 475_000
    assert result.loc["IMP-001", "signed_exposure_fc"] == -220_000
    assert result.loc["IMP-001", "total_krw_amount"] == 297_000_000
    assert result.loc["IMP-001", "signed_total_krw"] == -297_000_000


def test_full_hedge_removes_spot_sensitivity_per_transaction():
    result = calculate_transaction_level_portfolio_hedge(
        TRANSACTIONS,
        RATES,
        AS_OF,
        hedge_ratios=1,
        scenario_percentages=[-0.1, 0.1],
    ).transaction_results
    for _, rows in result.groupby("transaction_id"):
        assert rows["total_krw_amount"].nunique() == 1


def test_partial_hedge_uses_forward_and_terminal_spot_constants():
    result = calculate_transaction_level_portfolio_hedge(
        TRANSACTIONS, RATES, AS_OF, hedge_ratios=0.5, scenario_percentages=[0]
    ).transaction_results.set_index("transaction_id")
    export = result.loc["EXP-001"]
    assert export["hedged_amount_fc"] == 237_500
    assert export["unhedged_amount_fc"] == 237_500
    assert export["forward_locked_krw"] == pytest.approx(
        319_044_004.59231365, rel=1e-12
    )
    assert export["unhedged_terminal_krw"] == 320_625_000
    assert export["total_krw_amount"] == pytest.approx(
        639_669_004.5923136, rel=1e-12
    )


def test_bucket_summary_and_transaction_results_reconcile():
    exposure = build_maturity_bucket_exposure(TRANSACTIONS, RATES, AS_OF).summary
    assert exposure.set_index("maturity_bucket").loc[
        "0-30 days", "expected_import_exposure"
    ] == 30_000
    assert exposure.set_index("maturity_bucket").loc[
        "31-90 days", "expected_import_exposure"
    ] == 220_000
    assert exposure.set_index("maturity_bucket").loc[
        "91-180 days", "expected_export_exposure"
    ] == 475_000

    result = calculate_maturity_bucket_portfolio_hedge(
        TRANSACTIONS, RATES, AS_OF, hedge_ratios=0.5, scenario_percentages=[0]
    )
    assert result.bucket_summary["selected_hedge_amount_fc"].sum() == 362_500
    assert result.portfolio_scenario_totals.iloc[0]["signed_total_krw"] == pytest.approx(
        result.transaction_results["signed_total_krw"].sum(), rel=1e-12
    )


def test_currencies_are_aggregated_separately_before_portfolio_total():
    transactions = pd.concat(
        [
            TRANSACTIONS,
            pd.DataFrame(
                [
                    {
                        "transaction_id": "EUR-EXP",
                        "transaction_type": "export",
                        "currency": "EUR",
                        "amount_fc": 1_000,
                        "probability": 1.0,
                        "status": "confirmed",
                        "expected_date": "2026-10-01",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    result = calculate_transaction_level_portfolio_hedge(
        transactions, RATES, AS_OF, hedge_ratios=0, scenario_percentages=[0]
    )
    assert set(result.currency_scenario_totals["currency"]) == {"USD", "EUR"}
    assert result.portfolio_scenario_totals.iloc[0]["signed_total_krw"] == (
        result.currency_scenario_totals["signed_total_krw"].sum()
    )
