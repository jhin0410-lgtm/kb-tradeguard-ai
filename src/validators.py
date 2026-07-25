"""Input validation for transaction data."""

from __future__ import annotations

from datetime import date
from collections.abc import Collection
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

REQUIRED_TRANSACTION_COLUMNS = {
    "transaction_id",
    "transaction_type",
    "currency",
    "amount_fc",
    "probability",
    "status",
    "expected_date",
}

REQUIRED_FX_RATE_COLUMNS = {
    "currency",
    "spot_rate_krw",
    "krw_interest_rate",
    "foreign_interest_rate",
}


class TransactionRecord(BaseModel):
    """Validated representation of a supported transaction."""

    model_config = ConfigDict(str_strip_whitespace=True)

    transaction_id: str = Field(min_length=1)
    transaction_type: Literal["export", "import"]
    currency: str = Field(min_length=1)
    amount_fc: float = Field(gt=0)
    probability: float = Field(ge=0, le=1)
    status: Literal["confirmed", "expected"]
    expected_date: date
    invoice_date: date | None = None


def validate_fx_rates(fx_rates: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize a KRW spot/interest-rate table."""

    if not isinstance(fx_rates, pd.DataFrame):
        raise TypeError("fx_rates must be a pandas DataFrame")
    missing = sorted(REQUIRED_FX_RATE_COLUMNS - set(fx_rates.columns))
    if missing:
        raise ValueError(f"Missing required FX-rate columns: {', '.join(missing)}")
    if fx_rates.empty:
        raise ValueError("At least one FX-rate row is required")

    validated = fx_rates.copy()
    validated["currency"] = validated["currency"].astype(str).str.strip().str.upper()
    if (validated["currency"] == "").any():
        raise ValueError("FX currency must not be blank")
    if validated["currency"].duplicated().any():
        duplicates = sorted(validated.loc[validated["currency"].duplicated(), "currency"])
        raise ValueError(f"Duplicate FX currencies: {', '.join(duplicates)}")

    for column in ("spot_rate_krw", "krw_interest_rate", "foreign_interest_rate"):
        try:
            validated[column] = pd.to_numeric(validated[column], errors="raise").astype(float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{column} must be numeric") from exc
    if (validated["spot_rate_krw"] <= 0).any():
        raise ValueError("All spot_rate_krw values must be positive")
    return validated


def validate_transactions(
    transactions: pd.DataFrame,
    supported_currencies: Collection[str] | pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Validate and normalize a transaction DataFrame.

    The returned frame is a copy. Dates are normalized to pandas timestamps,
    numeric columns are floats, and unsupported currencies are rejected.
    """

    if not isinstance(transactions, pd.DataFrame):
        raise TypeError("transactions must be a pandas DataFrame")

    missing = sorted(REQUIRED_TRANSACTION_COLUMNS - set(transactions.columns))
    if missing:
        raise ValueError(f"Missing required transaction columns: {', '.join(missing)}")
    if transactions.empty:
        raise ValueError("At least one transaction is required")

    records: list[dict] = []
    for row_number, row in enumerate(transactions.to_dict(orient="records"), start=2):
        payload = {
            key: (None if pd.isna(value) else value)
            for key, value in row.items()
            if key in TransactionRecord.model_fields
        }
        try:
            record = TransactionRecord.model_validate(payload)
        except ValidationError as exc:
            messages = "; ".join(
                f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
                for error in exc.errors()
            )
            raise ValueError(f"Invalid transaction at CSV row {row_number}: {messages}") from exc
        records.append(record.model_dump())

    validated = transactions.copy()
    normalized = pd.DataFrame(records)
    for column in normalized.columns:
        if column in validated.columns or column == "invoice_date":
            validated[column] = normalized[column]

    validated["amount_fc"] = validated["amount_fc"].astype(float)
    validated["probability"] = validated["probability"].astype(float)
    validated["currency"] = validated["currency"].str.upper()
    validated["expected_date"] = pd.to_datetime(validated["expected_date"])
    if "invoice_date" in validated.columns:
        validated["invoice_date"] = pd.to_datetime(validated["invoice_date"])

    if supported_currencies is not None:
        if isinstance(supported_currencies, pd.DataFrame):
            supported = set(validate_fx_rates(supported_currencies)["currency"])
        else:
            supported = {str(value).strip().upper() for value in supported_currencies}
        unsupported = sorted(set(validated["currency"]) - supported)
        if unsupported:
            raise ValueError(
                "Unsupported transaction currency; no FX rate provided for: "
                + ", ".join(unsupported)
            )
    return validated
