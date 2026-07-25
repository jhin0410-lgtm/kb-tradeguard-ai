"""Explicit FX-input source selection for deterministic TradeGuard calculations.

Only the spot-rate column may be replaced by Korea Eximbank public reference
rates. Interest-rate inputs remain separately identified assumptions so that a
public reference spot is never presented as an executable KB quote or a live
forward price.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Literal

import pandas as pd

from .official_data_views import build_kexim_rate_frame
from .validators import validate_fx_rates

FXSource = Literal["bundled", "manual", "kexim"]


@dataclass(frozen=True)
class FXInputSelection:
    """Calculation-ready FX inputs plus source and fallback provenance."""

    rates: pd.DataFrame
    requested_source: FXSource
    applied_source: str
    required_currencies: tuple[str, ...]
    requested_as_of_date: str
    observation_date: str | None
    retrieved_at: str | None
    response_hash: str | None
    stale_days: int | None
    is_stale: bool
    used_fallback: bool
    fallback_reason: str | None
    limitations: tuple[str, ...]


def _normalize_date(value: str | date | datetime | pd.Timestamp | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.Timestamp(str(value)).date()
    except (TypeError, ValueError) as exc:
        raise ValueError("as_of_date must be a valid date") from exc


def _normalize_currencies(values: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(sorted({str(value).strip().upper() for value in values}))
    if not normalized or any(not value for value in normalized):
        raise ValueError("at least one non-blank required currency is needed")
    return normalized


def _subset_required(base_rates: pd.DataFrame, required: tuple[str, ...]) -> pd.DataFrame:
    rates = validate_fx_rates(base_rates).copy(deep=True)
    missing = sorted(set(required) - set(rates["currency"]))
    if missing:
        raise ValueError(
            "Missing spot/interest-rate assumptions for required currencies: "
            + ", ".join(missing)
        )
    return rates[rates["currency"].isin(required)].reset_index(drop=True)


def _annotate(
    rates: pd.DataFrame,
    *,
    spot_source: str,
    interest_rate_source: str,
    observation_date: str | None,
    retrieved_at: str | None,
    response_hash: str | None,
    stale_days: int | None,
    is_stale: bool,
) -> pd.DataFrame:
    annotated = rates.copy(deep=True)
    annotated["spot_source"] = spot_source
    annotated["interest_rate_source"] = interest_rate_source
    annotated["spot_observation_date"] = observation_date
    annotated["spot_retrieved_at"] = retrieved_at
    annotated["spot_response_hash"] = response_hash
    annotated["spot_stale_days"] = stale_days
    annotated["spot_is_stale"] = bool(is_stale)
    return annotated


def _bundled_selection(
    base_rates: pd.DataFrame,
    required: tuple[str, ...],
    requested_source: FXSource,
    as_of: date,
    *,
    fallback_reason: str | None = None,
) -> FXInputSelection:
    rates = _subset_required(base_rates, required)
    used_fallback = requested_source != "bundled"
    applied_source = "bundled_fallback" if used_fallback else "bundled"
    annotated = _annotate(
        rates,
        spot_source=(
            "bundled sample spot fallback"
            if used_fallback
            else "bundled sample spot assumption"
        ),
        interest_rate_source="bundled sample interest-rate assumptions",
        observation_date=None,
        retrieved_at=None,
        response_hash=None,
        stale_days=None,
        is_stale=False,
    )
    limitations = (
        "Bundled values are static sample assumptions and are not real-time market data.",
        "Theoretical forwards use separate interest-rate assumptions and are not executable KB quotes.",
    )
    if used_fallback:
        limitations = (
            "The requested official source was not applied; bundled sample inputs were used explicitly as fallback.",
            *limitations,
        )
    return FXInputSelection(
        rates=annotated,
        requested_source=requested_source,
        applied_source=applied_source,
        required_currencies=required,
        requested_as_of_date=as_of.isoformat(),
        observation_date=None,
        retrieved_at=None,
        response_hash=None,
        stale_days=None,
        is_stale=False,
        used_fallback=used_fallback,
        fallback_reason=fallback_reason,
        limitations=limitations,
    )


def select_fx_inputs(
    base_rates: pd.DataFrame,
    required_currencies: Iterable[str],
    *,
    source: FXSource = "bundled",
    as_of_date: str | date | datetime | pd.Timestamp | None = None,
    manual_rates: pd.DataFrame | None = None,
    kexim_snapshot: dict[str, Any] | None = None,
    stale_after_days: int = 3,
    allow_bundled_fallback: bool = False,
    fallback_reason: str | None = None,
) -> FXInputSelection:
    """Select calculation inputs without silently mixing data sources.

    For ``kexim``, public reference spot rates replace only ``spot_rate_krw``.
    The KRW and foreign interest-rate columns stay equal to the validated base
    assumptions and are labelled accordingly. Missing required official rates
    either raise or trigger an explicit whole-table bundled fallback.
    """

    if source not in {"bundled", "manual", "kexim"}:
        raise ValueError("source must be bundled, manual, or kexim")
    if stale_after_days < 0:
        raise ValueError("stale_after_days must be non-negative")

    required = _normalize_currencies(required_currencies)
    as_of = _normalize_date(as_of_date)

    if source == "bundled":
        return _bundled_selection(base_rates, required, source, as_of)

    if source == "manual":
        if manual_rates is None:
            raise ValueError("manual_rates are required when source is manual")
        rates = _subset_required(manual_rates, required)
        annotated = _annotate(
            rates,
            spot_source="manual input",
            interest_rate_source="manual input",
            observation_date=as_of.isoformat(),
            retrieved_at=None,
            response_hash=None,
            stale_days=0,
            is_stale=False,
        )
        return FXInputSelection(
            rates=annotated,
            requested_source=source,
            applied_source="manual",
            required_currencies=required,
            requested_as_of_date=as_of.isoformat(),
            observation_date=as_of.isoformat(),
            retrieved_at=None,
            response_hash=None,
            stale_days=0,
            is_stale=False,
            used_fallback=False,
            fallback_reason=None,
            limitations=(
                "Manual values are user inputs and must be independently reviewed.",
                "Manual forward or bank quotations remain separate from deterministic theoretical forwards.",
            ),
        )

    if kexim_snapshot is None:
        if allow_bundled_fallback:
            return _bundled_selection(
                base_rates,
                required,
                source,
                as_of,
                fallback_reason=fallback_reason or "KEXIM snapshot was unavailable",
            )
        raise ValueError("kexim_snapshot is required when source is kexim")

    try:
        base = _subset_required(base_rates, required)
        official = build_kexim_rate_frame(kexim_snapshot)
        if official.empty:
            raise ValueError("KEXIM snapshot contains no reference-rate rows")
        if official["currency"].duplicated().any():
            duplicates = sorted(
                official.loc[official["currency"].duplicated(), "currency"].unique()
            )
            raise ValueError("Duplicate KEXIM currencies: " + ", ".join(duplicates))

        official_map = official.set_index("currency")["spot_rate_krw_per_unit"]
        missing = sorted(set(required) - set(official_map.dropna().index))
        if missing:
            raise ValueError(
                "KEXIM reference rates are missing required currencies: "
                + ", ".join(missing)
            )

        selected = base.copy(deep=True)
        selected["spot_rate_krw"] = selected["currency"].map(official_map).astype(float)
        observation_text = str(kexim_snapshot.get("observation_date") or "").strip()
        if len(observation_text) != 8 or not observation_text.isdigit():
            raise ValueError("KEXIM observation_date must be YYYYMMDD")
        observation = datetime.strptime(observation_text, "%Y%m%d").date()
        stale_days = (as_of - observation).days
        if stale_days < 0:
            raise ValueError("KEXIM observation date cannot be after the requested as-of date")
        is_stale = stale_days > stale_after_days
        retrieved_at = kexim_snapshot.get("retrieved_at")
        response_hash = kexim_snapshot.get("response_hash")
        selected = _annotate(
            selected,
            spot_source="Korea Eximbank official public reference rate",
            interest_rate_source="bundled sample interest-rate assumptions",
            observation_date=observation.isoformat(),
            retrieved_at=str(retrieved_at) if retrieved_at else None,
            response_hash=str(response_hash) if response_hash else None,
            stale_days=stale_days,
            is_stale=is_stale,
        )
        return FXInputSelection(
            rates=selected,
            requested_source=source,
            applied_source="kexim_reference_spot",
            required_currencies=required,
            requested_as_of_date=as_of.isoformat(),
            observation_date=observation.isoformat(),
            retrieved_at=str(retrieved_at) if retrieved_at else None,
            response_hash=str(response_hash) if response_hash else None,
            stale_days=stale_days,
            is_stale=is_stale,
            used_fallback=False,
            fallback_reason=None,
            limitations=(
                "Korea Eximbank data is an official public reference rate, not an executable KB customer quote.",
                "Only spot_rate_krw was replaced; interest rates remain separately labelled sample assumptions.",
                "Theoretical forwards are interest-parity calculations and not live bank forward quotations.",
            ),
        )
    except (TypeError, ValueError) as exc:
        if allow_bundled_fallback:
            return _bundled_selection(
                base_rates,
                required,
                source,
                as_of,
                fallback_reason=fallback_reason or str(exc),
            )
        raise
