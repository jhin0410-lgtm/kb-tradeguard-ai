from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.trade_finance_domain import (
    ActionPlanItem,
    CompanyProfile,
    ComplianceMatch,
    ComplianceScreeningResult,
    ContractClauseFinding,
    CountryRiskFact,
    CounterpartyProfile,
    FinancialStatementSnapshot,
    PaymentStructure,
    ProductCandidate,
    SourceReference,
    TradeDocumentProfile,
    TradeFinanceDomainState,
    TradeRiskSignal,
)


def _source(
    source_id: str = "SRC-001",
    *,
    kind: str = "official_api",
    tier: str = "tier_1",
) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_name="Synthetic official-source fixture",
        source_tier=tier,
        source_kind=kind,
        source_locator="fixture://official/source",
        as_of_date=date(2026, 7, 26),
        retrieved_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
        content_hash="abc123",
        effective_date_verified=True,
    )


def test_company_and_financial_snapshot_normalize_codes_and_retain_provenance():
    company = CompanyProfile(
        company_id="COMP-001",
        legal_name="한빛테크",
        country_code="kr",
        source=_source("SRC-COMPANY", kind="user_document", tier="user_provided"),
        record_status="verified",
    )
    statement = FinancialStatementSnapshot(
        statement_id="FS-2025-A",
        company_id=company.company_id,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        report_type="annual",
        consolidation_scope="consolidated",
        currency="krw",
        unit_multiplier=Decimal("1000"),
        cash_and_cash_equivalents=Decimal("2100000"),
        current_assets=Decimal("8800000"),
        current_liabilities=Decimal("5200000"),
        short_term_borrowings=Decimal("540000"),
        equity=Decimal("3400000"),
        source=_source("SRC-OPENDART"),
        record_status="verified",
        limitations=["재무건전성 사전 스크리닝이며 공식 신용등급이 아닙니다."],
    )

    assert company.country_code == "KR"
    assert statement.currency == "KRW"
    assert statement.source.source_id == "SRC-OPENDART"
    assert statement.limitations


def test_financial_statement_rejects_reversed_period():
    with pytest.raises(ValidationError, match="period_start"):
        FinancialStatementSnapshot(
            statement_id="FS-BAD",
            company_id="COMP-001",
            period_start=date(2026, 1, 1),
            period_end=date(2025, 12, 31),
            report_type="annual",
            source=_source(),
        )


def test_confirmed_compliance_match_requires_entry_and_human_review():
    with pytest.raises(ValidationError, match="matched entry"):
        ComplianceScreeningResult(
            screening_id="SCR-001",
            subject_type="counterparty",
            subject_name="Example Buyer",
            screening_type="sanctions",
            result="potential_match",
            method="configured_fuzzy",
            source=_source("SRC-SANCTIONS"),
        )

    with pytest.raises(ValidationError, match="human review"):
        ComplianceScreeningResult(
            screening_id="SCR-002",
            subject_type="counterparty",
            subject_name="Example Buyer",
            screening_type="sanctions",
            result="confirmed_match",
            method="manual",
            matched_entries=[
                ComplianceMatch(
                    matched_name="Example Buyer",
                    list_name="Synthetic sanctions fixture",
                    match_score=Decimal("1"),
                )
            ],
            source=_source("SRC-SANCTIONS"),
        )


def test_payment_structure_rejects_percentages_over_one_hundred():
    with pytest.raises(ValidationError, match="must not exceed 100"):
        PaymentStructure(
            payment_structure_id="PAY-001",
            transaction_id="EXP-001",
            method="open_account",
            advance_payment_percent=Decimal("30"),
            deferred_payment_percent=Decimal("80"),
            source=_source("SRC-CONTRACT", kind="user_document", tier="user_provided"),
        )


def test_clause_finding_and_material_risk_signal_require_grounding():
    with pytest.raises(ValidationError, match="must reference evidence"):
        ContractClauseFinding(
            clause_finding_id="CLAUSE-001",
            document_id="DOC-001",
            evidence_ids=[],
            clause_locator="Clause 8.2",
            clause_excerpt="Payment after buyer acceptance.",
            issue_type="buyer_controlled_condition",
            severity="high",
            failure_path="The buyer can delay acceptance without a defined deadline.",
            suggested_clarification_or_revision="Add an objective acceptance period.",
            source=_source("SRC-RULE", kind="project_rule", tier="derived"),
        )

    with pytest.raises(ValidationError, match="must reference evidence or calculations"):
        TradeRiskSignal(
            signal_id="RISK-001",
            category="payment_instrument",
            severity="high",
            title="Buyer-controlled payment trigger",
            factual_trigger="Payment depends on undefined buyer acceptance.",
            source=_source("SRC-RULE", kind="project_rule", tier="derived"),
        )


def test_consultation_product_candidate_requires_official_source():
    with pytest.raises(ValidationError, match="official source"):
        ProductCandidate(
            product_candidate_id="PROD-001",
            provider="K-SURE",
            product_or_service_name="Synthetic export insurance candidate",
            product_category="trade_credit_insurance",
            matched_need="Open-account non-payment risk",
            candidate_status="consultation_candidate",
            next_action="Confirm current public conditions with K-SURE.",
            source=_source(
                "SRC-PRODUCT-REGISTRY",
                kind="project_rule",
                tier="derived",
            ),
        )


def test_domain_state_rejects_duplicate_record_ids_and_action_sequences():
    buyer = CounterpartyProfile(
        counterparty_id="BUYER-001",
        legal_name="Example Buyer Co.",
        country_code="vn",
        source=_source("SRC-BUYER", kind="user_document", tier="user_provided"),
    )

    with pytest.raises(ValidationError, match="Duplicate counterparty_id"):
        TradeFinanceDomainState(counterparties=[buyer, buyer.model_copy()])

    action_one = ActionPlanItem(
        action_id="ACT-001",
        sequence=1,
        title="Verify buyer identity",
        rationale="Buyer identity is not yet independently verified.",
        responsible_party="customer",
        source=_source("SRC-ACTION", kind="derived_calculation", tier="derived"),
    )
    action_two = ActionPlanItem(
        action_id="ACT-002",
        sequence=1,
        title="Request professional credit investigation",
        rationale="Public information is insufficient for buyer credit quality.",
        responsible_party="customer",
        source=_source("SRC-ACTION", kind="derived_calculation", tier="derived"),
    )

    with pytest.raises(ValidationError, match="sequence values must be unique"):
        TradeFinanceDomainState(action_plan=[action_one, action_two])


def test_typed_reference_case_serializes_without_claiming_approval():
    company = CompanyProfile(
        company_id="COMP-001",
        legal_name="한빛테크",
        source=_source("SRC-COMPANY", kind="user_document", tier="user_provided"),
        record_status="verified",
    )
    buyer = CounterpartyProfile(
        counterparty_id="BUYER-001",
        legal_name="Vietnam Example Buyer Co.",
        country_code="VN",
        relationship_status="new",
        due_diligence_status="professional_credit_investigation_required",
        source=_source("SRC-BUYER", kind="user_document", tier="user_provided"),
        record_status="partial",
    )
    country_fact = CountryRiskFact(
        fact_id="COUNTRY-VN-001",
        country_code="VN",
        dimension="sovereign_transfer",
        metric_name="synthetic transfer-risk observation",
        value="additional review required",
        risk_direction="categorical",
        interpretation="This fixture demonstrates a sourced country-risk fact.",
        source=_source("SRC-COUNTRY"),
        record_status="verified",
    )
    payment = PaymentStructure(
        payment_structure_id="PAY-001",
        transaction_id="EXP-001",
        method="open_account",
        tenor_days=90,
        deferred_payment_percent=Decimal("100"),
        payment_trigger="90 days after shipment",
        source=_source("SRC-CONTRACT", kind="user_document", tier="user_provided"),
        record_status="verified",
    )
    document = TradeDocumentProfile(
        document_id="DOC-001",
        evidence_id="EVID-001",
        document_type="contract",
        currency="USD",
        amount=Decimal("500000"),
        payment_structure_id=payment.payment_structure_id,
        linked_transaction_ids=["EXP-001"],
        source=_source("SRC-CONTRACT", kind="user_document", tier="user_provided"),
        record_status="verified",
    )
    risk = TradeRiskSignal(
        signal_id="RISK-001",
        category="counterparty",
        severity="high",
        title="Professional buyer due diligence is required",
        factual_trigger="The buyer is new and verified credit information is unavailable.",
        affected_transaction_ids=["EXP-001"],
        evidence_ids=["EVID-001"],
        country_fact_ids=[country_fact.fact_id],
        unresolved_facts=["Professional buyer credit report"],
        source=_source("SRC-RULE", kind="project_rule", tier="derived"),
        record_status="verified",
    )
    candidate = ProductCandidate(
        product_candidate_id="PROD-001",
        provider="K-SURE",
        product_or_service_name="Buyer credit investigation consultation candidate",
        product_category="buyer_credit_investigation",
        matched_need="Buyer credit information is incomplete",
        candidate_status="consultation_candidate",
        match_reasons=["New overseas buyer"],
        unresolved_eligibility_conditions=["Current service conditions must be verified"],
        official_source_ids=["KSURE-OFFICIAL-001"],
        next_action="Check current K-SURE service availability and required documents.",
        source=_source(
            "SRC-PRODUCT-REGISTRY",
            kind="institution_product_disclosure",
            tier="tier_1",
        ),
        record_status="verified",
    )

    state = TradeFinanceDomainState(
        company_profile=company,
        counterparties=[buyer],
        country_risk_facts=[country_fact],
        payment_structures=[payment],
        trade_documents=[document],
        risk_signals=[risk],
        product_candidates=[candidate],
    )
    payload = state.model_dump(mode="json")

    assert payload["domain_version"] == "trade-finance-domain/1.0"
    assert payload["counterparties"][0]["country_code"] == "VN"
    assert payload["product_candidates"][0]["candidate_status"] == "consultation_candidate"
    assert state.record_counts()["risk_signals"] == 1
