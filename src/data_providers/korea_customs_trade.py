"""Korea Customs Service country-by-HS-code trade-statistics provider.

The adapter reads official aggregate customs statistics from data.go.kr. It does
not expose company-level customs declarations and must not be used as proof of a
specific firm's exports, imports, creditworthiness, or transaction eligibility.
"""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime
from urllib.parse import quote, urlencode

from ._http import RetryableProviderRequestError, default_get_transport
from .base import (
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderResponseError,
    canonical_json_sha256,
    utc_now_iso,
)

API_URL = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
SOURCE_URL = "https://www.data.go.kr/data/15100475/openapi.do"
_YEARMONTH_PATTERN = re.compile(r"^\d{6}$")
_COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")
_HS_PATTERN = re.compile(r"^(?:\d{2}|\d{4}|\d{6}|\d{10})$")
Transport = Callable[[str, dict[str, str], float], bytes]
Sleeper = Callable[[float], None]


def _normalize_yearmonth(value: str) -> str:
    text = str(value).strip()
    if _YEARMONTH_PATTERN.fullmatch(text) is None:
        raise ValueError("year-month must use YYYYMM format")
    try:
        datetime.strptime(text, "%Y%m")
    except ValueError as exc:
        raise ValueError("year-month is not a valid calendar month") from exc
    return text


def _month_index(value: str) -> int:
    parsed = datetime.strptime(value, "%Y%m")
    return parsed.year * 12 + parsed.month


def normalize_country_code(value: str) -> str:
    code = str(value).strip().upper()
    if _COUNTRY_PATTERN.fullmatch(code) is None:
        raise ValueError("country code must be a two-letter code used by the KCS API")
    return code


def normalize_hs_code(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    code = re.sub(r"\s+", "", str(value))
    if _HS_PATTERN.fullmatch(code) is None:
        raise ValueError("HS code must contain 2, 4, 6, or 10 digits")
    return code


def _integer(text: str | None) -> int | None:
    if text is None or not text.strip():
        return None
    normalized = text.replace(",", "").strip()
    try:
        return int(normalized)
    except ValueError as exc:
        raise ProviderResponseError(f"KCS returned a non-integer value: {text}") from exc


class KoreaCustomsTradeProvider:
    """Read-only client for aggregate country and HS-code trade statistics."""

    provider_name = "Korea Customs Service trade-statistics API"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 15.0,
        max_attempts: int = 3,
        backoff_seconds: float = 0.75,
        transport: Transport | None = None,
        sleep: Sleeper | None = None,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("KCS_TRADE_API_KEY")
            or os.getenv("DATA_GO_KR_SERVICE_KEY")
            or ""
        ).strip()
        self.timeout = float(timeout)
        self.max_attempts = int(max_attempts)
        self.backoff_seconds = float(backoff_seconds)
        self.transport = transport or default_get_transport
        self.sleep = sleep or time.sleep

        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def get_country_product_trade(
        self,
        *,
        start_yymm: str,
        end_yymm: str,
        country_code: str,
        hs_code: str | None = None,
    ) -> dict:
        """Fetch up to twelve months of official country-by-product trade totals."""

        if not self.api_key:
            raise ProviderConfigurationError(
                "KCS_TRADE_API_KEY or DATA_GO_KR_SERVICE_KEY is required"
            )
        start = _normalize_yearmonth(start_yymm)
        end = _normalize_yearmonth(end_yymm)
        if _month_index(start) > _month_index(end):
            raise ValueError("start_yymm must not be after end_yymm")
        if _month_index(end) - _month_index(start) >= 12:
            raise ValueError("KCS query period must not exceed twelve months")
        country = normalize_country_code(country_code)
        hs = normalize_hs_code(hs_code)

        params = {
            "serviceKey": quote(self.api_key, safe="%"),
            "strtYymm": start,
            "endYymm": end,
            "cntyCd": country,
        }
        if hs is not None:
            params["hsSgn"] = hs
        url = f"{API_URL}?{urlencode(params, safe='%')}"

        raw: bytes | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                raw = self.transport(url, {"Accept": "application/xml"}, self.timeout)
                break
            except RetryableProviderRequestError as exc:
                if not exc.retryable or attempt >= self.max_attempts:
                    raise
                self.sleep(self.backoff_seconds * (2 ** (attempt - 1)))
        if raw is None:
            raise ProviderRequestError("KCS request did not produce a response")

        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ProviderResponseError("KCS returned invalid XML") from exc

        result_code = (root.findtext(".//resultCode") or "").strip()
        result_message = (root.findtext(".//resultMsg") or "").strip()
        if result_code and result_code != "00":
            raise ProviderResponseError(
                f"KCS returned result {result_code}: {result_message or 'unknown error'}"
            )

        results = []
        for item in root.findall(".//item"):
            results.append(
                {
                    "period": (item.findtext("year") or "").strip() or None,
                    "country_name_ko": (item.findtext("statCdCntnKor1") or "").strip() or None,
                    "country_code": (item.findtext("statCd") or country).strip() or country,
                    "product_name_ko": (item.findtext("statKor") or "").strip() or None,
                    "hs_code": (item.findtext("hsCd") or hs or "").strip() or None,
                    "export_weight_kg": _integer(item.findtext("expWgt")),
                    "export_value_usd": _integer(item.findtext("expDlr")),
                    "import_weight_kg": _integer(item.findtext("impWgt")),
                    "import_value_usd": _integer(item.findtext("impDlr")),
                    "trade_balance_usd": _integer(item.findtext("balPayments")),
                }
            )

        normalized_payload = {
            "result_code": result_code or None,
            "result_message": result_message or None,
            "results": results,
        }
        return {
            "provider": self.provider_name,
            "operation": "country_product_trade",
            "source_url": SOURCE_URL,
            "official_api_url": API_URL,
            "retrieved_at": utc_now_iso(),
            "request": {
                "start_yymm": start,
                "end_yymm": end,
                "country_code": country,
                "hs_code": hs,
            },
            "results": results,
            "response_hash": canonical_json_sha256(normalized_payload),
            "limitations": [
                "Aggregate customs statistics only; not company-level declaration data.",
                "Exports are reported on an FOB basis and imports on a CIF basis.",
                "Monthly figures may be revised after declaration corrections or withdrawals.",
                "Trade concentration is context only and does not determine transaction approval, buyer risk, or product eligibility.",
            ],
        }
