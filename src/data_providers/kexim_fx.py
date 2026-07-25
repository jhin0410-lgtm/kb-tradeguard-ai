"""Korea Eximbank official reference exchange-rate provider."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from ._http import GetTransport, Sleeper, get_json_with_retry
from .base import (
    ProviderConfigurationError,
    ProviderResponseError,
    canonical_json_sha256,
    utc_now_iso,
)

BASE_URL = "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"
SOURCE_URL = "https://www.data.go.kr/data/3068846/openapi.do"
RESULT_MESSAGES = {
    "1": "success",
    "2": "data code error",
    "3": "authentication key error",
    "4": "daily request limit exceeded",
}


def _parse_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ProviderResponseError(f"KEXIM returned a non-numeric rate: {value}") from exc


def _normalize_date(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value).replace("-", "").strip()
    if len(text) != 8 or not text.isdigit():
        raise ValueError("search date must be YYYYMMDD or YYYY-MM-DD")
    datetime.strptime(text, "%Y%m%d")
    return text


class KEXIMFXProvider:
    """Read-only client for official KEXIM reference-rate snapshots."""

    provider_name = "Korea Eximbank exchange-rate API"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 15.0,
        max_attempts: int = 3,
        backoff_seconds: float = 0.75,
        transport: GetTransport | None = None,
        sleep: Sleeper | None = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("KEXIM_API_KEY") or "").strip()
        self.timeout = float(timeout)
        self.max_attempts = int(max_attempts)
        self.backoff_seconds = float(backoff_seconds)
        self.transport = transport
        self.sleep = sleep

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def fetch_rates(self, search_date: str | date | datetime) -> dict[str, Any]:
        """Fetch one date's public reference rates; an empty list may mean no publication."""

        if not self.api_key:
            raise ProviderConfigurationError("KEXIM_API_KEY is required")
        normalized_date = _normalize_date(search_date)
        query = urlencode(
            {"authkey": self.api_key, "searchdate": normalized_date, "data": "AP01"}
        )
        response = get_json_with_retry(
            f"{BASE_URL}?{query}",
            timeout=self.timeout,
            max_attempts=self.max_attempts,
            backoff_seconds=self.backoff_seconds,
            transport=self.transport,
            sleep=self.sleep,
        )
        if isinstance(response, dict):
            code = response.get("result") or response.get("code")
            message = response.get("message") or response.get("msg") or "KEXIM request failed"
            raise ProviderResponseError(f"KEXIM {code}: {message}")
        if not isinstance(response, list):
            raise ProviderResponseError("KEXIM response must be a JSON list")

        rows = []
        for row in response:
            if not isinstance(row, dict):
                raise ProviderResponseError("KEXIM rate row must be a JSON object")
            result_code = str(row.get("result") or "")
            if result_code and result_code != "1":
                message = RESULT_MESSAGES.get(result_code, "unknown provider error")
                raise ProviderResponseError(f"KEXIM {result_code}: {message}")
            rows.append(
                {
                    "result_code": row.get("result"),
                    "currency_unit": row.get("cur_unit"),
                    "currency_name": row.get("cur_nm"),
                    "telegraphic_transfer_buy": _parse_number(row.get("ttb")),
                    "telegraphic_transfer_sell": _parse_number(row.get("tts")),
                    "deal_base_rate": _parse_number(row.get("deal_bas_r")),
                    "book_price": _parse_number(row.get("bkpr")),
                    "year_ago_rate": _parse_number(row.get("yy_efee_r")),
                    "ten_day_ago_rate": _parse_number(row.get("ten_dd_efee_r")),
                    "kftc_deal_base_rate": _parse_number(row.get("kftc_deal_bas_r")),
                    "kftc_book_price": _parse_number(row.get("kftc_bkpr")),
                }
            )
        return {
            "provider": self.provider_name,
            "operation": "reference_rates",
            "source_url": SOURCE_URL,
            "retrieved_at": utc_now_iso(),
            "observation_date": normalized_date,
            "results": rows,
            "response_hash": canonical_json_sha256(response),
            "limitations": (
                "Official public reference data, not an executable KB quote or guaranteed "
                "real-time market price. Currency units such as JPY(100) must be preserved."
            ),
        }

    def fetch_latest_rates(
        self,
        as_of_date: str | date | datetime | None = None,
        *,
        lookback_days: int = 10,
    ) -> dict[str, Any]:
        """Walk backward to the latest published date, covering weekends and holidays."""

        if lookback_days < 0:
            raise ValueError("lookback_days must be non-negative")
        anchor_text = _normalize_date(as_of_date or date.today())
        anchor = datetime.strptime(anchor_text, "%Y%m%d").date()
        for offset in range(lookback_days + 1):
            candidate = anchor - timedelta(days=offset)
            result = self.fetch_rates(candidate)
            if result["results"]:
                result["requested_as_of_date"] = anchor_text
                result["lookback_days_used"] = offset
                return result
        raise ProviderResponseError(
            f"KEXIM returned no published rates in the {lookback_days + 1}-day window"
        )
