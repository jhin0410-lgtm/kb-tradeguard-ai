"""No-key World Bank Indicators API adapter for country-context facts.

The provider returns sourced observations only.  It does not assign a country score,
trade approval, or probability of loss.
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlencode

from ._http import GetTransport, get_json_with_retry
from .base import ProviderResponseError, canonical_json_sha256, utc_now_iso

WORLD_BANK_API_BASE = "https://api.worldbank.org/v2"
REFERENCE_MACRO_INDICATORS = (
    "NY.GDP.MKTP.KD.ZG",  # GDP growth, annual percent
    "FP.CPI.TOTL.ZG",  # inflation, consumer prices, annual percent
    "FI.RES.TOTL.MO",  # total reserves in months of imports
    "BN.CAB.XOKA.GD.ZS",  # current-account balance, percent of GDP
)
_INDICATOR_PATTERN = re.compile(r"^[A-Z0-9_.]+$")


def normalize_world_bank_country_code(value: str) -> str:
    code = str(value).strip().upper()
    if len(code) not in {2, 3} or not code.isalpha():
        raise ValueError("World Bank country code must contain 2 or 3 letters")
    return code


def normalize_indicator_code(value: str) -> str:
    code = str(value).strip().upper()
    if not code or _INDICATOR_PATTERN.fullmatch(code) is None:
        raise ValueError("World Bank indicator code is invalid")
    return code


class WorldBankCountryProvider:
    """Fetch latest non-null official indicator observations without an API key."""

    def __init__(
        self,
        *,
        transport: GetTransport | None = None,
        timeout: float = 15.0,
        max_attempts: int = 3,
    ) -> None:
        self.transport = transport
        self.timeout = float(timeout)
        self.max_attempts = int(max_attempts)

    def get_latest_indicator(
        self,
        country_code: str,
        indicator_code: str,
        *,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> dict:
        country = normalize_world_bank_country_code(country_code)
        indicator = normalize_indicator_code(indicator_code)
        current_year = date.today().year
        end = int(end_year or current_year)
        start = int(start_year or end - 8)
        if start > end:
            raise ValueError("start_year must not be after end_year")

        query = urlencode(
            {
                "format": "json",
                "date": f"{start}:{end}",
                "per_page": 100,
            }
        )
        url = f"{WORLD_BANK_API_BASE}/country/{country}/indicator/{indicator}?{query}"
        payload = get_json_with_retry(
            url,
            timeout=self.timeout,
            max_attempts=self.max_attempts,
            transport=self.transport,
        )
        observation = self._parse_latest_observation(payload, country, indicator)
        limitations = []
        if observation is None:
            limitations.append(
                "No non-null observation was returned for the requested country, indicator, and period."
            )
        return {
            "provider": "World Bank Indicators API v2",
            "official_source_url": url,
            "country_code": country,
            "indicator_code": indicator,
            "requested_period": {"start_year": start, "end_year": end},
            "retrieved_at": utc_now_iso(),
            "response_hash": canonical_json_sha256(payload),
            "results": observation,
            "limitations": limitations,
        }

    def get_reference_macro_indicators(
        self,
        country_code: str,
        *,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[dict]:
        """Return the narrow, governed indicator set used by the first reference case."""

        return [
            self.get_latest_indicator(
                country_code,
                indicator,
                start_year=start_year,
                end_year=end_year,
            )
            for indicator in REFERENCE_MACRO_INDICATORS
        ]

    @staticmethod
    def _parse_latest_observation(
        payload: object,
        country_code: str,
        indicator_code: str,
    ) -> dict | None:
        if not isinstance(payload, list) or len(payload) < 2:
            raise ProviderResponseError("World Bank response must be a metadata/data array")
        rows = payload[1]
        if rows is None:
            return None
        if not isinstance(rows, list):
            raise ProviderResponseError("World Bank observation payload must be a list")

        usable = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = row.get("value")
            year_text = str(row.get("date") or "")
            if value is None or not year_text.isdigit():
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError) as exc:
                raise ProviderResponseError(
                    f"World Bank returned a non-numeric value for {indicator_code}"
                ) from exc
            indicator = row.get("indicator") or {}
            country = row.get("country") or {}
            usable.append(
                {
                    "country_code": country_code,
                    "country_name": country.get("value"),
                    "country_iso3_code": row.get("countryiso3code"),
                    "indicator_code": indicator.get("id") or indicator_code,
                    "indicator_name": indicator.get("value"),
                    "observation_year": int(year_text),
                    "value": numeric_value,
                    "unit": row.get("unit") or None,
                    "observation_status": row.get("obs_status") or None,
                    "decimal_places": row.get("decimal"),
                }
            )
        if not usable:
            return None
        return max(usable, key=lambda item: item["observation_year"])
