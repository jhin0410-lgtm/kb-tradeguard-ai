import pandas as pd
import pytest

from src.forward_rates import (
    build_forward_rate_table,
    calculate_theoretical_forward_rate,
)
from src.hedging import adjusted_forward_rate


@pytest.mark.parametrize(
    ("tenor", "expected"),
    [
        (1, 1347.7584059775843),
        (3, 1343.325092707046),
        (6, 1336.79706601467),
        (12, 1324.1626794258373),
    ],
)
def test_exact_usd_theoretical_forward_rates(tenor, expected):
    result = calculate_theoretical_forward_rate(1350.0, 0.025, 0.045, tenor)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize("tenor", [0, 2, -1, 24])
def test_invalid_tenor_fails(tenor):
    with pytest.raises(ValueError, match="tenor_months"):
        calculate_theoretical_forward_rate(1350.0, 0.025, 0.045, tenor)


def test_manual_quote_is_separate_and_does_not_overwrite_theoretical_rate():
    rates = pd.DataFrame(
        [["USD", 1350.0, 0.025, 0.045]],
        columns=[
            "currency",
            "spot_rate_krw",
            "krw_interest_rate",
            "foreign_interest_rate",
        ],
    )
    result = build_forward_rate_table(rates, (3,), {("USD", 3): 1400.0}).iloc[0]
    assert result["theoretical_forward_rate"] == pytest.approx(1343.325092707046)
    assert result["manual_bank_quote"] == 1400.0


def test_spread_direction_is_adverse_for_export_and_import():
    assert adjusted_forward_rate(1350, 10, "export") == 1340
    assert adjusted_forward_rate(1350, 10, "import") == 1360
