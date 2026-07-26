"""Explicit execution contract for governed FX-shock scenario analysis.

The contract translates a disclosed Copilot shock assumption into the exact inputs
required by the existing deterministic hedge-ratio comparison tool. It performs no
financial arithmetic itself.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .copilot_scenarios import ScenarioExecutionRequest


class FXShockExecutionContract(BaseModel):
    currencies: list[str]
    analysis_basis: str = "Expected transaction exposure"
    scenario_percentages: list[float]
    hedge_ratios: list[float] = Field(default_factory=lambda: [0.0, 0.3, 0.5, 0.7, 1.0])
    tenor_months: int = 3
    spread: float = 0.0

    @field_validator("currencies")
    @classmethod
    def currencies_required(cls, value: list[str]) -> list[str]:
        normalized = sorted({str(item).upper() for item in value if str(item).strip()})
        if not normalized:
            raise ValueError("FX-shock execution requires at least one currency.")
        return normalized

    @field_validator("scenario_percentages")
    @classmethod
    def shocks_must_be_fractional(cls, value: list[float]) -> list[float]:
        normalized = [float(item) for item in value]
        if not normalized:
            raise ValueError("FX-shock execution requires at least one scenario percentage.")
        if any(item <= -1.0 for item in normalized):
            raise ValueError("FX scenario percentages must remain above -100%.")
        return normalized

    @field_validator("hedge_ratios")
    @classmethod
    def hedge_ratios_bounded(cls, value: list[float]) -> list[float]:
        normalized = [float(item) for item in value]
        if not normalized or any(item < 0 or item > 1 for item in normalized):
            raise ValueError("Hedge ratios must be between 0 and 1.")
        return normalized

    @field_validator("tenor_months")
    @classmethod
    def tenor_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Tenor months must be positive.")
        return value

    @field_validator("spread")
    @classmethod
    def spread_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("Spread must be non-negative.")
        return float(value)


def build_fx_shock_execution_contract(
    request: ScenarioExecutionRequest,
) -> FXShockExecutionContract:
    """Build a fully explicit deterministic execution contract from a request."""

    if request.execution_tool != "compare_hedge_ratios":
        raise ValueError("Request is not an FX hedge-ratio comparison scenario.")

    changes = request.parameter_changes
    if "fx_shock_percent" not in changes:
        raise ValueError("FX-shock request must disclose fx_shock_percent.")

    shock_percent = float(changes["fx_shock_percent"])
    shock_fraction = shock_percent / 100.0
    if shock_percent <= -100:
        raise ValueError("FX shock must remain above -100%.")

    return FXShockExecutionContract(
        currencies=list(changes.get("currencies") or []),
        analysis_basis=str(
            changes.get("analysis_basis") or "Expected transaction exposure"
        ),
        scenario_percentages=[shock_fraction],
        hedge_ratios=list(changes.get("hedge_ratios") or [0.0, 0.3, 0.5, 0.7, 1.0]),
        tenor_months=int(changes.get("tenor_months") or 3),
        spread=float(changes.get("spread") or 0.0),
    )
