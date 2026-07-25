"""Normalization helpers for presenting official provider data safely.

These helpers preserve raw quotation units and source metadata. They do not turn
public reference data into executable prices, official credit ratings, or
customer-specific decisions.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .data_providers.base import ProviderResponseError

_CURRENCY_UNIT_PATTERN = re.compile(r"^([A-Z]{3})(?:\((\d+)\))?$")


def parse_currency_unit(value: str) -> tuple[str, int]:
    """Parse KEXIM currency units such as USD and JPY(100)."""

    text = str(value).strip().upper()
    match = _CURRENCY_UNIT_PATTERN.fullmatch(text)
    if not match:
        raise ValueError(f"unsupported KEXIM currency unit: {value}")
    currency = match.group(1)
    quotation_unit = int(match.group(2) or 1)
    if quotation_unit <= 0:
        raise ValueError("quotation unit must be positive")
    return currency, quotation_unit


def _per_unit(value: Any, quotation_unit: int) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ProviderResponseError(f"official rate is not numeric: {value}") from exc
    return numeric / quotation_unit


def build_kexim_rate_frame(snapshot: dict[str, Any]) -> pd.DataFrame:
    """Build a calculation-ready KEXIM reference-rate table.

    Raw quoted rates and the quotation unit remain visible. The normalized
    ``*_per_unit`` columns express KRW per one foreign-currency unit, which is
    the convention expected by the existing deterministic calculation engine.
    """

    rows = snapshot.get("results")
    if not isinstance(rows, list):
        raise ProviderResponseError("KEXIM snapshot is missing a results list")

    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ProviderResponseError("KEXIM result row must be a mapping")
        currency, quotation_unit = parse_currency_unit(row.get("currency_unit") or "")
        normalized.append(
            {
                "currency": currency,
                "currency_name": row.get("currency_name"),
                "raw_currency_unit": row.get("currency_unit"),
                "quotation_unit": quotation_unit,
                "deal_base_rate_raw": row.get("deal_base_rate"),
                "spot_rate_krw_per_unit": _per_unit(
                    row.get("deal_base_rate"), quotation_unit
                ),
                "telegraphic_transfer_buy_per_unit": _per_unit(
                    row.get("telegraphic_transfer_buy"), quotation_unit
                ),
                "telegraphic_transfer_sell_per_unit": _per_unit(
                    row.get("telegraphic_transfer_sell"), quotation_unit
                ),
                "observation_date": snapshot.get("observation_date"),
                "retrieved_at": snapshot.get("retrieved_at"),
                "source_url": snapshot.get("source_url"),
                "response_hash": snapshot.get("response_hash"),
            }
        )
    return pd.DataFrame(normalized)


def build_ecos_key_statistics_frame(snapshot: dict[str, Any]) -> pd.DataFrame:
    """Return ECOS key statistics with source metadata attached."""

    rows = snapshot.get("results")
    if not isinstance(rows, list):
        raise ProviderResponseError("ECOS snapshot is missing a results list")
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["retrieved_at"] = snapshot.get("retrieved_at")
    frame["source_url"] = snapshot.get("source_url")
    frame["response_hash"] = snapshot.get("response_hash")
    return frame


def build_dart_company_frame(snapshot: dict[str, Any]) -> pd.DataFrame:
    """Return one OpenDART public company profile as a display table."""

    result = snapshot.get("results")
    if not isinstance(result, dict):
        raise ProviderResponseError("OpenDART company snapshot is missing a result mapping")
    row = dict(result)
    row.update(
        {
            "retrieved_at": snapshot.get("retrieved_at"),
            "source_url": snapshot.get("source_url"),
            "response_hash": snapshot.get("response_hash"),
        }
    )
    return pd.DataFrame([row])
