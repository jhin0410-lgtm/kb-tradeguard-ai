import json

import pytest

from src.data_providers import (
    NTSBusinessStatusProvider,
    ProviderConfigurationError,
    ProviderResponseError,
)
from src.data_providers.nts_business import (
    _TransportRequestError,
    normalize_business_number,
)


def test_normalize_business_number_removes_separators():
    assert normalize_business_number("123-45-67890") == "1234567890"


@pytest.mark.parametrize("value", ["", "123", "12345678901", "abcdefghij"])
def test_normalize_business_number_rejects_invalid_length(value):
    with pytest.raises(ValueError, match="10 digits"):
        normalize_business_number(value)


def test_missing_api_key_fails_before_network_call(monkeypatch):
    monkeypatch.delenv("NTS_BUSINESS_API_KEY", raising=False)
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    provider = NTSBusinessStatusProvider(api_key="")
    with pytest.raises(ProviderConfigurationError, match="NTS_BUSINESS_API_KEY"):
        provider.check_status(["1234567890"])


def _status_response() -> bytes:
    return json.dumps(
        {
            "status_code": "OK",
            "match_cnt": 1,
            "request_cnt": 1,
            "data": [
                {
                    "b_no": "1234567890",
                    "b_stt": "계속사업자",
                    "b_stt_cd": "01",
                    "tax_type": "부가가치세 일반과세자",
                    "tax_type_cd": "01",
                    "end_dt": "",
                    "utcc_yn": "N",
                    "tax_type_change_dt": "",
                    "invoice_apply_dt": "",
                    "rbf_tax_type": "해당없음",
                    "rbf_tax_type_cd": "99",
                }
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")


def test_status_request_is_normalized_and_provenance_is_returned():
    captured = {}

    def transport(url, body, headers, timeout):
        captured.update(
            {
                "url": url,
                "body": json.loads(body.decode("utf-8")),
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _status_response()

    provider = NTSBusinessStatusProvider(
        api_key="test%2Fencoded-key",
        timeout=3.0,
        transport=transport,
    )
    result = provider.check_status(["123-45-67890"])

    assert captured["url"].endswith(
        "/status?serviceKey=test%2Fencoded-key&returnType=JSON"
    )
    assert captured["body"] == {"b_no": ["1234567890"]}
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["timeout"] == 3.0
    assert result["requested_count"] == 1
    assert result["results"][0]["business_status"] == "계속사업자"
    assert result["results"][0]["closure_date"] is None
    assert len(result["response_hash"]) == 64
    assert "not a credit assessment" in result["limitations"]


def test_transient_transport_errors_retry_with_exponential_backoff():
    attempts = 0
    sleeps = []

    def transport(url, body, headers, timeout):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise _TransportRequestError(
                "NTS request failed with HTTP 503: temporary outage",
                retryable=True,
            )
        return _status_response()

    provider = NTSBusinessStatusProvider(
        api_key="test",
        max_attempts=3,
        backoff_seconds=0.25,
        transport=transport,
        sleep=sleeps.append,
    )
    result = provider.check_status(["1234567890"])

    assert attempts == 3
    assert sleeps == [0.25, 0.5]
    assert result["results"][0]["business_status_code"] == "01"


def test_non_retryable_transport_error_is_not_retried():
    attempts = 0

    def transport(url, body, headers, timeout):
        nonlocal attempts
        attempts += 1
        raise _TransportRequestError(
            "NTS request failed with HTTP 401: invalid key",
            retryable=False,
        )

    provider = NTSBusinessStatusProvider(
        api_key="test",
        max_attempts=3,
        transport=transport,
        sleep=lambda _: None,
    )

    with pytest.raises(_TransportRequestError, match="HTTP 401"):
        provider.check_status(["1234567890"])
    assert attempts == 1


def test_status_batch_limit_is_enforced():
    provider = NTSBusinessStatusProvider(api_key="test", transport=lambda *args: b"{}")
    with pytest.raises(ValueError, match="at most 100"):
        provider.check_status(["1234567890"] * 101)


def test_invalid_json_response_is_rejected():
    provider = NTSBusinessStatusProvider(
        api_key="test",
        transport=lambda *args: b"not-json",
    )
    with pytest.raises(ProviderResponseError, match="invalid JSON"):
        provider.check_status(["1234567890"])


def test_validate_registration_requires_core_fields():
    provider = NTSBusinessStatusProvider(api_key="test", transport=lambda *args: b"{}")
    with pytest.raises(ValueError, match="start_dt"):
        provider.validate_registration([{"b_no": "1234567890", "p_nm": "홍길동"}])


def test_validate_registration_posts_businesses_payload():
    captured = {}

    def transport(url, body, headers, timeout):
        captured["body"] = json.loads(body.decode("utf-8"))
        return json.dumps(
            {
                "status_code": "OK",
                "match_cnt": 1,
                "request_cnt": 1,
                "data": [{"b_no": "1234567890", "valid": "01", "valid_msg": "일치"}],
            },
            ensure_ascii=False,
        ).encode("utf-8")

    provider = NTSBusinessStatusProvider(api_key="test", transport=transport)
    result = provider.validate_registration(
        [{"b_no": "123-45-67890", "start_dt": "20200101", "p_nm": "홍길동"}]
    )

    assert captured["body"]["businesses"][0]["b_no"] == "1234567890"
    assert result["operation"] == "validate"
    assert result["results"][0]["valid"] == "01"
