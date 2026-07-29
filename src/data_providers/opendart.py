"""OpenDART corporate and financial-statement provider."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlencode

from ._http import GetTransport, Sleeper, get_json_with_retry
from .base import (
    ProviderConfigurationError,
    ProviderResponseError,
    canonical_json_sha256,
    utc_now_iso,
)

BASE_URL = "https://opendart.fss.or.kr/api"
SOURCE_URL = "https://opendart.fss.or.kr/guide/main.do"
SUCCESS_CODE = "000"
NO_DATA_CODE = "013"


def normalize_corp_code(value: str) -> str:
    code = re.sub(r"\D", "", str(value))
    if len(code) != 8:
        raise ValueError("OpenDART corp_code must contain exactly 8 digits")
    return code


class OpenDARTProvider:
    """Read-only client for corporate profiles and reported financial statements."""

    provider_name = "Financial Supervisory Service OpenDART API"

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
        self.api_key = (api_key or os.getenv("OPENDART_API_KEY") or "").strip()
        self.timeout = float(timeout)
        self.max_attempts = int(max_attempts)
        self.backoff_seconds = float(backoff_seconds)
        self.transport = transport
        self.sleep = sleep

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigurationError("OPENDART_API_KEY is required")
        query = urlencode({"crtfc_key": self.api_key, **params})
        parsed = get_json_with_retry(
            f"{BASE_URL}/{endpoint}?{query}",
            timeout=self.timeout,
            max_attempts=self.max_attempts,
            backoff_seconds=self.backoff_seconds,
            transport=self.transport,
            sleep=self.sleep,
        )
        if not isinstance(parsed, dict):
            raise ProviderResponseError("OpenDART response must be a JSON object")
        status = str(parsed.get("status") or "")
        if status and status not in {SUCCESS_CODE, NO_DATA_CODE}:
            raise ProviderResponseError(
                f"OpenDART {status}: {parsed.get('message') or 'request failed'}"
            )
        return parsed

    def get_company(self, corp_code: str) -> dict[str, Any]:
        """Fetch the public corporate profile for one DART corporation code."""

        normalized = normalize_corp_code(corp_code)
        response = self._get("company.json", {"corp_code": normalized})
        if str(response.get("status")) != SUCCESS_CODE:
            raise ProviderResponseError(
                f"OpenDART {response.get('status')}: {response.get('message')}"
            )
        profile_fields = {
            key: response.get(key)
            for key in (
                "corp_code",
                "corp_name",
                "corp_name_eng",
                "stock_name",
                "stock_code",
                "ceo_nm",
                "corp_cls",
                "jurir_no",
                "bizr_no",
                "adres",
                "hm_url",
                "ir_url",
                "phn_no",
                "fax_no",
                "induty_code",
                "est_dt",
                "acc_mt",
            )
        }
        return {
            "provider": self.provider_name,
            "operation": "company_profile",
            "source_url": SOURCE_URL,
            "retrieved_at": utc_now_iso(),
            "results": profile_fields,
            "response_hash": canonical_json_sha256(response),
            "limitations": (
                "Public filing profile only. Registration status, current credit quality, "
                "ownership verification, and lending eligibility require separate checks."
            ),
        }

    def get_financial_statements(
        self,
        corp_code: str,
        business_year: int | str,
        *,
        report_code: str = "11011",
        fs_div: str = "CFS",
    ) -> dict[str, Any]:
        """Fetch all reported accounts for one company and reporting period."""

        normalized = normalize_corp_code(corp_code)
        year = str(business_year)
        if len(year) != 4 or not year.isdigit():
            raise ValueError("business_year must be four digits")
        if report_code not in {"11013", "11012", "11014", "11011"}:
            raise ValueError("unsupported OpenDART report_code")
        if fs_div not in {"CFS", "OFS"}:
            raise ValueError("fs_div must be CFS or OFS")

        response = self._get(
            "fnlttSinglAcntAll.json",
            {
                "corp_code": normalized,
                "bsns_year": year,
                "reprt_code": report_code,
                "fs_div": fs_div,
            },
        )
        status = str(response.get("status") or "")
        if status == NO_DATA_CODE:
            rows: list[dict[str, Any]] = []
        else:
            rows = response.get("list")
            if not isinstance(rows, list):
                raise ProviderResponseError("OpenDART financial response is missing list")
        return {
            "provider": self.provider_name,
            "operation": "financial_statements",
            "source_url": SOURCE_URL,
            "retrieved_at": utc_now_iso(),
            "corp_code": normalized,
            "business_year": year,
            "report_code": report_code,
            "fs_div": fs_div,
            "results": rows,
            "response_hash": canonical_json_sha256(response),
            "limitations": (
                "Issuer-filed public statements. The regulator does not guarantee accuracy "
                "or completeness; account taxonomy and restatements must be normalized."
            ),
        }
