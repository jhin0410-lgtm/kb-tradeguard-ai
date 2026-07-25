"""Per-currency transaction exposure, cash assets, and economic FX positions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from .validators import validate_fx_rates, validate_transactions


@dataclass(frozen=True)
class ExposureResult:
    """Structured positions kept separate by currency until KRW conversion."""

    by_currency: pd.DataFrame
    consolidated_nominal_transaction_exposure_krw: float | None = None
    consolidated_expected_transaction_exposure_krw: float | None = None
    consolidated_foreign_cash_position_krw: float | None = None
    consolidated_nominal_total_economic_position_krw: float | None = None
    consolidated_expected_total_economic_position_krw: float | None = None

    def row_for(self, currency: str) -> pd.Series:
        """Return one currency row or raise a clear error."""

        normalized = currency.strip().upper()
        rows = self.by_currency[self.by_currency["currency"] == normalized]
        if rows.empty:
            raise ValueError(f"Currency not present in exposure result: {normalized}")
        return rows.iloc[0]


def _normalize_amounts(
    values: Mapping[str, float] | float,
    field_name: str,
) -> dict[str, float]:
    if isinstance(values, Mapping):
        normalized = {
            str(currency).strip().upper(): float(amount)
            for currency, amount in values.items()
        }
    else:
        normalized = {"USD": float(values)}
    if any(amount < 0 for amount in normalized.values()):
        raise ValueError(f"{field_name} amounts must be non-negative")
    return normalized


def calculate_exposure(
    transactions: pd.DataFrame,
    foreign_cash_held: Mapping[str, float] | float = 0.0,
    fx_rates: pd.DataFrame | None = None,
    allocated_foreign_cash: Mapping[str, float] | float | None = None,
) -> ExposureResult:
    """Calculate distinct transaction, cash, economic, and funding positions.

    Foreign cash is a positive economic FX asset. It is never subtracted from
    transaction exposure. Import-funding allocation is optional, defaults to
    zero, and affects only ``import_funding_gap_fc``.
    """

    foreign_cash = _normalize_amounts(foreign_cash_held, "foreign cash")
    allocated = (
        _normalize_amounts(allocated_foreign_cash, "allocated foreign cash")
        if allocated_foreign_cash is not None
        else {}
    )
    for currency, amount in allocated.items():
        if amount > foreign_cash.get(currency, 0.0):
            raise ValueError(
                f"Allocated foreign cash for {currency} exceeds available foreign cash"
            )

    rates = validate_fx_rates(fx_rates) if fx_rates is not None else None
    validated = validate_transactions(
        transactions, rates if rates is not None else None
    )
    currencies = sorted(
        set(validated["currency"]) | set(foreign_cash) | set(allocated)
    )
    rows: list[dict[str, float | str]] = []
    for currency in currencies:
        subset = validated[validated["currency"] == currency]
        export_mask = subset["transaction_type"] == "export"
        import_mask = subset["transaction_type"] == "import"
        nominal_exports = float(subset.loc[export_mask, "amount_fc"].sum())
        nominal_imports = float(subset.loc[import_mask, "amount_fc"].sum())
        expected_amount = subset["amount_fc"] * subset["probability"]
        expected_exports = float(expected_amount[export_mask].sum())
        expected_imports = float(expected_amount[import_mask].sum())
        cash = foreign_cash.get(currency, 0.0)
        cash_allocated = allocated.get(currency, 0.0)
        nominal_transaction = nominal_exports - nominal_imports
        expected_transaction = expected_exports - expected_imports

        rows.append(
            {
                "currency": currency,
                "nominal_export_exposure": nominal_exports,
                "expected_export_exposure": expected_exports,
                "nominal_import_exposure": nominal_imports,
                "expected_import_exposure": expected_imports,
                "nominal_transaction_exposure": nominal_transaction,
                "expected_transaction_exposure": expected_transaction,
                "foreign_cash_position": cash,
                "nominal_total_economic_position": nominal_transaction + cash,
                "expected_total_economic_position": expected_transaction + cash,
                "available_foreign_cash": cash,
                "allocated_foreign_cash_to_imports": cash_allocated,
                "import_funding_gap_fc": max(
                    nominal_imports - cash_allocated, 0.0
                ),
                "position_classification": (
                    "Balance-sheet foreign-currency asset position"
                    if nominal_exports == 0 and nominal_imports == 0 and cash > 0
                    else "Transaction and/or cash FX position"
                ),
            }
        )

    by_currency = pd.DataFrame(rows)
    consolidated: dict[str, float | None] = {
        "nominal_transaction": None,
        "expected_transaction": None,
        "cash": None,
        "nominal_total": None,
        "expected_total": None,
    }
    if rates is not None:
        rate_map = rates.set_index("currency")["spot_rate_krw"]
        missing = sorted(set(currencies) - set(rate_map.index))
        if missing:
            raise ValueError(f"No FX rate provided for: {', '.join(missing)}")
        by_currency["spot_rate_krw"] = by_currency["currency"].map(rate_map)
        krw_columns = {
            "nominal_transaction_exposure": "nominal_transaction_exposure_krw",
            "expected_transaction_exposure": "expected_transaction_exposure_krw",
            "foreign_cash_position": "foreign_cash_position_krw",
            "nominal_total_economic_position": "nominal_total_economic_position_krw",
            "expected_total_economic_position": "expected_total_economic_position_krw",
            "import_funding_gap_fc": "import_funding_gap_krw",
        }
        for source, target in krw_columns.items():
            by_currency[target] = by_currency[source] * by_currency["spot_rate_krw"]
        consolidated = {
            "nominal_transaction": float(
                by_currency["nominal_transaction_exposure_krw"].sum()
            ),
            "expected_transaction": float(
                by_currency["expected_transaction_exposure_krw"].sum()
            ),
            "cash": float(by_currency["foreign_cash_position_krw"].sum()),
            "nominal_total": float(
                by_currency["nominal_total_economic_position_krw"].sum()
            ),
            "expected_total": float(
                by_currency["expected_total_economic_position_krw"].sum()
            ),
        }

    return ExposureResult(
        by_currency=by_currency,
        consolidated_nominal_transaction_exposure_krw=consolidated[
            "nominal_transaction"
        ],
        consolidated_expected_transaction_exposure_krw=consolidated[
            "expected_transaction"
        ],
        consolidated_foreign_cash_position_krw=consolidated["cash"],
        consolidated_nominal_total_economic_position_krw=consolidated[
            "nominal_total"
        ],
        consolidated_expected_total_economic_position_krw=consolidated[
            "expected_total"
        ],
    )
