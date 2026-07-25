"""Bank of Korea ECOS public statistics provider."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from ._http import GetTransport, Sleeper, get_json_with_retry
from .base import (
    ProviderConfigurationError,
    ProviderResponseError,
    canonical_json_sha256,
    utc_now_iso,
)

BASE_URL = "https://ecos.bok.or.kr/api"
SOURCE_URL = "https://ecos.bok.or.kr/api/#/"


class BOKECOSProvider:
    """Read-only ECOS client preserving source metadata and raw observations."""

    provider_name = "Bank of Korea ECOS API"

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
        self.api_key = (api_key or os.getenv("BOK_ECOS_API_KEY") or "").strip()
        self.timeout = float(timeout)
        self.max_attempts = int(max_attempts)
        self.backoff_seconds = float(backoff_seconds)
        self.transport = transport
        self.sleep = sleep

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigurationError("BOK_ECOS_API_KEY is required")
        url = f"{BASE_URL}/{path}"
        parsed = get_json_with_retry(
            url,
            timeout=self.timeout,
            max_attempts=self.max_attempts,
            backoff_seconds=self.backoff_seconds,
            transport=self.transport,
            sleep=self.sleep,
        )
        if not isinstance(parsed, dict):
            raise ProviderResponseError("ECOS response must be a JSON object")
        result = parsed.get("RESULT")
        if isinstance(result, dict):
            code = str(result.get("CODE") or "")
            message = str(result.get("MESSAGE") or "ECOS request failed")
            if code and code != "INFO-000":
                raise ProviderResponseError(f"ECOS {code}: {message}")
        return parsed

    def get_key_statistics(self, start: int = 1, end: int = 20) -> dict[str, Any]:
        """Fetch ECOS key statistics for a lightweight live-connection check."""

        if start < 1 or end < start:
            raise ValueError("start/end range is invalid")
        key = quote(self.api_key, safe="")
        response = self._get(f"KeyStatisticList/{key}/json/kr/{start}/{end}")
        block = response.get("KeyStatisticList")
        if not isinstance(block, dict) or not isinstance(block.get("row"), list):
            raise ProviderResponseError("ECOS key-statistics response is missing rows")
        rows = []
        for row in block["row"]:
            if not isinstance(row, dict):
                raise ProviderResponseError("ECOS row must be a JSON object")
            rows.append(
                {
                    "class_name": row.get("CLASS_NAME"),
                    "stat_name": row.get("KEYSTAT_NAME"),
                    "data_value": row.get("DATA_VALUE"),
                    "cycle": row.get("CYCLE"),
                    "unit_name": row.get("UNIT_NAME"),
                }
            )
        return {
            "provider": self.provider_name,
            "operation": "key_statistics",
            "source_url": SOURCE_URL,
            "retrieved_at": utc_now_iso(),
            "requested_range": [start, end],
            "results": rows,
            "response_hash": canonical_json_sha256(response),
            "limitations": (
                "Official public statistics only. Observation periods, units, revisions, "
                "and publication lags must be preserved before financial use."
            ),
        }

    def search_statistics(
        self,
        stat_code: str,
        cycle: str,
        start_time: str,
        end_time: str,
        item_code1: str,
        item_code2: str = "?",
        item_code3: str = "?",
        *,
        start: int = 1,
        end: int = 100,
    ) -> dict[str, Any]:
        """Fetch one ECOS time series using explicit statistical codes."""

        required = [stat_code, cycle, start_time, end_time, item_code1]
        if any(not str(value).strip() for value in required):
            raise ValueError("statistic search parameters must not be blank")
        key = quote(self.api_key, safe="")
        parts = [
            "StatisticSearch",
            key,
            "json",
            "kr",
            str(start),
            str(end),
            stat_code,
            cycle,
            start_time,
            end_time,
            item_code1,
            item_code2,
            item_code3,
        ]
        response = self._get("/".join(quote(str(part), safe="?") for part in parts))
        block = response.get("StatisticSearch")
        if not isinstance(block, dict) or not isinstance(block.get("row"), list):
            raise ProviderResponseError("ECOS statistic response is missing rows")
        return {
            "provider": self.provider_name,
            "operation": "statistic_search",
            "source_url": SOURCE_URL,
            "retrieved_at": utc_now_iso(),
            "series": {
                "stat_code": stat_code,
                "cycle": cycle,
                "start_time": start_time,
                "end_time": end_time,
                "item_code1": item_code1,
                "item_code2": item_code2,
                "item_code3": item_code3,
            },
            "results": block["row"],
            "response_hash": canonical_json_sha256(response),
            "limitations": (
                "Raw ECOS observations are returned without silent frequency conversion, "
                "interpolation, or revision handling."
            ),
        }
