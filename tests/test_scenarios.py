import pytest

from src.scenarios import calculate_scenarios


def test_minus_five_base_and_plus_five_scenarios():
    result = calculate_scenarios(
        net_exposure=185_000,
        base_exchange_rate=1_350,
        scenario_percentages=[-0.05, 0.0, 0.05],
    ).set_index("scenario_pct")

    assert result.loc[-0.05, "exchange_rate"] == pytest.approx(1_282.5)
    assert result.loc[0.00, "exchange_rate"] == pytest.approx(1_350)
    assert result.loc[0.05, "exchange_rate"] == pytest.approx(1_417.5)
    assert result.loc[-0.05, "net_exposure_krw"] == pytest.approx(237_262_500)
    assert result.loc[0.00, "net_exposure_krw"] == pytest.approx(249_750_000)
    assert result.loc[0.05, "net_exposure_krw"] == pytest.approx(262_237_500)
    assert result.loc[-0.05, "change_vs_base_krw"] == pytest.approx(-12_487_500)
    assert result.loc[0.00, "change_vs_base_krw"] == pytest.approx(0)
    assert result.loc[0.05, "change_vs_base_krw"] == pytest.approx(12_487_500)
