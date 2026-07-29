import pytest

from src.data_providers import ProviderResponseError
from src.official_data_views import (
    build_dart_company_frame,
    build_ecos_key_statistics_frame,
    build_kexim_rate_frame,
    parse_currency_unit,
)


def test_parse_currency_unit_preserves_quote_multiplier():
    assert parse_currency_unit("USD") == ("USD", 1)
    assert parse_currency_unit("JPY(100)") == ("JPY", 100)


@pytest.mark.parametrize("value", ["", "US", "USD(0)", "KRW/USD", "JPY(x)"])
def test_parse_currency_unit_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        parse_currency_unit(value)


def test_kexim_frame_normalizes_jpy_to_one_currency_unit():
    snapshot = {
        "observation_date": "20260724",
        "retrieved_at": "2026-07-25T16:00:00+00:00",
        "source_url": "official",
        "response_hash": "a" * 64,
        "results": [
            {
                "currency_unit": "JPY(100)",
                "currency_name": "일본 옌",
                "deal_base_rate": 919.45,
                "telegraphic_transfer_buy": 910.25,
                "telegraphic_transfer_sell": 928.64,
            }
        ],
    }

    row = build_kexim_rate_frame(snapshot).iloc[0]

    assert row["currency"] == "JPY"
    assert row["quotation_unit"] == 100
    assert row["deal_base_rate_raw"] == pytest.approx(919.45)
    assert row["spot_rate_krw_per_unit"] == pytest.approx(9.1945)
    assert row["telegraphic_transfer_buy_per_unit"] == pytest.approx(9.1025)
    assert row["telegraphic_transfer_sell_per_unit"] == pytest.approx(9.2864)
    assert row["response_hash"] == "a" * 64


def test_kexim_frame_rejects_missing_results():
    with pytest.raises(ProviderResponseError, match="results list"):
        build_kexim_rate_frame({})


def test_ecos_frame_attaches_source_metadata():
    snapshot = {
        "retrieved_at": "2026-07-25T16:00:00+00:00",
        "source_url": "official",
        "response_hash": "b" * 64,
        "results": [
            {
                "class_name": "시장금리",
                "stat_name": "한국은행 기준금리",
                "data_value": "2.50",
                "cycle": "202607",
                "unit_name": "%",
            }
        ],
    }
    row = build_ecos_key_statistics_frame(snapshot).iloc[0]
    assert row["stat_name"] == "한국은행 기준금리"
    assert row["source_url"] == "official"
    assert row["response_hash"] == "b" * 64


def test_dart_company_frame_is_one_row_with_provenance():
    snapshot = {
        "retrieved_at": "2026-07-25T16:00:00+00:00",
        "source_url": "official",
        "response_hash": "c" * 64,
        "results": {"corp_code": "00126380", "corp_name": "삼성전자"},
    }
    frame = build_dart_company_frame(snapshot)
    assert len(frame) == 1
    assert frame.iloc[0]["corp_name"] == "삼성전자"
    assert frame.iloc[0]["response_hash"] == "c" * 64
