from urllib.parse import parse_qs, urlparse

import pytest

from src.data_providers.base import ProviderConfigurationError, ProviderResponseError
from src.data_providers.korea_customs_trade import (
    KoreaCustomsTradeProvider,
    normalize_country_code,
    normalize_hs_code,
)


_SAMPLE_XML = b"""<?xml version='1.0' encoding='UTF-8'?>
<response>
  <header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header>
  <body>
    <items>
      <item>
        <year>2026.01</year>
        <statCdCntnKor1>베트남</statCdCntnKor1>
        <statCd>VN</statCd>
        <statKor>전자부품</statKor>
        <hsCd>8542</hsCd>
        <expWgt>12,300</expWgt>
        <expDlr>456789</expDlr>
        <impWgt>7000</impWgt>
        <impDlr>123456</impDlr>
        <balPayments>333333</balPayments>
      </item>
    </items>
  </body>
</response>"""


def test_customs_provider_requires_a_service_key():
    provider = KoreaCustomsTradeProvider(api_key="")

    with pytest.raises(ProviderConfigurationError, match="KCS_TRADE_API_KEY"):
        provider.get_country_product_trade(
            start_yymm="202601",
            end_yymm="202601",
            country_code="VN",
        )


def test_customs_provider_parses_official_country_product_rows_and_provenance():
    captured = {}

    def transport(url, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _SAMPLE_XML

    provider = KoreaCustomsTradeProvider(api_key="encoded%2Fkey", transport=transport)
    snapshot = provider.get_country_product_trade(
        start_yymm="202601",
        end_yymm="202603",
        country_code="vn",
        hs_code="8542",
    )

    query = parse_qs(urlparse(captured["url"]).query)
    assert query["serviceKey"] == ["encoded/key"]
    assert query["strtYymm"] == ["202601"]
    assert query["endYymm"] == ["202603"]
    assert query["cntyCd"] == ["VN"]
    assert query["hsSgn"] == ["8542"]
    assert captured["headers"] == {"Accept": "application/xml"}
    assert snapshot["provider"] == "Korea Customs Service trade-statistics API"
    assert snapshot["request"] == {
        "start_yymm": "202601",
        "end_yymm": "202603",
        "country_code": "VN",
        "hs_code": "8542",
    }
    assert snapshot["results"] == [
        {
            "period": "2026.01",
            "country_name_ko": "베트남",
            "country_code": "VN",
            "product_name_ko": "전자부품",
            "hs_code": "8542",
            "export_weight_kg": 12300,
            "export_value_usd": 456789,
            "import_weight_kg": 7000,
            "import_value_usd": 123456,
            "trade_balance_usd": 333333,
        }
    ]
    assert len(snapshot["response_hash"]) == 64
    assert any("Aggregate customs statistics" in item for item in snapshot["limitations"])


def test_customs_provider_rejects_invalid_query_scope():
    provider = KoreaCustomsTradeProvider(api_key="test", transport=lambda *_: _SAMPLE_XML)

    with pytest.raises(ValueError, match="twelve months"):
        provider.get_country_product_trade(
            start_yymm="202501",
            end_yymm="202601",
            country_code="VN",
        )
    with pytest.raises(ValueError, match="start_yymm"):
        provider.get_country_product_trade(
            start_yymm="202602",
            end_yymm="202601",
            country_code="VN",
        )
    with pytest.raises(ValueError, match="calendar month"):
        provider.get_country_product_trade(
            start_yymm="202613",
            end_yymm="202613",
            country_code="VN",
        )


def test_customs_normalizers_reject_ambiguous_codes():
    assert normalize_country_code(" us ") == "US"
    assert normalize_hs_code("8542") == "8542"
    assert normalize_hs_code("") is None

    with pytest.raises(ValueError, match="two-letter"):
        normalize_country_code("USA")
    with pytest.raises(ValueError, match="2, 4, 6, or 10"):
        normalize_hs_code("85421")


def test_customs_provider_rejects_non_success_result_codes():
    error_xml = b"""<response><header><resultCode>99</resultCode><resultMsg>FAILED</resultMsg></header></response>"""
    provider = KoreaCustomsTradeProvider(api_key="test", transport=lambda *_: error_xml)

    with pytest.raises(ProviderResponseError, match="result 99"):
        provider.get_country_product_trade(
            start_yymm="202601",
            end_yymm="202601",
            country_code="VN",
        )
