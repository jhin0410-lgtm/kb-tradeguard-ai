"""Deterministic single-company, multi-transaction portfolio assessment.

The existing single-transaction pipeline remains the authoritative document and
transaction decision engine.  This module sits above it and aggregates approved
transactions into currency exposure, expected liquidity, stress, and consultation
preparation views without silently approving a trade or executing a hedge.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..copilot_case import UnifiedCopilotCase
from .product_matching import (
    ProductMatchingResult,
    TradeFinanceNeedProfile,
    match_trade_finance_products,
)

TransactionDirection = Literal["export", "import"]
TransactionStage = Literal[
    "pre_contract", "pre_shipment", "post_shipment", "pre_payment", "ongoing"
]


def _decimal(value: Any, *, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not result.is_finite():
        raise ValueError(f"{label} must be finite")
    return result


def _month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _iter_months(start: date, end: date):
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield f"{year:04d}-{month:02d}"
        month += 1
        if month == 13:
            year += 1
            month = 1


class PortfolioTransaction(BaseModel):
    """Validated transaction subset used by the portfolio layer."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    transaction_id: str
    transaction_type: TransactionDirection
    currency: str
    amount_fc: Decimal = Field(gt=0)
    expected_date: date | None = None
    probability: Decimal = Field(default=Decimal("1"), ge=0, le=1)
    status: str = "expected"
    country_code: str | None = None
    payment_method: str | None = None
    transaction_stage: TransactionStage | None = None
    tenor_days: int | None = Field(default=None, ge=0)
    advance_payment_percent: Decimal | None = Field(default=None, ge=0, le=100)
    company_size: Literal["sme", "mid_market", "large", "unknown"] = "unknown"
    preferred_bank: str | None = None
    industry_tags: list[str] = Field(default_factory=list)
    available_documents: list[str] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a three-letter code")
        return normalized

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("country_code must be a two-letter code")
        return normalized


class CurrencyExposure(BaseModel):
    currency: str
    reference_rate_krw: Decimal | None = None
    export_receivables_fc: Decimal
    import_payables_fc: Decimal
    foreign_cash_fc: Decimal
    gross_trade_exposure_fc: Decimal
    natural_offset_fc: Decimal
    natural_hedge_ratio_percent: Decimal
    net_exposure_fc: Decimal
    net_exposure_krw: Decimal | None = None
    net_direction: Literal["long", "short", "flat"]
    transaction_ids: list[str]


class LiquidityBucket(BaseModel):
    period: str
    expected_inflow_krw: Decimal
    expected_outflow_krw: Decimal
    fixed_cost_krw: Decimal
    net_cashflow_krw: Decimal
    ending_cash_krw: Decimal
    transaction_ids: list[str] = Field(default_factory=list)
    missing_currency_rates: list[str] = Field(default_factory=list)


class PortfolioStressPoint(BaseModel):
    shock_percent: Decimal
    estimated_fx_value_change_krw: Decimal
    impacted_currencies: list[str] = Field(default_factory=list)


class PortfolioAssessment(BaseModel):
    assessment_version: str = "trade-portfolio/1.0"
    case_id: str
    company_name: str | None
    source_case_hash: str
    transaction_count: int
    currency_count: int
    currency_exposures: list[CurrencyExposure]
    liquidity_buckets: list[LiquidityBucket]
    stress_points: list[PortfolioStressPoint]
    gross_exposure_krw: Decimal | None
    net_exposure_krw: Decimal | None
    largest_currency_concentration_percent: Decimal | None
    missing_inputs: list[str] = Field(default_factory=list)
    official_data_status: dict[str, str] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    authority_boundary: str = (
        "Portfolio aggregation is deterministic decision support. It does not execute "
        "foreign-exchange trades, approve financing, confirm product eligibility, or "
        "replace bank, insurer, legal, customs, or compliance review."
    )


class CompanyPortfolioWorkspace(BaseModel):
    """Lightweight company switcher, not a multi-tenant security boundary."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    workspace_id: str
    companies: dict[str, UnifiedCopilotCase]
    active_company_id: str
    operating_scope: str = (
        "One analyst may switch between isolated demonstration company cases. "
        "Authentication, tenant isolation, entitlements, and customer-data storage "
        "are intentionally outside this competition prototype."
    )

    @model_validator(mode="after")
    def active_company_exists(self):
        if not self.companies:
            raise ValueError("Workspace must contain at least one company case")
        if self.active_company_id not in self.companies:
            raise ValueError("active_company_id must reference a known company case")
        return self

    @property
    def active_case(self) -> UnifiedCopilotCase:
        return self.companies[self.active_company_id]

    def switch_company(self, company_id: str) -> "CompanyPortfolioWorkspace":
        if company_id not in self.companies:
            raise ValueError(f"Unknown company workspace ID: {company_id}")
        return self.model_copy(update={"active_company_id": company_id})


def _currency_and_unit(value: Any) -> tuple[str | None, Decimal]:
    text = str(value or "").strip().upper()
    if not text:
        return None, Decimal("1")
    if "(" in text and text.endswith(")"):
        code, raw_unit = text[:-1].split("(", 1)
        if raw_unit.isdigit() and int(raw_unit) > 0:
            return code, Decimal(raw_unit)
    return text, Decimal("1")


def extract_reference_rates(case: UnifiedCopilotCase) -> dict[str, Decimal]:
    """Return KRW rates normalized to one unit of foreign currency."""

    asset = case.official_fx_reference
    if asset is None or asset.status not in {"available", "partial"} or asset.payload is None:
        return {}
    payload: Any = asset.payload
    if isinstance(payload, dict):
        if all(isinstance(value, (int, float, Decimal, str)) for value in payload.values()):
            rows = [
                {"currency": currency, "spot_rate_krw": value}
                for currency, value in payload.items()
            ]
        else:
            rows = [payload]
    else:
        rows = payload

    rates: dict[str, Decimal] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        currency, unit = _currency_and_unit(
            row.get("currency") or row.get("currency_unit") or row.get("cur_unit")
        )
        raw_rate = (
            row.get("spot_rate_krw")
            if row.get("spot_rate_krw") is not None
            else row.get("deal_base_rate", row.get("rate"))
        )
        if currency is None or raw_rate in (None, ""):
            continue
        try:
            rate = _decimal(raw_rate, label=f"{currency} reference rate") / unit
        except ValueError:
            continue
        if rate > 0:
            rates[currency] = rate
    return rates


def _validated_transactions(case: UnifiedCopilotCase) -> list[PortfolioTransaction]:
    transactions = [
        PortfolioTransaction.model_validate(item) for item in case.approved_transactions
    ]
    if not transactions:
        raise ValueError("Portfolio assessment requires at least one approved transaction")
    identifiers = [item.transaction_id for item in transactions]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Approved transaction IDs must be unique for portfolio assessment")
    return transactions


def _foreign_cash(case: UnifiedCopilotCase) -> dict[str, Decimal]:
    positions: dict[str, Decimal] = defaultdict(Decimal)
    for row in case.foreign_cash_positions:
        currency = str(row.get("currency") or "").strip().upper()
        if len(currency) != 3:
            raise ValueError("Foreign-cash positions require three-letter currency codes")
        amount = _decimal(
            row.get("amount_fc", row.get("amount")),
            label=f"{currency} foreign-cash amount",
        )
        positions[currency] += amount
    return dict(positions)


def _build_exposures(
    transactions: list[PortfolioTransaction],
    cash_positions: dict[str, Decimal],
    rates: dict[str, Decimal],
) -> list[CurrencyExposure]:
    exports: dict[str, Decimal] = defaultdict(Decimal)
    imports: dict[str, Decimal] = defaultdict(Decimal)
    transaction_ids: dict[str, list[str]] = defaultdict(list)

    for transaction in transactions:
        if transaction.transaction_type == "export":
            exports[transaction.currency] += transaction.amount_fc
        else:
            imports[transaction.currency] += transaction.amount_fc
        transaction_ids[transaction.currency].append(transaction.transaction_id)

    currencies = sorted(set(exports) | set(imports) | set(cash_positions))
    rows: list[CurrencyExposure] = []
    for currency in currencies:
        export_amount = exports[currency]
        import_amount = imports[currency]
        cash_amount = cash_positions.get(currency, Decimal("0"))
        gross = export_amount + import_amount
        natural_offset = min(export_amount, import_amount)
        larger_leg = max(export_amount, import_amount)
        natural_ratio = (
            natural_offset / larger_leg * Decimal("100")
            if larger_leg > 0
            else Decimal("0")
        )
        net = export_amount + cash_amount - import_amount
        direction: Literal["long", "short", "flat"]
        if net > 0:
            direction = "long"
        elif net < 0:
            direction = "short"
        else:
            direction = "flat"
        rate = rates.get(currency)
        rows.append(
            CurrencyExposure(
                currency=currency,
                reference_rate_krw=rate,
                export_receivables_fc=export_amount,
                import_payables_fc=import_amount,
                foreign_cash_fc=cash_amount,
                gross_trade_exposure_fc=gross,
                natural_offset_fc=natural_offset,
                natural_hedge_ratio_percent=natural_ratio.quantize(Decimal("0.01")),
                net_exposure_fc=net,
                net_exposure_krw=(net * rate if rate is not None else None),
                net_direction=direction,
                transaction_ids=sorted(transaction_ids.get(currency, [])),
            )
        )
    return rows


def _build_liquidity(
    case: UnifiedCopilotCase,
    transactions: list[PortfolioTransaction],
    rates: dict[str, Decimal],
    missing_inputs: list[str],
) -> list[LiquidityBucket]:
    dated = [item for item in transactions if item.expected_date is not None]
    undated = sorted(
        item.transaction_id for item in transactions if item.expected_date is None
    )
    if undated:
        missing_inputs.append(
            "expected_date for transactions: " + ", ".join(undated)
        )
    if not dated:
        return []

    opening_cash_raw = case.monthly_cost_assumptions.get("current_cash_krw")
    fixed_cost_raw = case.monthly_cost_assumptions.get("monthly_fixed_cost_krw")
    if opening_cash_raw in (None, ""):
        opening_cash = Decimal("0")
        missing_inputs.append("current_cash_krw")
    else:
        opening_cash = _decimal(opening_cash_raw, label="current_cash_krw")
    if fixed_cost_raw in (None, ""):
        fixed_cost = Decimal("0")
        missing_inputs.append("monthly_fixed_cost_krw")
    else:
        fixed_cost = _decimal(fixed_cost_raw, label="monthly_fixed_cost_krw")

    start = min(item.expected_date for item in dated if item.expected_date is not None)
    end = max(item.expected_date for item in dated if item.expected_date is not None)
    raw: dict[str, dict[str, Any]] = {
        period: {
            "inflow": Decimal("0"),
            "outflow": Decimal("0"),
            "transaction_ids": [],
            "missing_rates": set(),
        }
        for period in _iter_months(start, end)
    }
    for transaction in dated:
        assert transaction.expected_date is not None
        period = _month_key(transaction.expected_date)
        rate = rates.get(transaction.currency)
        raw[period]["transaction_ids"].append(transaction.transaction_id)
        if rate is None:
            raw[period]["missing_rates"].add(transaction.currency)
            continue
        expected_krw = transaction.amount_fc * transaction.probability * rate
        if transaction.transaction_type == "export":
            raw[period]["inflow"] += expected_krw
        else:
            raw[period]["outflow"] += expected_krw

    ending_cash = opening_cash
    result: list[LiquidityBucket] = []
    for period, values in raw.items():
        net = values["inflow"] - values["outflow"] - fixed_cost
        ending_cash += net
        result.append(
            LiquidityBucket(
                period=period,
                expected_inflow_krw=values["inflow"],
                expected_outflow_krw=values["outflow"],
                fixed_cost_krw=fixed_cost,
                net_cashflow_krw=net,
                ending_cash_krw=ending_cash,
                transaction_ids=sorted(values["transaction_ids"]),
                missing_currency_rates=sorted(values["missing_rates"]),
            )
        )
    return result


def _build_stress_points(
    exposures: list[CurrencyExposure],
    shock_percentages: tuple[int | float | Decimal, ...],
) -> list[PortfolioStressPoint]:
    rows: list[PortfolioStressPoint] = []
    for raw_shock in shock_percentages:
        shock = _decimal(raw_shock, label="FX shock percent")
        impact = Decimal("0")
        currencies: list[str] = []
        for exposure in exposures:
            if exposure.net_exposure_krw is None or exposure.net_exposure_krw == 0:
                continue
            impact += exposure.net_exposure_krw * shock / Decimal("100")
            currencies.append(exposure.currency)
        rows.append(
            PortfolioStressPoint(
                shock_percent=shock,
                estimated_fx_value_change_krw=impact,
                impacted_currencies=sorted(currencies),
            )
        )
    return rows


def analyze_trade_portfolio(
    case: UnifiedCopilotCase,
    *,
    shock_percentages: tuple[int | float | Decimal, ...] = (-10, -5, 5, 10),
) -> PortfolioAssessment:
    """Aggregate one company's approved transactions without mutating the case."""

    transactions = _validated_transactions(case)
    rates = extract_reference_rates(case)
    cash_positions = _foreign_cash(case)
    missing_inputs: list[str] = []
    exposures = _build_exposures(transactions, cash_positions, rates)
    for exposure in exposures:
        if exposure.reference_rate_krw is None:
            missing_inputs.append(f"FX reference for currency: {exposure.currency}")

    liquidity = _build_liquidity(case, transactions, rates, missing_inputs)
    stress = _build_stress_points(exposures, shock_percentages)

    valued = [item for item in exposures if item.reference_rate_krw is not None]
    if len(valued) == len(exposures):
        gross_krw = sum(
            item.gross_trade_exposure_fc * item.reference_rate_krw
            for item in valued
            if item.reference_rate_krw is not None
        )
        net_krw = sum(
            item.net_exposure_krw or Decimal("0") for item in valued
        )
        largest = max(
            (
                item.gross_trade_exposure_fc * item.reference_rate_krw
                for item in valued
                if item.reference_rate_krw is not None
            ),
            default=Decimal("0"),
        )
        concentration = (
            largest / gross_krw * Decimal("100")
            if gross_krw > 0
            else Decimal("0")
        )
    else:
        gross_krw = None
        net_krw = None
        concentration = None

    official_status = {
        key: asset.status for key, asset in sorted(case.official_data_assets.items())
    }
    return PortfolioAssessment(
        case_id=case.identity.case_id,
        company_name=case.identity.company_name,
        source_case_hash=case.case_hash,
        transaction_count=len(transactions),
        currency_count=len(exposures),
        currency_exposures=exposures,
        liquidity_buckets=liquidity,
        stress_points=stress,
        gross_exposure_krw=gross_krw,
        net_exposure_krw=net_krw,
        largest_currency_concentration_percent=(
            concentration.quantize(Decimal("0.01"))
            if concentration is not None
            else None
        ),
        missing_inputs=list(dict.fromkeys(missing_inputs)),
        official_data_status=official_status,
        limitations=[
            "Expected liquidity applies declared probabilities and reviewed reference rates; it is not a cash forecast guarantee.",
            "Uniform FX shocks are disclosed sensitivities, not exchange-rate forecasts or executable hedge quotes.",
            "Natural offset is calculated from approved receivables and payables in the same currency; legal set-off and timing mismatch are not assumed away.",
        ],
    )


def _infer_stage(transaction: PortfolioTransaction) -> TransactionStage:
    if transaction.transaction_stage is not None:
        return transaction.transaction_stage
    status = transaction.status.lower()
    if transaction.transaction_type == "export":
        if any(token in status for token in ("shipped", "post", "invoiced", "receivable")):
            return "post_shipment"
        return "pre_shipment"
    if any(token in status for token in ("paid", "settled", "ongoing")):
        return "ongoing"
    return "pre_payment"


def infer_portfolio_need_profiles(
    case: UnifiedCopilotCase,
) -> list[TradeFinanceNeedProfile]:
    """Translate explicit transaction context into reviewable product-need profiles."""

    profiles: list[TradeFinanceNeedProfile] = []
    for transaction in _validated_transactions(case):
        stage = _infer_stage(transaction)
        payment = (transaction.payment_method or "").lower()
        needs: list[str] = [
            "fx_cashflow_certainty",
            "forward_exchange_hedging",
            "fx_order_management",
        ]
        if transaction.transaction_type == "export":
            needs.extend(
                [
                    "buyer_credit_investigation",
                    "export_receivable_nonpayment_protection",
                    "trade_receivable_collection",
                ]
            )
            if stage in {"pre_contract", "pre_shipment", "ongoing"}:
                needs.extend(
                    [
                        "pre_shipment_working_capital",
                        "export_working_capital",
                        "trade_finance_working_capital",
                    ]
                )
            if stage == "post_shipment":
                needs.extend(
                    [
                        "post_shipment_receivables_financing",
                        "export_bill_negotiation",
                    ]
                )
            if "lc" in payment or "l/c" in payment or "letter of credit" in payment or "신용장" in payment:
                needs.append("export_letter_of_credit_advising")
            if transaction.company_size in {"sme", "mid_market"}:
                needs.append("export_support_program")
        else:
            needs.extend(
                [
                    "import_working_capital",
                    "supply_chain_payment_finance",
                ]
            )
            if (
                (transaction.advance_payment_percent or Decimal("0")) > 0
                or "advance" in payment
                or "선급" in payment
            ):
                needs.append("import_advance_payment_protection")
            if "lc" in payment or "l/c" in payment or "letter of credit" in payment or "신용장" in payment:
                needs.append("import_letter_of_credit")
            if (
                transaction.tenor_days not in (None, 0)
                or "usance" in payment
                or "deferred" in payment
                or "기한부" in payment
            ):
                needs.append("import_usance_financing")

        profiles.append(
            TradeFinanceNeedProfile(
                profile_id=f"PORTFOLIO-NEED-{transaction.transaction_id}",
                transaction_id=transaction.transaction_id,
                transaction_direction=transaction.transaction_type,
                transaction_stage=stage,
                declared_needs=list(dict.fromkeys(needs)),
                company_size=transaction.company_size,
                payment_method=transaction.payment_method,
                tenor_days=transaction.tenor_days,
                preferred_bank=transaction.preferred_bank,
                industry_tags=transaction.industry_tags,
                available_documents=transaction.available_documents,
            )
        )
    return profiles


def match_portfolio_products(
    case: UnifiedCopilotCase,
    *,
    registry_path: str | None = None,
) -> tuple[list[TradeFinanceNeedProfile], ProductMatchingResult]:
    profiles = infer_portfolio_need_profiles(case)
    return profiles, match_trade_finance_products(
        profiles,
        registry_path=registry_path,
    )
