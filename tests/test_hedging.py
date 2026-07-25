import pytest

from src.hedging import compare_hedge_ratios


def _comparison(exposure_type="export", spread=0):
    return compare_hedge_ratios(
        "USD",
        100,
        exposure_type,
        spot_rate=1000,
        forward_rate=990,
        spread=spread,
        hedge_ratios=[0, 0.5, 1],
        scenario_percentages=[-0.1, 0, 0.1],
    )


def test_zero_percent_hedge_equals_unhedged_scenario_value():
    result = _comparison()
    zero = result[result["hedge_ratio"] == 0].set_index("scenario_pct")
    assert zero.loc[-0.1, "total_krw_value"] == 90_000
    assert zero.loc[0.0, "total_krw_value"] == 100_000
    assert zero.loc[0.1, "total_krw_value"] == 110_000


def test_full_hedge_is_spot_insensitive_before_spread_costs():
    full = _comparison().query("hedge_ratio == 1")
    assert full["total_krw_value"].tolist() == [99_000, 99_000, 99_000]


def test_half_hedge_combines_forward_and_spot():
    result = _comparison()
    row = result[
        (result["hedge_ratio"] == 0.5) & (result["scenario_pct"] == 0.1)
    ].iloc[0]
    assert row["forward_locked_krw"] == 49_500
    assert row["unhedged_krw_value"] == 55_000
    assert row["total_krw_value"] == 104_500


def test_export_and_import_signed_directions_are_opposite():
    export = _comparison("export").query(
        "hedge_ratio == 1 and scenario_pct == 0"
    ).iloc[0]
    import_row = _comparison("import").query(
        "hedge_ratio == 1 and scenario_pct == 0"
    ).iloc[0]
    assert export["signed_total_krw"] == 99_000
    assert import_row["signed_total_krw"] == -99_000


def test_spread_reduces_export_proceeds_and_increases_import_payment():
    export = _comparison("export", spread=10).query(
        "hedge_ratio == 1 and scenario_pct == 0"
    ).iloc[0]
    import_row = _comparison("import", spread=10).query(
        "hedge_ratio == 1 and scenario_pct == 0"
    ).iloc[0]
    assert export["total_krw_value"] == 98_000
    assert import_row["total_krw_value"] == 100_000
