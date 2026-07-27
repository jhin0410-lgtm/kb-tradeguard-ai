"""UN Comtrade public-preview trade-statistics provider.

The preview endpoint needs no subscription key and is useful for showing real official
country-by-product trade context in the public competition demo. It is intentionally
bounded to one period and aggregate statistics; it is not buyer/supplier-level data and
must not be used as proof of a company's transaction history or financing eligibility.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import urlencode

from ._http import GetTransport, Sleeper, get_json_with_retry
from .base import ProviderResponseError, canonical_json_sha256, utc_now_iso

PREVIEW_BASE_URL = "https://comtradeapi.un.org/public/v1/preview/C"
SOURCE_URL = "https://uncomtrade.org/docs/un-comtrade-api/"

Frequency = Literal["A", "M"]
FlowCode = Literal["X", "M"]

# Small governed lookup covering the current showcase countries and major comparison
# markets. The provider also accepts explicit numeric M49 codes so this list is not a
# claim of complete country coverage.
ISO2_TO_M49 = {
    "KR": 410,
    "VN": 704,
    "US": 842,
    "CN": 156,
    "JP": 392,
    "DE": 276,
    "IN": 356,
    "ID": 360,
    "TH": 764,
    "AE": 784,
    "SA": 682,
}

_HS_PATTERN = re.compile(r"^(?:TOTAL|\d{2}|\d{4}|\d{6})$")
_YEAR_PATTERN = re.compile(r"^\d{4}$")
_MONTH_PATTERN = re.compile(r"^\d{6}$")


def country_to_m49(value: str | int) -> int:
    """Resolve a two-letter governed code or validate an explicit M49 number."""

    if isinstance(value, int) or str(value).strip().isdigit():
        number = int(value)
        if number < 0 or number > 999:
            raise ValueError("M49 country code must be between 0 and 999")
        return number
    code = str(value).strip().upper()
    try:
        return ISO2_TO_M49[code]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported ISO2 country code for the governed preview lookup: {code}"
        ) from exc


def _normalize_period(value: str | int, frequency: Frequency) -> str:
    period = str(value).strip()
    pattern = _YEAR_PATTERN if frequency == "A" else _MONTH_PATTERN
    label = "YYYY" if frequency == "A" else "YYYYMM"
    if pattern.fullmatch(period) is None:
        raise ValueError(f"period must use {label} format for frequency {frequency}")
    if frequency == "M" and not 1 <= int(period[-2:]) <= 12:
        raise ValueError("monthly period contains an invalid month")
    return period


def _normalize_hs_code(value: str | int | None) -> str:
    if value is None or not str(value).strip():
        return "TOTAL"
    code = str(value).replace(" ", "").upper()
    if _HS_PATTERN.fullmatch(code) is None:
        raise ValueError("HS code must be TOTAL or contain 2, 4, or 6 digits")
    return code


def _number(value: Any) -> float | int | None:
    if value in {None, ""}:
        return None
    try:
        number = float(str(value).replace(",", ""))
    except ValueError as exc:
        raise ProviderResponseError(f"UN Comtrade returned a non-numeric value: {value}") from exc
    return int(number) if number.is_integer() else number


class UNComtradePreviewProvider:
    """Read-only client for one-period public preview requests."""

    provider_name = "UN Comtrade public preview API"

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        max_attempts: int = 3,
        backoff_seconds: float = 1.0,
        transport: GetTransport | None = None,
        sleep: Sleeper | None = None,
    ) -> None:
        self.timeout = float(timeout)
        self.max_attempts = int(max_attempts)
        self.backoff_seconds = float(backoff_seconds)
        self.transport = transport
        self.sleep = sleep

    def get_trade_snapshot(
        self,
        *,
        period: str | int,
        reporter: str | int = "KR",
        partner: str | int = 0,
        hs_code: str | int | None = None,
        flow_code: FlowCode = "X",
        frequency: Frequency = "A",
        max_records: int = 100,
    ) -> dict[str, Any]:
        """Fetch one annual or monthly reporter-partner-product preview snapshot."""

        if frequency not in {"A", "M"}:
            raise ValueError("frequency must be A or M")
        if flow_code not in {"X", "M"}:
            raise ValueError("flow_code must be X for exports or M for imports")
        if max_records < 1 or max_records > 500:
            raise ValueError("max_records must be between 1 and 500")

        normalized_period = _normalize_period(period, frequency)
        reporter_code = country_to_m49(reporter)
        partner_code = country_to_m49(partner)
        product_code = _normalize_hs_code(hs_code)
        params = {
            "period": normalized_period,
            "reporterCode": str(reporter_code),
            "partnerCode": str(partner_code),
            "cmdCode": product_code,
            "flowCode": flow_code,
            "maxRecords": str(max_records),
        }
        url = f"{PREVIEW_BASE_URL}/{frequency}/HS?{urlencode(params)}"
        payload = get_json_with_retry(
            url,
            timeout=self.timeout,
            max_attempts=self.max_attempts,
            backoff_seconds=self.backoff_seconds,
            transport=self.transport,
            sleep=self.sleep,
        )
        if not isinstance(payload, dict):
            raise ProviderResponseError("UN Comtrade response must be a JSON object")
        raw_rows = payload.get("data")
        if raw_rows is None:
            raw_rows = []
        if not isinstance(raw_rows, list):
            raise ProviderResponseError("UN Comtrade data field must be a list")

        rows: list[dict[str, Any]] = []
        for raw in raw_rows:
            if not isinstance(raw, dict):
                raise ProviderResponseError("UN Comtrade data rows must be JSON objects")
            rows.append(
                {
                    "period": str(raw.get("period") or normalized_period),
                    "reporter_code": raw.get("reporterCode", reporter_code),
                    "reporter_iso": raw.get("reporterISO"),
                    "reporter_name": raw.get("reporterDesc"),
                    "partner_code": raw.get("partnerCode", partner_code),
                    "partner_iso": raw.get("partnerISO"),
                    "partner_name": raw.get("partnerDesc"),
                    "flow_code": raw.get("flowCode", flow_code),
                    "flow_name": raw.get("flowDesc"),
                    "hs_code": raw.get("cmdCode", product_code),
                    "product_name": raw.get("cmdDesc"),
                    "primary_value_usd": _number(raw.get("primaryValue")),
                    "fob_value_usd": _number(raw.get("fobvalue")),
                    "cif_value_usd": _number(raw.get("cifvalue")),
                    "net_weight_kg": _number(raw.get("netWgt")),
                    "quantity": _number(raw.get("qty")),
                    "quantity_unit": raw.get("qtyUnitAbbr"),
                    "is_reported": raw.get("isReported"),
                    "is_aggregate": raw.get("isAggregate"),
                }
            )

        return {
            "provider": self.provider_name,
            "operation": "trade_preview",
            "source_url": SOURCE_URL,
            "official_api_url": url,
            "retrieved_at": utc_now_iso(),
            "request": {
                "period": normalized_period,
                "frequency": frequency,
                "reporter_code": reporter_code,
                "partner_code": partner_code,
                "hs_code": product_code,
                "flow_code": flow_code,
                "max_records": max_records,
            },
            "results": rows,
            "response_hash": canonical_json_sha256(payload),
            "limitations": [
                "Public preview endpoint with limited records and rate limits; not a complete extraction.",
                "Official aggregate trade statistics only; no buyer, supplier, company, or declaration-level records.",
                "Reported trade data can be revised and bilateral mirror statistics can differ.",
                "This context does not determine transaction approval, buyer credit, hedge suitability, or product eligibility.",
            ],
        }
