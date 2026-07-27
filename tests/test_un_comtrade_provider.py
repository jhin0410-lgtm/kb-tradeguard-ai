import json
from urllib.parse import parse_qs, urlparse

import pytest

from src.data_providers.base import ProviderResponseError
from src.data_providers.un_comtrade import UNComtradePreviewProvider, country_to_m49


SAMPLE = {
    "data": [
        {
            "period": "2023",
            "reporterCode": 410,
            "reporterISO": "KOR",
            "reporterDesc": "Rep. of Korea",
            "partnerCode": 704,
            "partnerISO": "VNM",
            "partnerDesc": "Viet Nam",
            "flowCode": "X",
            "flowDesc": "Export",
            "cmdCode": "8542",
            "cmdDesc": "Electronic integrated circuits",
            "primaryValue": 1200000,
            "fobvalue": 1200000,
            "netWgt": 3400,
            "qty": 120,
            "qtyUnitAbbr": "u",
            "isReported": True,
            "isAggregate": True,
        }
    ]
}


def test_country_lookup_accepts_iso_and_m49():
    assert country_to_m49("KR") == 410
    assert country_to_m49("VN") == 704
    assert country_to_m49(0) == 0
    with pytest.raises(ValueError):
        country_to_m49("ZZ")


def test_preview_query_and_normalized_result():
    captured = {}

    def transport(url, headers, timeout):
        captured.update(url=url, headers=headers, timeout=timeout)
        return json.dumps(SAMPLE).encode("utf-8")

    snapshot = UNComtradePreviewProvider(transport=transport).get_trade_snapshot(
        period="2023",
        reporter="KR",
        partner="VN",
        hs_code="8542",
        max_records=25,
    )

    query = parse_qs(urlparse(captured["url"]).query)
    assert query["reporterCode"] == ["410"]
    assert query["partnerCode"] == ["704"]
    assert query["cmdCode"] == ["8542"]
    assert query["maxRecords"] == ["25"]
    row = snapshot["results"][0]
    assert row["reporter_iso"] == "KOR"
    assert row["partner_iso"] == "VNM"
    assert row["primary_value_usd"] == 1200000
    assert row["net_weight_kg"] == 3400
    assert len(snapshot["response_hash"]) == 64


def test_preview_validates_scope():
    provider = UNComtradePreviewProvider(
        transport=lambda *_: json.dumps({"data": []}).encode("utf-8")
    )
    with pytest.raises(ValueError):
        provider.get_trade_snapshot(period="202301", frequency="A")
    with pytest.raises(ValueError):
        provider.get_trade_snapshot(period="202313", frequency="M")
    with pytest.raises(ValueError):
        provider.get_trade_snapshot(period="2023", hs_code="85421")
    with pytest.raises(ValueError):
        provider.get_trade_snapshot(period="2023", max_records=501)


def test_preview_rejects_bad_data_shape():
    provider = UNComtradePreviewProvider(
        transport=lambda *_: json.dumps({"data": {}}).encode("utf-8")
    )
    with pytest.raises(ProviderResponseError):
        provider.get_trade_snapshot(period="2023")
