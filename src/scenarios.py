"""Deterministic USD/KRW exchange-rate scenario analysis."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

DEFAULT_SCENARIOS = (-0.10, -0.05, 0.0, 0.05, 0.10)


def calculate_scenarios(
    net_exposure: float,
    base_exchange_rate: float,
    scenario_percentages: Iterable[float] = DEFAULT_SCENARIOS,
) -> pd.DataFrame:
    """Value USD net exposure in KRW under percentage rate shocks."""

    if base_exchange_rate <= 0:
        raise ValueError("base_exchange_rate must be positive")

    scenarios = [float(value) for value in scenario_percentages]
    if not scenarios:
        raise ValueError("At least one scenario percentage is required")

    base_value = float(net_exposure) * float(base_exchange_rate)
    rows = []
    for percentage in scenarios:
        scenario_rate = float(base_exchange_rate) * (1 + percentage)
        krw_value = float(net_exposure) * scenario_rate
        rows.append(
            {
                "scenario_pct": percentage,
                "scenario_label": f"{percentage:+.0%}",
                "exchange_rate": scenario_rate,
                "net_exposure_krw": krw_value,
                "change_vs_base_krw": krw_value - base_value,
            }
        )
    return pd.DataFrame(rows)
