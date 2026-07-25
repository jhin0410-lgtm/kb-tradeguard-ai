import json
from datetime import date

import pytest

from src.data_providers import (
    BOKECOSProvider,
    KEXIMFXProvider,
    OpenDARTProvider,
    ProviderConfigurationError,
    ProviderResponseError,
)
from src.data_providers.opendart import normalize_corp_code


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def test_bok_key_statistics_normalizes_rows_and_provenance():
    captured = {}

    def transport(url, headers, timeout):
        captured.update(url=url, headers=headers, timeout=timeout)
        return _json_bytes(
            {
                "KeyStatisticList": {
                    "list_total_count": 1,
                    "row": [
                        {
                            "CLASS_NAME": "시장금리",
                            "KEYSTAT_NAME": "한국은행 기준금리",
                            "DATA_VALUE": "2.50",
                            "CYCLE": "202607",
                            "UNIT_NAME": "%",
                        }
                    ],
                }
            }
        )

    result = BOKECOSProvider(
        api_key="test-key", transport=transport
    ).get_key_statistics(1, 1)

    assert "/KeyStatisticList/test-key/json/kr/1/1" in captured["url"]
    assert captured["headers"]["Accept"] == "application/json"
    assert result["results"][0]["stat_name"] == "한국은행 기준금리"
    assert len(result["response_hash"]) == 64


def test_bok_missing_key_fails_before_transport(monkeypatch):
    monkeypatch.delenv("BOK_ECOS_API_KEY", raising=False)
    provider = BOKECOSProvider(api_key="")
    with pytest.raises(ProviderConfigurationError, match="BOK_ECOS_API_KEY"):
        provider.get_key_statistics()


def test_bok_provider_error_payload_is_rejected():
    provider = BOKECOSProvider(
        api_key="test",
        transport=lambda *args: _json_bytes(
            {"RESULT": {"CODE": "ERROR-100", "MESSAGE": "invalid request"}}
        ),
    )
    with pytest.raises(ProviderResponseError, match="ERROR-100"):
        provider.get_key_statistics()


def test_kexim_rate_snapshot_parses_numbers_and_preserves_unit():
    captured = {}

    def transport(url, headers, timeout):
        captured["url"] = url
        return _json_bytes(
            [
                {
                    "result": 1,
                    "cur_unit": "JPY(100)",
                    "cur_nm": "일본 옌",
                    "ttb": "910.25",
                    "tts": "928.64",
                    "deal_bas_r": "919.45",
                    "bkpr": "919",
                    "yy_efee_r": "0",
                    "ten_dd_efee_r": "0",
                    "kftc_deal_bas_r": "919.45",
                    "kftc_bkpr": "919",
                }
            ]
        )

    result = KEXIMFXProvider(api_key="test/key", transport=transport).fetch_rates(
        "2026-07-24"
    )

    assert "searchdate=20260724" in captured["url"]
    assert "data=AP01" in captured["url"]
    assert result["observation_date"] == "20260724"
    assert result["results"][0]["currency_unit"] == "JPY(100)"
    assert result["results"][0]["deal_base_rate"] == pytest.approx(919.45)


def test_kexim_latest_rates_walks_back_over_empty_dates():
    calls = []

    def transport(url, headers, timeout):
        calls.append(url)
        if "searchdate=20260726" in url:
            return b"[]"
        return _json_bytes(
            [{"result": 1, "cur_unit": "USD", "cur_nm": "미국 달러", "deal_bas_r": "1,350.50"}]
        )

    result = KEXIMFXProvider(api_key="test", transport=transport).fetch_latest_rates(
        date(2026, 7, 26), lookback_days=2
    )

    assert len(calls) == 2
    assert result["observation_date"] == "20260725"
    assert result["lookback_days_used"] == 1
    assert result["results"][0]["deal_base_rate"] == pytest.approx(1350.50)


def test_kexim_rejects_invalid_date():
    provider = KEXIMFXProvider(api_key="test", transport=lambda *args: b"[]")
    with pytest.raises(ValueError, match="YYYYMMDD"):
        provider.fetch_rates("2026/07/24")


def test_kexim_list_wrapped_provider_error_is_rejected():
    provider = KEXIMFXProvider(
        api_key="bad",
        transport=lambda *args: _json_bytes([{"result": 3}]),
    )
    with pytest.raises(ProviderResponseError, match="authentication key error"):
        provider.fetch_rates("20260724")


def test_opendart_company_profile_is_normalized():
    captured = {}

    def transport(url, headers, timeout):
        captured["url"] = url
        return _json_bytes(
            {
                "status": "000",
                "message": "정상",
                "corp_code": "00126380",
                "corp_name": "삼성전자",
                "corp_name_eng": "SAMSUNG ELECTRONICS CO., LTD.",
                "stock_code": "005930",
                "ceo_nm": "대표이사",
                "corp_cls": "Y",
                "bizr_no": "1248100998",
                "induty_code": "264",
                "est_dt": "19690113",
                "acc_mt": "12",
            }
        )

    result = OpenDARTProvider(api_key="x" * 40, transport=transport).get_company(
        "00126380"
    )

    assert "company.json?" in captured["url"]
    assert "corp_code=00126380" in captured["url"]
    assert result["results"]["corp_name"] == "삼성전자"
    assert result["results"]["bizr_no"] == "1248100998"


def test_opendart_financial_no_data_is_empty_not_fabricated():
    provider = OpenDARTProvider(
        api_key="x" * 40,
        transport=lambda *args: _json_bytes(
            {"status": "013", "message": "조회된 데이터가 없습니다."}
        ),
    )
    result = provider.get_financial_statements("00126380", 2026)
    assert result["results"] == []
    assert result["business_year"] == "2026"


def test_opendart_authentication_error_is_rejected():
    provider = OpenDARTProvider(
        api_key="bad",
        transport=lambda *args: _json_bytes(
            {"status": "010", "message": "등록되지 않은 키입니다."}
        ),
    )
    with pytest.raises(ProviderResponseError, match="010"):
        provider.get_company("00126380")


@pytest.mark.parametrize("value", ["", "123", "001263800", "abcdefgh"])
def test_opendart_corp_code_validation(value):
    with pytest.raises(ValueError, match="8 digits"):
        normalize_corp_code(value)
