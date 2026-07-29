from datetime import date

import pandas as pd
import pytest

from src.fx_source_selection import select_fx_inputs


def _base_rates():
    return pd.DataFrame(
        [
            {
                "currency": "USD",
                "spot_rate_krw": 1350.0,
                "krw_interest_rate": 0.025,
                "foreign_interest_rate": 0.045,
            },
            {
                "currency": "EUR",
                "spot_rate_krw": 1580.0,
                "krw_interest_rate": 0.025,
                "foreign_interest_rate": 0.030,
            },
            {
                "currency": "JPY",
                "spot_rate_krw": 9.2,
                "krw_interest_rate": 0.025,
                "foreign_interest_rate": 0.010,
            },
        ]
    )


def _snapshot(*, include_eur=True):
    rows = [
        {
            "currency_unit": "USD",
            "currency_name": "미국 달러",
            "deal_base_rate": 1380.0,
            "telegraphic_transfer_buy": 1365.0,
            "telegraphic_transfer_sell": 1395.0,
        },
        {
            "currency_unit": "JPY(100)",
            "currency_name": "일본 옌",
            "deal_base_rate": 920.0,
            "telegraphic_transfer_buy": 910.0,
            "telegraphic_transfer_sell": 930.0,
        },
    ]
    if include_eur:
        rows.append(
            {
                "currency_unit": "EUR",
                "currency_name": "유로",
                "deal_base_rate": 1620.0,
                "telegraphic_transfer_buy": 1600.0,
                "telegraphic_transfer_sell": 1640.0,
            }
        )
    return {
        "observation_date": "20260724",
        "retrieved_at": "2026-07-25T16:02:23+00:00",
        "response_hash": "a" * 64,
        "results": rows,
    }


def test_bundled_selection_is_explicit_and_does_not_mutate_base():
    base = _base_rates()
    original = base.copy(deep=True)

    result = select_fx_inputs(base, ["USD", "EUR"], source="bundled")

    assert result.applied_source == "bundled"
    assert result.used_fallback is False
    assert set(result.rates["currency"]) == {"USD", "EUR"}
    assert set(result.rates["spot_source"]) == {"bundled sample spot assumption"}
    pd.testing.assert_frame_equal(base, original)


def test_kexim_replaces_only_spot_and_preserves_interest_assumptions():
    result = select_fx_inputs(
        _base_rates(),
        ["USD", "EUR"],
        source="kexim",
        as_of_date="2026-07-25",
        kexim_snapshot=_snapshot(),
    )
    rates = result.rates.set_index("currency")

    assert rates.loc["USD", "spot_rate_krw"] == pytest.approx(1380.0)
    assert rates.loc["EUR", "spot_rate_krw"] == pytest.approx(1620.0)
    assert rates.loc["USD", "krw_interest_rate"] == pytest.approx(0.025)
    assert rates.loc["USD", "foreign_interest_rate"] == pytest.approx(0.045)
    assert rates.loc["USD", "interest_rate_source"] == (
        "bundled sample interest-rate assumptions"
    )
    assert result.observation_date == "2026-07-24"
    assert result.stale_days == 1
    assert result.is_stale is False
    assert result.response_hash == "a" * 64


def test_kexim_jpy_100_is_normalized_to_one_yen():
    result = select_fx_inputs(
        _base_rates(),
        ["JPY"],
        source="kexim",
        as_of_date=date(2026, 7, 25),
        kexim_snapshot=_snapshot(),
    )
    assert result.rates.iloc[0]["spot_rate_krw"] == pytest.approx(9.2)


def test_kexim_stale_flag_uses_observation_date():
    result = select_fx_inputs(
        _base_rates(),
        ["USD"],
        source="kexim",
        as_of_date="2026-07-30",
        kexim_snapshot=_snapshot(),
        stale_after_days=3,
    )
    assert result.stale_days == 6
    assert result.is_stale is True
    assert bool(result.rates.iloc[0]["spot_is_stale"]) is True


def test_missing_required_official_currency_is_blocked():
    with pytest.raises(ValueError, match="missing required currencies: EUR"):
        select_fx_inputs(
            _base_rates(),
            ["USD", "EUR"],
            source="kexim",
            as_of_date="2026-07-25",
            kexim_snapshot=_snapshot(include_eur=False),
        )


def test_missing_required_currency_can_use_explicit_whole_table_fallback():
    result = select_fx_inputs(
        _base_rates(),
        ["USD", "EUR"],
        source="kexim",
        as_of_date="2026-07-25",
        kexim_snapshot=_snapshot(include_eur=False),
        allow_bundled_fallback=True,
    )
    rates = result.rates.set_index("currency")

    assert result.used_fallback is True
    assert result.applied_source == "bundled_fallback"
    assert "EUR" in result.fallback_reason
    assert rates.loc["USD", "spot_rate_krw"] == pytest.approx(1350.0)
    assert rates.loc["EUR", "spot_rate_krw"] == pytest.approx(1580.0)
    assert set(result.rates["spot_source"]) == {"bundled sample spot fallback"}


def test_unavailable_snapshot_can_use_explicit_fallback_reason():
    result = select_fx_inputs(
        _base_rates(),
        ["USD"],
        source="kexim",
        as_of_date="2026-07-25",
        kexim_snapshot=None,
        allow_bundled_fallback=True,
        fallback_reason="HTTP 503",
    )
    assert result.used_fallback is True
    assert result.fallback_reason == "HTTP 503"


def test_manual_source_requires_all_required_currencies():
    manual = _base_rates()[lambda frame: frame["currency"] == "USD"]
    with pytest.raises(ValueError, match="required currencies: EUR"):
        select_fx_inputs(
            _base_rates(),
            ["USD", "EUR"],
            source="manual",
            manual_rates=manual,
        )


def test_observation_after_as_of_is_rejected():
    with pytest.raises(ValueError, match="cannot be after"):
        select_fx_inputs(
            _base_rates(),
            ["USD"],
            source="kexim",
            as_of_date="2026-07-23",
            kexim_snapshot=_snapshot(),
        )
