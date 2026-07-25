import pandas as pd
import pytest

from src.forward_rates import build_settlement_forward_table


def test_act_365_is_exact_and_transaction_tenors_differ():
    result = build_settlement_forward_table(
        pd.read_csv("data/sample_transactions.csv"),
        pd.read_csv("data/sample_fx_rates.csv"),
        "2026-08-31",
    ).set_index("transaction_id")

    assert result.loc["IMP-002", "tenor_days"] == 30
    assert result.loc["IMP-001", "tenor_days"] == 45
    assert result.loc["EXP-001", "tenor_days"] == 91
    assert result.loc["IMP-002", "tenor_years"] == pytest.approx(30 / 365)
    assert result.loc["IMP-001", "tenor_years"] == pytest.approx(45 / 365)
    assert result.loc["EXP-001", "tenor_years"] == pytest.approx(91 / 365)
    assert result.loc["IMP-002", "theoretical_forward_rate"] == pytest.approx(
        1347.7889995905555, rel=1e-12
    )
    assert result.loc["IMP-001", "theoretical_forward_rate"] == pytest.approx(
        1346.6895988011715, rel=1e-12
    )
    assert result.loc["EXP-001", "theoretical_forward_rate"] == pytest.approx(
        1343.3431772307943, rel=1e-12
    )


def test_missing_or_nonpositive_settlement_tenor_fails():
    transactions = pd.read_csv("data/sample_transactions.csv")
    rates = pd.read_csv("data/sample_fx_rates.csv")
    with pytest.raises(ValueError, match="as_of_date is required"):
        build_settlement_forward_table(transactions, rates, None)
    with pytest.raises(ValueError, match="must be after as_of_date"):
        build_settlement_forward_table(transactions, rates, "2026-09-30")
