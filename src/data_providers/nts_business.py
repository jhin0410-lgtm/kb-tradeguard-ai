"""National Tax Service business-registration status provider.

This adapter supports domestic business identity/status checks only. It does not
provide credit ratings, financial statements, trade statistics, or legal
clearance.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .base import (
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderResponseError,
    canonical_json_sha256,
    utc_now_iso,
)

BASE_URL = "https://api.odcloud.kr/api/nts-businessman/v1"
SOURCE_URL = "https://www.data.go.kr/data/15081808/openapi.do"
MAX_BATCH_SIZE = 100
Transport = Callable[[str, bytes, dict[str, str], float], bytes]


def normalize_business_number(value: str) -> str:
    """Normalize a Korean business registration number to ten digits."""

    normalized = re.sub(r"\D", "", str(value))
    if len(normalized) != 10:
        raise ValueError("business registration number must contain exactly 10 digits")
    return normalized


def _default_transport(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
) -> bytes:
    request = Request(url=url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderRequestError(
            f"NTS request failed with HTTP {exc.code}: {detail[:300]}"
        ) from exc
    except URLError as exc:
        raise ProviderRequestError(f"NTS request failed: {exc.reason}") from exc


class NTSBusinessStatusProvider:
    """Read-only client for NTS status and authenticity endpoints."""

    provider_name = "National Tax Service business-registration API"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 15.0,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("NTS_BUSINESS_API_KEY")
            or os.getenv("DATA_GO_KR_SERVICE_KEY")
            or ""
        ).strip()
        self.timeout = float(timeout)
        self.transport = transport or _default_transport

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigurationError(
                "NTS_BUSINESS_API_KEY or DATA_GO_KR_SERVICE_KEY is required"
            )
        encoded_key = quote(self.api_key, safe="%")
        url = f"{BASE_URL}/{endpoint}?serviceKey={encoded_key}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        raw = self.transport(
            url,
            body,
            {"Content-Type": "application/json", "Accept": "application/json"},
            self.timeout,
        )
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderResponseError("NTS returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise ProviderResponseError("NTS response must be a JSON object")
        if not isinstance(parsed.get("data"), list):
            raise ProviderResponseError("NTS response is missing a data list")
        return parsed

    @staticmethod
    def _normalize_batch(business_numbers: Sequence[str]) -> list[str]:
        normalized = [normalize_business_number(value) for value in business_numbers]
        if not normalized:
            raise ValueError("at least one business registration number is required")
        if len(normalized) > MAX_BATCH_SIZE:
            raise ValueError(f"NTS accepts at most {MAX_BATCH_SIZE} records per request")
        return normalized

    def check_status(self, business_numbers: Sequence[str]) -> dict[str, Any]:
        """Return business operating/tax status for up to 100 registrations."""

        normalized = self._normalize_batch(business_numbers)
        response = self._post("status", {"b_no": normalized})
        results = []
        for row in response["data"]:
            if not isinstance(row, dict):
                raise ProviderResponseError("NTS status row must be a JSON object")
            results.append(
                {
                    "business_number": row.get("b_no"),
                    "business_status": row.get("b_stt"),
                    "business_status_code": row.get("b_stt_cd"),
                    "tax_type": row.get("tax_type"),
                    "tax_type_code": row.get("tax_type_cd"),
                    "closure_date": row.get("end_dt") or None,
                    "unit_tax_type": row.get("utcc_yn"),
                    "tax_type_change_date": row.get("tax_type_change_dt") or None,
                    "invoice_application_date": row.get("invoice_apply_dt") or None,
                    "previous_tax_type": row.get("rbf_tax_type"),
                    "previous_tax_type_code": row.get("rbf_tax_type_cd"),
                }
            )
        return {
            "provider": self.provider_name,
            "operation": "status",
            "source_url": SOURCE_URL,
            "retrieved_at": utc_now_iso(),
            "requested_count": len(normalized),
            "results": results,
            "response_hash": canonical_json_sha256(response),
            "limitations": (
                "Domestic registration status only; not a credit assessment, "
                "counterparty guarantee, sanctions clearance, or trade-risk decision."
            ),
        }

    def validate_registration(
        self,
        registrations: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate registration details supplied by an authorized user."""

        if not registrations:
            raise ValueError("at least one registration record is required")
        if len(registrations) > MAX_BATCH_SIZE:
            raise ValueError(f"NTS accepts at most {MAX_BATCH_SIZE} records per request")

        normalized_records = []
        for item in registrations:
            if not isinstance(item, dict):
                raise ValueError("each registration record must be a mapping")
            required = {"b_no", "start_dt", "p_nm"}
            missing = sorted(required - set(item))
            if missing:
                raise ValueError(
                    "registration record is missing required fields: " + ", ".join(missing)
                )
            normalized = dict(item)
            normalized["b_no"] = normalize_business_number(str(item["b_no"]))
            normalized_records.append(normalized)

        response = self._post("validate", {"businesses": normalized_records})
        return {
            "provider": self.provider_name,
            "operation": "validate",
            "source_url": SOURCE_URL,
            "retrieved_at": utc_now_iso(),
            "requested_count": len(normalized_records),
            "results": response["data"],
            "response_hash": canonical_json_sha256(response),
            "limitations": (
                "Authenticity comparison only. Input business details must be handled "
                "under the project's privacy and authorization controls."
            ),
        }
