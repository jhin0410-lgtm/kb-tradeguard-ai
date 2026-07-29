"""Deterministic transaction-to-financial-capacity assessment.

The module links one approved transaction to one reviewed financial-statement snapshot.
It calculates scale and liquidity measures and applies only governed structural review
triggers.  It does not estimate default probability, expected loss, lending approval,
insurance acceptance, or product suitability.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..advisor_models import CalculationResult
from ..advisor_tools import _calculation_result
from ..copilot_case import UnifiedCopilotCase
from ..trade_finance_domain import (
    FinancialStatementSnapshot,
    MaterialityMeasure,
    PaymentStructure,
    SourceReference,
    TradeRiskSignal,
)


class TransactionCapacityRule(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rule_id: str
    metric_name: str
    operator: Literal["greater_than"]
    threshold: Decimal
    severity: Literal["critical", "high", "medium", "low", "informational"]
    category: Literal["company_capacity", "liquidity", "concentration"]
    title: str
    failure_path: str
    unresolved_fact: str


class TransactionCapacityRuleRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    registry_name: str
    registry_version: str
    effective_date: date
    authority_boundary: str
    rules: list[TransactionCapacityRule]

    @model_validator(mode="after")
    def rule_ids_are_unique(self):
        identifiers = [item.rule_id for item in self.rules]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Transaction-capacity rule IDs must be unique")
        return self


class TransactionCapacityRequest(BaseModel):
    """Reviewed assumptions needed to assess one approved transaction."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    assessment_id: str
    transaction_id: str
    statement_id: str
    payment_structure_id: str | None = None
    protection_percent: Decimal | None = Field(default=None, ge=0, le=100)
    pre_shipment_funding_need_krw: Decimal | None = Field(default=None, ge=0)
    fx_rate_krw: Decimal | None = Field(default=None, gt=0)
    fx_rate_source: str | None = None

    @model_validator(mode="after")
    def override_rate_requires_source(self):
        if self.fx_rate_krw is not None and not self.fx_rate_source:
            raise ValueError("An explicit FX-rate override requires fx_rate_source")
        if self.fx_rate_krw is None and self.fx_rate_source:
            raise ValueError("fx_rate_source is valid only with an explicit FX-rate override")
        return self


class TransactionCapacityMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    metric_name: str
    value: Decimal | None
    unit: str
    formula: str
    interpretation: str
    available: bool


class TransactionCapacityAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: TransactionCapacityRequest
    calculation: CalculationResult
    metrics: list[TransactionCapacityMetric]
    risk_signals: list[TradeRiskSignal]
    missing_inputs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TransactionCapacityOutcome(BaseModel):
    case_before_hash: str
    case_after_hash: str
    assessment_id: str
    calculation_id: str
    risk_signal_ids: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)


def default_transaction_capacity_registry_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "reference"
        / "transaction_capacity_rules_v1.json"
    )


def load_transaction_capacity_registry(
    path: str | Path | None = None,
) -> TransactionCapacityRuleRegistry:
    registry_path = (
        Path(path) if path is not None else default_transaction_capacity_registry_path()
    )
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Unable to load transaction-capacity rule registry: {registry_path}"
        ) from exc
    return TransactionCapacityRuleRegistry.model_validate(payload)


def _registry_source(
    registry: TransactionCapacityRuleRegistry,
    path: Path,
) -> SourceReference:
    return SourceReference(
        source_id=f"TRANSACTION-CAPACITY-{registry.registry_version}",
        source_name=registry.registry_name,
        source_tier="derived",
        source_kind="project_rule",
        source_locator=path.as_posix(),
        as_of_date=registry.effective_date,
        content_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
        effective_date_verified=True,
    )


def _decimal(value: Any, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not parsed.is_finite():
        raise ValueError(f"{label} must be finite")
    return parsed


def _find_transaction(case: UnifiedCopilotCase, transaction_id: str) -> dict[str, Any]:
    matches = [
        item
        for item in case.approved_transactions
        if str(item.get("transaction_id")) == transaction_id
    ]
    if not matches:
        raise ValueError(f"Approved transaction not found: {transaction_id}")
    if len(matches) > 1:
        raise ValueError(f"Approved transaction ID is duplicated: {transaction_id}")
    transaction = matches[0]
    required = {"transaction_type", "currency", "amount_fc"}
    missing = sorted(key for key in required if transaction.get(key) in {None, ""})
    if missing:
        raise ValueError(
            "Approved transaction is missing capacity inputs: " + ", ".join(missing)
        )
    amount = _decimal(transaction["amount_fc"], "transaction amount_fc")
    if amount <= 0:
        raise ValueError("transaction amount_fc must be greater than zero")
    return transaction


def _find_statement(
    case: UnifiedCopilotCase, statement_id: str
) -> FinancialStatementSnapshot:
    matches = [
        item
        for item in case.trade_finance.financial_statements
        if item.statement_id == statement_id
    ]
    if not matches:
        raise ValueError(f"Financial statement snapshot not found: {statement_id}")
    if len(matches) > 1:
        raise ValueError(f"Financial statement snapshot ID is duplicated: {statement_id}")
    statement = matches[0]
    if statement.currency != "KRW":
        raise ValueError("Transaction-capacity assessment currently requires KRW statements")
    company_profile = case.trade_finance.company_profile
    if company_profile is None:
        raise ValueError(
            "A reviewed company profile is required to bind the financial statement to the case"
        )
    if statement.company_id != company_profile.company_id:
        raise ValueError("Financial statement company does not match the case company profile")
    return statement


def _find_payment_structure(
    case: UnifiedCopilotCase,
    request: TransactionCapacityRequest,
) -> PaymentStructure | None:
    if request.payment_structure_id:
        matches = [
            item
            for item in case.trade_finance.payment_structures
            if item.payment_structure_id == request.payment_structure_id
        ]
        if not matches:
            raise ValueError(
                f"Payment structure not found: {request.payment_structure_id}"
            )
        payment = matches[0]
        if payment.transaction_id != request.transaction_id:
            raise ValueError("Payment structure is linked to a different transaction")
        return payment

    matches = [
        item
        for item in case.trade_finance.payment_structures
        if item.transaction_id == request.transaction_id
    ]
    if len(matches) > 1:
        raise ValueError(
            "Multiple payment structures exist; payment_structure_id must be explicit"
        )
    return matches[0] if matches else None


def _official_fx_rate(case: UnifiedCopilotCase, currency: str) -> Decimal:
    if currency == "KRW":
        return Decimal("1")
    asset = case.official_fx_reference
    if (
        asset is None
        or asset.status not in {"available", "partial"}
        or asset.payload is None
    ):
        raise ValueError(
            f"A current available or partial FX reference is required for transaction currency {currency}"
        )
    payload: Any = asset.payload
    if isinstance(payload, dict):
        if currency in {str(key).upper() for key in payload}:
            for key, value in payload.items():
                if str(key).upper() == currency and isinstance(value, (int, float, str)):
                    return _decimal(value, f"{currency} FX rate")
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("FX reference payload must be a mapping or list")
    for row in payload:
        if not isinstance(row, dict):
            continue
        if str(row.get("currency") or "").upper() != currency:
            continue
        value = row.get("spot_rate_krw", row.get("rate"))
        if value is not None:
            return _decimal(value, f"{currency} FX rate")
    raise ValueError(f"FX reference contains no usable rate for {currency}")


def _scaled(statement: FinancialStatementSnapshot, field_name: str) -> Decimal | None:
    value = getattr(statement, field_name)
    if value is None:
        return None
    return Decimal(str(value)) * Decimal(str(statement.unit_multiplier))


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator * Decimal("100")


def _metric(
    name: str,
    value: Decimal | None,
    unit: str,
    formula: str,
    interpretation: str,
) -> TransactionCapacityMetric:
    return TransactionCapacityMetric(
        metric_name=name,
        value=value,
        unit=unit,
        formula=formula,
        interpretation=interpretation,
        available=value is not None,
    )


def _json_value(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def analyze_transaction_capacity(
    case: UnifiedCopilotCase,
    request: TransactionCapacityRequest,
    *,
    registry_path: str | Path | None = None,
) -> TransactionCapacityAnalysis:
    """Calculate transaction scale and apply governed structural review triggers."""

    transaction = _find_transaction(case, request.transaction_id)
    statement = _find_statement(case, request.statement_id)
    payment = _find_payment_structure(case, request)
    currency = str(transaction["currency"]).upper()
    amount_fc = _decimal(transaction["amount_fc"], "transaction amount_fc")
    if amount_fc <= 0:
        raise ValueError("transaction amount_fc must be greater than zero")
    fx_rate = (
        Decimal(str(request.fx_rate_krw))
        if request.fx_rate_krw is not None
        else _official_fx_rate(case, currency)
    )
    if fx_rate <= 0:
        raise ValueError("FX rate must be greater than zero")
    gross_transaction_krw = amount_fc * fx_rate

    cash = _scaled(statement, "cash_and_cash_equivalents")
    short_term_assets = _scaled(statement, "short_term_financial_assets")
    liquid_assets = None
    if cash is not None:
        liquid_assets = cash + (short_term_assets or Decimal("0"))
    current_assets = _scaled(statement, "current_assets")
    equity = _scaled(statement, "equity")
    revenue = _scaled(statement, "revenue") if statement.report_type == "annual" else None

    deferred_percent = payment.deferred_payment_percent if payment is not None else None
    deferred_trade_amount = (
        gross_transaction_krw * Decimal(str(deferred_percent)) / Decimal("100")
        if deferred_percent is not None
        else None
    )
    unprotected_exposure = (
        deferred_trade_amount
        * (Decimal("100") - Decimal(str(request.protection_percent)))
        / Decimal("100")
        if deferred_trade_amount is not None and request.protection_percent is not None
        else None
    )
    funding_need = (
        Decimal(str(request.pre_shipment_funding_need_krw))
        if request.pre_shipment_funding_need_krw is not None
        else None
    )
    post_funding_liquidity = (
        liquid_assets - funding_need
        if liquid_assets is not None and funding_need is not None
        else None
    )

    values: dict[str, Decimal | None] = {
        "gross_transaction_krw": gross_transaction_krw,
        "identified_liquid_assets_krw": liquid_assets,
        "deferred_trade_amount_krw": deferred_trade_amount,
        "unprotected_exposure_krw": unprotected_exposure,
        "pre_shipment_funding_need_krw": funding_need,
        "post_funding_liquidity_krw": post_funding_liquidity,
        "gross_transaction_to_cash_pct": _ratio(gross_transaction_krw, cash),
        "gross_transaction_to_liquid_assets_pct": _ratio(
            gross_transaction_krw, liquid_assets
        ),
        "gross_transaction_to_current_assets_pct": _ratio(
            gross_transaction_krw, current_assets
        ),
        "gross_transaction_to_equity_pct": _ratio(gross_transaction_krw, equity),
        "gross_transaction_to_revenue_pct": _ratio(gross_transaction_krw, revenue),
        "deferred_trade_amount_to_cash_pct": _ratio(deferred_trade_amount, cash),
        "unprotected_exposure_to_cash_pct": _ratio(unprotected_exposure, cash),
        "unprotected_exposure_to_equity_pct": _ratio(unprotected_exposure, equity),
        "funding_need_to_liquid_assets_pct": _ratio(funding_need, liquid_assets),
    }

    metrics = [
        _metric(
            "gross_transaction_krw",
            values["gross_transaction_krw"],
            "KRW",
            "approved amount_fc × reviewed KRW FX rate",
            "계약의 원화환산 총액이며 예상손실이 아닙니다.",
        ),
        _metric(
            "identified_liquid_assets_krw",
            values["identified_liquid_assets_krw"],
            "KRW",
            "cash_and_cash_equivalents + available short_term_financial_assets",
            "최근 공시에서 식별된 유동성 자원이며 실제 인출가능액과 다를 수 있습니다.",
        ),
        _metric(
            "deferred_trade_amount_krw",
            values["deferred_trade_amount_krw"],
            "KRW",
            "gross_transaction_krw × reviewed deferred_payment_percent",
            "후불 결제부분의 총액이며 미회수확률이나 예상손실이 아닙니다.",
        ),
        _metric(
            "unprotected_exposure_krw",
            values["unprotected_exposure_krw"],
            "KRW",
            "deferred_trade_amount_krw × (1 - explicit protection_percent)",
            "명시된 보호비율만 반영한 잔여노출로 실제 보상가능액과 동일하지 않습니다.",
        ),
        _metric(
            "pre_shipment_funding_need_krw",
            values["pre_shipment_funding_need_krw"],
            "KRW",
            "explicit reviewed funding need",
            "사용자가 검토해 입력한 거래 준비자금입니다.",
        ),
        _metric(
            "post_funding_liquidity_krw",
            values["post_funding_liquidity_krw"],
            "KRW",
            "identified_liquid_assets_krw - pre_shipment_funding_need_krw",
            "다른 현금흐름과 가용한도를 제외한 단순 잔액입니다.",
        ),
    ]
    ratio_labels = {
        "gross_transaction_to_cash_pct": (
            "gross_transaction_krw / cash_and_cash_equivalents × 100",
            "단일 거래 총액과 최근 현금성자산의 규모 비교입니다.",
        ),
        "gross_transaction_to_liquid_assets_pct": (
            "gross_transaction_krw / identified_liquid_assets_krw × 100",
            "단일 거래 총액과 식별된 유동성 자원의 규모 비교입니다.",
        ),
        "gross_transaction_to_current_assets_pct": (
            "gross_transaction_krw / current_assets × 100",
            "단일 거래 총액과 최근 유동자산의 규모 비교입니다.",
        ),
        "gross_transaction_to_equity_pct": (
            "gross_transaction_krw / equity × 100",
            "단일 거래 총액과 최근 자기자본의 규모 비교이며 손실률이 아닙니다.",
        ),
        "gross_transaction_to_revenue_pct": (
            "gross_transaction_krw / annual revenue × 100",
            "단일 거래 총액과 최근 연간 매출의 규모 비교입니다.",
        ),
        "deferred_trade_amount_to_cash_pct": (
            "deferred_trade_amount_krw / cash_and_cash_equivalents × 100",
            "후불 결제금액과 현금성자산의 규모 비교입니다.",
        ),
        "unprotected_exposure_to_cash_pct": (
            "unprotected_exposure_krw / cash_and_cash_equivalents × 100",
            "명시적 보호 후 잔여노출과 현금성자산의 규모 비교입니다.",
        ),
        "unprotected_exposure_to_equity_pct": (
            "unprotected_exposure_krw / equity × 100",
            "명시적 보호 후 잔여노출과 자기자본의 규모 비교입니다.",
        ),
        "funding_need_to_liquid_assets_pct": (
            "pre_shipment_funding_need_krw / identified_liquid_assets_krw × 100",
            "거래 준비자금과 식별된 유동성 자원의 규모 비교입니다.",
        ),
    }
    metrics.extend(
        _metric(name, values[name], "%", formula, interpretation)
        for name, (formula, interpretation) in ratio_labels.items()
    )

    missing_inputs: list[str] = []
    limitations = [
        "Financial values are issuer-filed public statement amounts and may be stale, restated, consolidated, or unavailable.",
        "Gross transaction value and residual exposure are not expected-loss estimates.",
        "No unreported bank limits, pledged cash, restricted deposits, other transactions, taxes, or operating cash flows are inferred.",
    ]
    if cash is None:
        missing_inputs.append("cash_and_cash_equivalents")
    if cash is not None and short_term_assets is None:
        limitations.append(
            "Short-term financial assets were unavailable; identified liquid assets use cash only and may be a lower bound."
        )
    if payment is None or deferred_percent is None:
        missing_inputs.append("reviewed deferred_payment_percent")
    if request.protection_percent is None:
        missing_inputs.append("explicit effective protection_percent")
    if request.pre_shipment_funding_need_krw is None:
        missing_inputs.append("reviewed pre_shipment_funding_need_krw")
    if statement.report_type != "annual":
        missing_inputs.append("annual revenue snapshot for concentration comparison")
    for field_name, value in (
        ("current_assets", current_assets),
        ("equity", equity),
    ):
        if value is None or value <= 0:
            missing_inputs.append(field_name)

    calculation = _calculation_result(
        "Transaction financial capacity assessment",
        {
            "assessment_id": request.assessment_id,
            "transaction_id": request.transaction_id,
            "statement_id": request.statement_id,
            "statement_snapshot": statement.model_dump(mode="json"),
            "payment_structure_id": (
                payment.payment_structure_id if payment is not None else None
            ),
            "transaction_currency": currency,
            "amount_fc": _json_value(amount_fc),
            "fx_rate_krw": _json_value(fx_rate),
            "fx_rate_source": (
                request.fx_rate_source
                if request.fx_rate_krw is not None
                else (
                    "KRW identity rate"
                    if currency == "KRW"
                    else case.official_fx_reference.source
                )
            ),
            "protection_percent": _json_value(request.protection_percent),
            "pre_shipment_funding_need_krw": _json_value(
                request.pre_shipment_funding_need_krw
            ),
            "analysis_basis": "gross transaction scale and explicit residual exposure",
        },
        {
            "metrics": {name: _json_value(value) for name, value in values.items()},
            "missing_inputs": list(dict.fromkeys(missing_inputs)),
            "statement_period_end": statement.period_end.isoformat(),
            "statement_scope": statement.consolidation_scope,
            "statement_record_status": statement.record_status,
        },
        "mixed KRW and percent",
        (
            case.identity.analysis_as_of_date.isoformat()
            if case.identity.analysis_as_of_date
            else statement.period_end.isoformat()
        ),
        (
            f"approved transaction {request.transaction_id}; financial statement "
            f"{statement.statement_id}; reviewed FX input"
        ),
        limitations + list(statement.limitations),
    )

    resolved_path = (
        Path(registry_path)
        if registry_path is not None
        else default_transaction_capacity_registry_path()
    )
    registry = load_transaction_capacity_registry(resolved_path)
    source = _registry_source(registry, resolved_path)
    signals: list[TradeRiskSignal] = []
    for rule in registry.rules:
        value = values.get(rule.metric_name)
        if value is None:
            continue
        if rule.operator == "greater_than" and value <= rule.threshold:
            continue
        signals.append(
            TradeRiskSignal(
                signal_id=(
                    f"RISK-CAPACITY-{rule.rule_id}-{request.assessment_id}"
                ),
                category=rule.category,
                severity=rule.severity,
                title=rule.title,
                factual_trigger=(
                    f"{rule.metric_name}={value.quantize(Decimal('0.01'))}% > "
                    f"{rule.threshold}%"
                ),
                authority_type="screening_flag",
                affected_transaction_ids=[request.transaction_id],
                materiality=[
                    MaterialityMeasure(
                        metric_name=rule.metric_name,
                        value=value,
                        unit="%",
                        comparator=rule.operator,
                        threshold=rule.threshold,
                        calculation_id=calculation.calculation_id,
                    )
                ],
                calculation_ids=[calculation.calculation_id],
                mitigating_facts=(
                    [
                        f"Explicit reviewed protection_percent={request.protection_percent}% was applied."
                    ]
                    if request.protection_percent is not None
                    else []
                ),
                unresolved_facts=[rule.unresolved_fact],
                source=source,
                record_status=(
                    "verified" if statement.record_status == "verified" else "partial"
                ),
                limitations=[
                    registry.authority_boundary,
                    "The trigger compares disclosed amounts and does not predict loss, default, or approval.",
                    *limitations,
                ],
            )
        )

    return TransactionCapacityAnalysis(
        request=request,
        calculation=calculation,
        metrics=metrics,
        risk_signals=signals,
        missing_inputs=list(dict.fromkeys(missing_inputs)),
        limitations=limitations,
    )


def apply_transaction_capacity_assessment(
    case: UnifiedCopilotCase,
    request: TransactionCapacityRequest,
    *,
    registry_path: str | Path | None = None,
) -> tuple[UnifiedCopilotCase, TransactionCapacityOutcome]:
    """Attach the current capacity calculation and replace stale signals for the transaction."""

    analysis = analyze_transaction_capacity(
        case,
        request,
        registry_path=registry_path,
    )
    calculation = analysis.calculation
    existing_calculation = case.calculations.get(calculation.calculation_id)
    if (
        existing_calculation is not None
        and existing_calculation.normalized_input_hash == calculation.normalized_input_hash
        and existing_calculation.result == calculation.result
    ):
        calculation = existing_calculation

    resolved_path = (
        Path(registry_path)
        if registry_path is not None
        else default_transaction_capacity_registry_path()
    )
    registry = load_transaction_capacity_registry(resolved_path)
    source_id = _registry_source(registry, resolved_path).source_id
    retained_signals = [
        item
        for item in case.trade_finance.risk_signals
        if not (
            item.source.source_id == source_id
            and request.transaction_id in item.affected_transaction_ids
        )
    ]
    updated_domain = case.trade_finance.model_copy(
        update={"risk_signals": retained_signals + analysis.risk_signals}
    )
    calculations = dict(case.calculations)
    calculations[calculation.calculation_id] = calculation
    updated_case = case.model_copy(
        update={
            "trade_finance": updated_domain,
            "calculations": calculations,
        }
    )
    outcome = TransactionCapacityOutcome(
        case_before_hash=case.case_hash,
        case_after_hash=updated_case.case_hash,
        assessment_id=request.assessment_id,
        calculation_id=calculation.calculation_id,
        risk_signal_ids=[item.signal_id for item in analysis.risk_signals],
        missing_inputs=analysis.missing_inputs,
    )
    return updated_case, outcome
