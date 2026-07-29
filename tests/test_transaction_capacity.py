from datetime import date
from decimal import Decimal

import pytest

from src.copilot_case import CaseDataAsset, CaseIdentity, UnifiedCopilotCase
from src.intelligence.transaction_capacity import (
    TransactionCapacityRequest,
    analyze_transaction_capacity,
    apply_transaction_capacity_assessment,
    load_transaction_capacity_registry,
)
from src.trade_finance_domain import (
    CompanyProfile,
    FinancialStatementSnapshot,
    PaymentStructure,
    SourceReference,
    TradeFinanceDomainState,
)


def _source(source_id, source_kind="official_api"):
    return SourceReference(
        source_id=source_id,
        source_name="Reviewed synthetic source",
        source_tier="tier_1" if source_kind == "official_api" else "user_provided",
        source_kind=source_kind,
        source_locator=f"fixture://{source_id}",
        as_of_date=date(2025, 12, 31),
        effective_date_verified=True,
    )


def _statement(**updates):
    payload = {
        "statement_id": "FS-2025-CFS",
        "company_id": "COMPANY-001",
        "period_start": date(2025, 1, 1),
        "period_end": date(2025, 12, 31),
        "report_type": "annual",
        "consolidation_scope": "consolidated",
        "currency": "KRW",
        "cash_and_cash_equivalents": Decimal("300000000"),
        "short_term_financial_assets": Decimal("100000000"),
        "current_assets": Decimal("1000000000"),
        "current_liabilities": Decimal("600000000"),
        "equity": Decimal("500000000"),
        "revenue": Decimal("5000000000"),
        "operating_cash_flow": Decimal("180000000"),
        "source": _source("SRC-FS"),
        "record_status": "verified",
    }
    payload.update(updates)
    return FinancialStatementSnapshot(**payload)


def _case(statement=None, payment=True):
    company = CompanyProfile(
        company_id="COMPANY-001",
        legal_name="Example Exporter Co., Ltd.",
        business_registration_number="1234567890",
        sme_status="confirmed",
        source=_source("SRC-COMPANY"),
        record_status="verified",
    )
    payments = []
    if payment:
        payments.append(
            PaymentStructure(
                payment_structure_id="PAY-EXP-001",
                transaction_id="EXP-001",
                method="open_account",
                tenor_days=90,
                deferred_payment_percent=Decimal("100"),
                payment_trigger="90 days after shipment",
                source=_source("SRC-PAY", source_kind="user_document"),
                record_status="verified",
            )
        )
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-CAPACITY",
            company_name="Example Exporter Co., Ltd.",
            analysis_as_of_date=date(2026, 7, 26),
        ),
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "expected_date": "2026-10-31",
            }
        ],
        official_fx_reference=CaseDataAsset(
            asset_name="official FX reference",
            status="available",
            source="test FX fixture",
            as_of_date=date(2026, 7, 26),
            payload=[{"currency": "USD", "spot_rate_krw": 1350}],
        ),
        trade_finance=TradeFinanceDomainState(
            company_profile=company,
            financial_statements=[statement or _statement()],
            payment_structures=payments,
        ),
    )


def _request(**updates):
    payload = {
        "assessment_id": "CAPACITY-EXP-001",
        "transaction_id": "EXP-001",
        "statement_id": "FS-2025-CFS",
        "payment_structure_id": "PAY-EXP-001",
        "protection_percent": Decimal("80"),
        "pre_shipment_funding_need_krw": Decimal("450000000"),
    }
    payload.update(updates)
    return TransactionCapacityRequest(**payload)


def _metrics(analysis):
    return {item.metric_name: item for item in analysis.metrics}


def test_capacity_registry_uses_structural_review_triggers_not_credit_claims():
    registry = load_transaction_capacity_registry()

    assert registry.registry_version == "transaction-capacity-rules/1.0"
    assert len(registry.rules) == 5
    assert len({item.rule_id for item in registry.rules}) == len(registry.rules)
    assert "not bank credit standards" in registry.authority_boundary


def test_transaction_amount_and_explicit_residual_exposure_are_calculated():
    analysis = analyze_transaction_capacity(_case(), _request())
    metrics = _metrics(analysis)

    assert metrics["gross_transaction_krw"].value == Decimal("675000000")
    assert metrics["identified_liquid_assets_krw"].value == Decimal("400000000")
    assert metrics["deferred_trade_amount_krw"].value == Decimal("675000000")
    assert metrics["unprotected_exposure_krw"].value == Decimal("135000000")
    assert metrics["gross_transaction_to_cash_pct"].value == Decimal("225.00")
    assert metrics["unprotected_exposure_to_cash_pct"].value == Decimal("45.00")
    assert metrics["funding_need_to_liquid_assets_pct"].value == Decimal("112.500")
    assert metrics["post_funding_liquidity_krw"].value == Decimal("-50000000")
    assert analysis.calculation.calculation_id.startswith("CALC-")


def test_funding_need_above_identified_liquidity_creates_grounded_signal():
    analysis = analyze_transaction_capacity(_case(), _request())

    assert len(analysis.risk_signals) == 1
    signal = analysis.risk_signals[0]
    assert "FUNDING-NEED-EXCEEDS-LIQUID-ASSETS" in signal.signal_id
    assert signal.category == "liquidity"
    assert signal.severity == "high"
    assert signal.calculation_ids == [analysis.calculation.calculation_id]
    assert signal.materiality[0].threshold == Decimal("100")
    assert signal.materiality[0].value == Decimal("112.500")


def test_zero_protection_can_trigger_cash_and_equity_capacity_reviews():
    analysis = analyze_transaction_capacity(
        _case(),
        _request(
            protection_percent=Decimal("0"),
            pre_shipment_funding_need_krw=Decimal("100000000"),
        ),
    )
    ids = {item.signal_id for item in analysis.risk_signals}

    assert any("UNPROTECTED-EXPOSURE-EXCEEDS-CASH" in item for item in ids)
    assert any("UNPROTECTED-EXPOSURE-EXCEEDS-EQUITY" in item for item in ids)
    assert not any("FUNDING-NEED-EXCEEDS-LIQUID-ASSETS" in item for item in ids)
    assert all("expected-loss" in item.limitations[1] or "predict" in item.limitations[1] for item in analysis.risk_signals)


def test_missing_protection_and_payment_terms_remain_missing_not_assumed():
    case = _case(payment=False)
    request = _request(
        payment_structure_id=None,
        protection_percent=None,
        pre_shipment_funding_need_krw=None,
    )
    analysis = analyze_transaction_capacity(case, request)
    metrics = _metrics(analysis)

    assert metrics["deferred_trade_amount_krw"].value is None
    assert metrics["unprotected_exposure_krw"].value is None
    assert "reviewed deferred_payment_percent" in analysis.missing_inputs
    assert "explicit effective protection_percent" in analysis.missing_inputs
    assert analysis.risk_signals == []


def test_nonannual_revenue_is_not_used_as_annual_concentration_denominator():
    statement = _statement(
        report_type="semiannual",
        period_end=date(2025, 6, 30),
        revenue=Decimal("2500000000"),
    )
    analysis = analyze_transaction_capacity(_case(statement=statement), _request())

    assert _metrics(analysis)["gross_transaction_to_revenue_pct"].value is None
    assert "annual revenue snapshot for concentration comparison" in analysis.missing_inputs


def test_explicit_fx_override_requires_source_and_is_preserved():
    with pytest.raises(ValueError, match="requires fx_rate_source"):
        _request(fx_rate_krw=Decimal("1400"))

    request = _request(
        fx_rate_krw=Decimal("1400"),
        fx_rate_source="Reviewed bank reference for sensitivity analysis",
    )
    analysis = analyze_transaction_capacity(_case(), request)

    assert _metrics(analysis)["gross_transaction_krw"].value == Decimal("700000000")
    assert analysis.calculation.input_assumptions["fx_rate_source"] == (
        "Reviewed bank reference for sensitivity analysis"
    )


def test_case_application_is_immutable_and_idempotent_for_same_inputs():
    case = _case()
    before = case.case_hash

    first, first_outcome = apply_transaction_capacity_assessment(case, _request())
    second, second_outcome = apply_transaction_capacity_assessment(first, _request())

    assert case.calculations == {}
    assert case.trade_finance.risk_signals == []
    assert case.case_hash == before
    assert first.case_hash != before
    assert second.case_hash == first.case_hash
    assert second_outcome.calculation_id == first_outcome.calculation_id
    assert second_outcome.risk_signal_ids == first_outcome.risk_signal_ids
    assert len(second.trade_finance.risk_signals) == 1


def test_reassessment_replaces_stale_capacity_signal_but_keeps_audit_calculation():
    first, first_outcome = apply_transaction_capacity_assessment(_case(), _request())
    reduced_request = _request(
        pre_shipment_funding_need_krw=Decimal("100000000"),
    )
    second, second_outcome = apply_transaction_capacity_assessment(first, reduced_request)

    assert first_outcome.risk_signal_ids
    assert second_outcome.risk_signal_ids == []
    assert not any(
        item.source.source_id.startswith("TRANSACTION-CAPACITY-")
        for item in second.trade_finance.risk_signals
    )
    assert first_outcome.calculation_id in second.calculations
    assert second_outcome.calculation_id in second.calculations


def test_unknown_transaction_statement_and_direction_inputs_are_rejected():
    with pytest.raises(ValueError, match="Approved transaction not found"):
        analyze_transaction_capacity(
            _case(), _request(transaction_id="EXP-UNKNOWN")
        )
    with pytest.raises(ValueError, match="snapshot not found"):
        analyze_transaction_capacity(
            _case(), _request(statement_id="FS-UNKNOWN")
        )

    wrong_statement = _statement(company_id="COMPANY-OTHER")
    with pytest.raises(ValueError, match="does not match"):
        analyze_transaction_capacity(
            _case(statement=wrong_statement), _request()
        )
