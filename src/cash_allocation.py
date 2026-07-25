"""Auditable foreign-currency cash allocation to import funding."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .validators import validate_transactions

REQUIRED_ALLOCATION_COLUMNS = {
    "currency",
    "transaction_id",
    "allocation_amount",
    "allocation_date",
}


@dataclass(frozen=True)
class CashAllocationResult:
    allocation_table: pd.DataFrame
    unallocated_foreign_cash: pd.DataFrame
    import_funding_gap_by_transaction: pd.DataFrame
    import_funding_gap_by_currency: pd.DataFrame
    funding_gap_timing: pd.DataFrame


def allocate_foreign_cash(
    transactions: pd.DataFrame,
    foreign_cash: dict[str, float],
    allocations: pd.DataFrame | None = None,
) -> CashAllocationResult:
    """Validate allocations without changing economic or transaction exposure."""

    validated = validate_transactions(transactions)
    cash = {str(key).upper(): float(value) for key, value in foreign_cash.items()}
    if any(value < 0 for value in cash.values()):
        raise ValueError("foreign cash amounts must be non-negative")
    imports = validated[validated["transaction_type"] == "import"].copy()

    if allocations is None or allocations.empty:
        allocation_table = pd.DataFrame(columns=sorted(REQUIRED_ALLOCATION_COLUMNS))
    else:
        missing = sorted(REQUIRED_ALLOCATION_COLUMNS - set(allocations.columns))
        if missing:
            raise ValueError(f"Missing allocation columns: {', '.join(missing)}")
        allocation_table = allocations.copy()
        allocation_table["currency"] = (
            allocation_table["currency"].astype(str).str.strip().str.upper()
        )
        allocation_table["allocation_amount"] = pd.to_numeric(
            allocation_table["allocation_amount"], errors="raise"
        ).astype(float)
        if (allocation_table["allocation_amount"] <= 0).any():
            raise ValueError("allocation_amount must be positive")
        allocation_table["allocation_date"] = pd.to_datetime(
            allocation_table["allocation_date"], errors="raise"
        )
        import_lookup = imports.set_index("transaction_id")
        for row in allocation_table.itertuples(index=False):
            if row.transaction_id not in import_lookup.index:
                raise ValueError(
                    f"Allocation target must be an import transaction: {row.transaction_id}"
                )
            target = import_lookup.loc[row.transaction_id]
            if row.currency != target["currency"]:
                raise ValueError(
                    f"Allocation currency {row.currency} does not match "
                    f"{row.transaction_id} currency {target['currency']}"
                )
        by_currency = allocation_table.groupby("currency")["allocation_amount"].sum()
        for currency, amount in by_currency.items():
            if amount > cash.get(currency, 0.0):
                raise ValueError(
                    f"Allocated {currency} cash exceeds available foreign cash"
                )
        by_transaction = allocation_table.groupby("transaction_id")[
            "allocation_amount"
        ].sum()
        for transaction_id, amount in by_transaction.items():
            obligation = float(import_lookup.loc[transaction_id, "amount_fc"])
            if amount > obligation:
                raise ValueError(
                    f"Allocation exceeds import obligation for {transaction_id}"
                )

    allocated_by_currency = (
        allocation_table.groupby("currency")["allocation_amount"].sum().to_dict()
        if not allocation_table.empty
        else {}
    )
    allocated_by_transaction = (
        allocation_table.groupby("transaction_id")["allocation_amount"].sum().to_dict()
        if not allocation_table.empty
        else {}
    )
    unallocated = pd.DataFrame(
        [
            {
                "currency": currency,
                "available_foreign_cash": amount,
                "allocated_foreign_cash": allocated_by_currency.get(currency, 0.0),
                "unallocated_foreign_cash": amount
                - allocated_by_currency.get(currency, 0.0),
            }
            for currency, amount in sorted(cash.items())
        ]
    )
    gaps = imports[
        ["transaction_id", "currency", "amount_fc", "expected_date"]
    ].copy()
    gaps["allocated_foreign_cash"] = gaps["transaction_id"].map(
        allocated_by_transaction
    ).fillna(0.0)
    gaps["import_funding_gap_fc"] = (
        gaps["amount_fc"] - gaps["allocated_foreign_cash"]
    )
    by_currency_gap = (
        gaps.groupby("currency", as_index=False)
        .agg(
            import_obligations_fc=("amount_fc", "sum"),
            allocated_foreign_cash=("allocated_foreign_cash", "sum"),
            import_funding_gap_fc=("import_funding_gap_fc", "sum"),
        )
    )
    timing = gaps[
        ["transaction_id", "currency", "expected_date", "import_funding_gap_fc"]
    ].sort_values(["expected_date", "currency", "transaction_id"])
    return CashAllocationResult(
        allocation_table.reset_index(drop=True),
        unallocated,
        gaps,
        by_currency_gap,
        timing,
    )
