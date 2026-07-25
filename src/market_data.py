"""Validated market-data provider interfaces.

Bundled CSV values are static sample assumptions and are not real-time quotes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from .validators import validate_fx_rates


class SpotRateProvider(ABC):
    """Interface for retrieving a KRW spot rate by foreign currency."""

    @abstractmethod
    def get_spot_rate(self, currency: str) -> float:
        """Return KRW per one unit of the requested foreign currency."""


class CsvSpotRateProvider(SpotRateProvider):
    """Spot provider backed by validated user or bundled CSV data."""

    def __init__(self, source: str | Path | pd.DataFrame):
        raw = source.copy() if isinstance(source, pd.DataFrame) else pd.read_csv(source)
        self._rates = validate_fx_rates(raw).set_index("currency")

    @property
    def rates(self) -> pd.DataFrame:
        return self._rates.reset_index().copy()

    def get_spot_rate(self, currency: str) -> float:
        normalized = currency.strip().upper()
        if normalized not in self._rates.index:
            raise ValueError(f"Unsupported currency; no FX rate provided for: {normalized}")
        return float(self._rates.loc[normalized, "spot_rate_krw"])

    def get_rate_inputs(self, currency: str) -> dict[str, float]:
        normalized = currency.strip().upper()
        if normalized not in self._rates.index:
            raise ValueError(f"Unsupported currency; no FX rate provided for: {normalized}")
        row = self._rates.loc[normalized]
        return {
            "spot_rate_krw": float(row["spot_rate_krw"]),
            "krw_interest_rate": float(row["krw_interest_rate"]),
            "foreign_interest_rate": float(row["foreign_interest_rate"]),
        }
