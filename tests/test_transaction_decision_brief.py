from datetime import date
from decimal import Decimal

import pytest

from src.advisor_tools import _calculation_result
from src.copilot_case import CaseEvidenceItem, CaseIdentity, UnifiedCopilotCase
from src.intelligence.product_matching import (
    TradeFinanceNeedProfile,
    match_trade_finance_products,
)
from src.intelligence.transaction_decision_brief import (
    TransactionDecisionBriefRequest,
    apply_transaction_decision_brief,
    build_transaction_decision_brief,
    load_transaction_decision_brief_registry,
)
from src.trade_finance_domain import (
    ComplianceMatch,
    ComplianceScreeningResult,
    CounterpartyProfile,
    CountryRiskFact,
    PaymentStructure,
    SourceReference,
    TradeDocumentProfile,
    TradeFinanceDomainState,
    TradeRiskSignal,
)


def _source(source_id, kind="project_rule", tier="derived"):
    return SourceReference(
        source_id=source_id,
        source_name=f"Source {source_id}",
        source_tier=tier,
        source_kind=kind,
        source_locator=f"fixture://{source_id}",
        as_of_date=date(2026, 7, 26),
        effective_date_verified=True,
    )


def _calculation(transaction_id="EXP-001"):
    return _calculation_result(
        "Transaction financial capacity assessment",
        {
            "transaction_id": transaction_id,
            "statement_id": "FS-2025",
            "analysis_basis": "test capacity basis",
        },
        {"metrics": {"funding_need_to_liquid_assets_pct": 112.5}},
        "mixed KRW and percent",
        "2026-07-26",
        "test transaction and financial statement",
        ["Test fixture only."],
    )


def _product_result():
    profile = TradeFinanceNeedProfile(
        profile_id="NEED-EXP-001",
        transaction_id="EXP-001",
        transaction_direction="export",
        transaction_stage="pre_shipment",
        declared_needs=["buyer_credit_investigation", "pre_shipment_working_capital"],
        company_size="sme",
        tenor_days=90,
        preferred_bank="KB국민은행",
        available_documents=["수출계약 또는 발주서"],
    )
    return match_trade_finance_products([profile])


def _case(
    *,
    include_high_signals=True,
    counterparty_status="professional_credit_investigation_required",
    screening_result="clear",
    screening_type="sanctions",
    include_country=True,
    include_payment=True,
    include_document=True,
    include_calculation=True,
    include_products=True,
):
    counterparty = CounterpartyProfile(
        counterparty_id="BUYER-001",
        legal_name="Vietnam Buyer Co., Ltd.",
        country_code="VN",
        registration_number="VN-REG-001",
        relationship_status="new",
        due_diligence_status=counterparty_status,
        prior_payment_history="none",
        source=_source("SRC-BUYER", "user_document", "user_provided"),
        record_status="verified",
    )
    country_facts = []
    if include_country:
        country_facts = [
            CountryRiskFact(
                fact_id="COUNTRY-VN-GDP",
                country_code="VN",
                dimension="macroeconomic",
                metric_name="GDP growth",
                value=Decimal("7.09"),
                unit="% annual growth",
                observation_date=date(2024, 12, 31),
                risk_direction="lower_is_worse",
                interpretation="Macroeconomic context only.",
                source=_source("SRC-WB", "official_api", "tier_1"),
                record_status="verified",
            ),
            CountryRiskFact(
                fact_id="COUNTRY-VN-FATF",
                country_code="VN",
                dimension="sanctions_aml",
                metric_name="FATF public-list status",
                value="increased_monitoring",
                observation_date=date(2026, 6, 19),
                risk_direction="categorical",
                interpretation="AML/CFT context flag, not a prohibition.",
                source=_source("SRC-FATF", "official_publication", "tier_1"),
                record_status="verified",
            ),
        ]
    matched_entries = []
    if screening_result in {"potential_match", "confirmed_match"}:
        matched_entries = [
            ComplianceMatch(
                matched_name=counterparty.legal_name,
                list_name="Synthetic sanctions list",
                match_score=Decimal("1"),
                identifiers={"registration_number": counterparty.registration_number},
            )
        ]
    screenings = [
        ComplianceScreeningResult(
            screening_id="SCREEN-BUYER-001",
            subject_type="counterparty",
            subject_id=counterparty.counterparty_id,
            subject_name=counterparty.legal_name,
            screening_type=screening_type,
            result=screening_result,
            method="exact",
            matched_entries=matched_entries,
            reviewed_by_human=screening_result == "confirmed_match",
            source=_source("SRC-SCREEN", "official_publication", "tier_1"),
            record_status="verified",
        ),
        ComplianceScreeningResult(
            screening_id="SCREEN-VN-FATF",
            subject_type="country",
            subject_id="VN",
            subject_name="Vietnam",
            screening_type="aml_country",
            result="clear",
            method="exact",
            source=_source("SRC-FATF-SCREEN", "official_publication", "tier_1"),
            record_status="verified",
        ),
    ]
    payments = []
    if include_payment:
        payments.append(
            PaymentStructure(
                payment_structure_id="PAY-EXP-001",
                transaction_id="EXP-001",
                method="open_account",
                tenor_days=90,
                deferred_payment_percent=Decimal("100"),
                payment_trigger="90 days after shipment",
                source=_source("SRC-PAY", "user_document", "user_provided"),
                record_status="verified",
            )
        )
    documents = []
    if include_document:
        documents.append(
            TradeDocumentProfile(
                document_id="DOC-CONTRACT-001",
                evidence_id="EVID-CONTRACT-001",
                document_type="contract",
                currency="USD",
                amount=Decimal("500000"),
                linked_transaction_ids=["EXP-001"],
                payment_structure_id="PAY-EXP-001" if include_payment else None,
                reviewed_fields={"governing_law": "Republic of Korea"},
                source=_source("SRC-CONTRACT", "user_document", "user_provided"),
                record_status="verified",
            )
        )
    risk_signals = []
    if include_high_signals:
        risk_signals.extend(
            [
                TradeRiskSignal(
                    signal_id="RISK-DOC-EXP-001",
                    category="contract_document",
                    severity="high",
                    title="지급기산점 조건 보완 필요",
                    factual_trigger="buyer acceptance period is unresolved",
                    affected_transaction_ids=["EXP-001"],
                    affected_document_ids=["DOC-CONTRACT-001"],
                    evidence_ids=["EVID-CONTRACT-001"],
                    unresolved_facts=["검수기간과 간주승인 조건 확인"],
                    source=_source("SRC-DOC-RULE"),
                    record_status="verified",
                ),
                TradeRiskSignal(
                    signal_id="RISK-CAPACITY-EXP-001",
                    category="liquidity",
                    severity="high",
                    title="필요자금이 식별 유동성을 초과함",
                    factual_trigger="funding_need_to_liquid_assets_pct=112.50% > 100%",
                    affected_transaction_ids=["EXP-001"],
                    calculation_ids=[_calculation().calculation_id],
                    unresolved_facts=["가용한도와 다른 현금유출 확인"],
                    source=_source("SRC-CAPACITY-RULE"),
                    record_status="verified",
                ),
            ]
        )
    risk_signals.append(
        TradeRiskSignal(
            signal_id="RISK-OTHER-TRANSACTION",
            category="operational",
            severity="critical",
            title="다른 거래 위험",
            factual_trigger="not relevant to EXP-001",
            affected_transaction_ids=["EXP-OTHER"],
            evidence_ids=["EVID-OTHER"],
            source=_source("SRC-OTHER-RULE"),
            record_status="verified",
        )
    )
    products = _product_result() if include_products else None
    calculation = _calculation()
    calculations = {calculation.calculation_id: calculation} if include_calculation else {}
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-DECISION-BRIEF",
            company_name="Example Exporter Co., Ltd.",
            analysis_as_of_date=date(2026, 7, 26),
        ),
        evidence=[
            CaseEvidenceItem(
                evidence_id="EVID-CONTRACT-001",
                evidence_type="contract",
                source_name="contract.pdf",
                status="approved",
                linked_transaction_ids=["EXP-001"],
            )
        ],
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "expected_date": "2026-10-31",
            }
        ],
        calculations=calculations,
        trade_finance=TradeFinanceDomainState(
            counterparties=[counterparty],
            country_risk_facts=country_facts,
            compliance_screenings=screenings,
            payment_structures=payments,
            trade_documents=documents,
            risk_signals=risk_signals,
            product_candidates=(products.product_candidates if products else []),
            consultation_requirements=(
                products.consultation_requirements if products else []
            ),
        ),
    )


def _request(case, **updates):
    payload = {
        "brief_id": "BRIEF-EXP-001",
        "transaction_id": "EXP-001",
        "counterparty_id": "BUYER-001",
        "country_code": "VN",
        "product_candidate_ids": [
            item.product_candidate_id
            for item in case.trade_finance.product_candidates
            if item.candidate_status in {"consultation_candidate", "insufficient_information"}
        ],
        "consultation_requirement_ids": [
            item.requirement_id
            for item in case.trade_finance.consultation_requirements
        ],
        "max_ranked_concerns": 5,
    }
    payload.update(updates)
    return TransactionDecisionBriefRequest(**payload)


def test_registry_uses_explicit_orders_and_no_score():
    registry = load_transaction_decision_brief_registry()

    assert registry.registry_version == "transaction-decision-brief/1.0"
    assert registry.severity_order[0] == "critical"
    assert registry.category_order[0] == "compliance"
    assert "score" not in registry.model_dump()
    assert "does not approve or reject" in registry.authority_boundary


def test_high_concerns_create_conditions_before_commitment_and_rank_deterministically():
    case = _case()
    brief = build_transaction_decision_brief(case, _request(case))

    assert brief.disposition == "conditions_required_before_commitment"
    assert [item.rank for item in brief.ranked_concerns] == list(
        range(1, len(brief.ranked_concerns) + 1)
    )
    assert brief.ranked_concerns[0].category == "counterparty"
    assert {item.category for item in brief.ranked_concerns} >= {
        "counterparty",
        "contract_document",
        "liquidity",
        "compliance",
    }
    assert not any(item.concern_id == "CONCERN-RISK-OTHER-TRANSACTION" for item in brief.ranked_concerns)


def test_potential_sanctions_match_requires_specialist_clearance():
    case = _case(screening_result="potential_match", screening_type="sanctions")
    brief = build_transaction_decision_brief(case, _request(case))

    assert brief.disposition == "specialist_clearance_required"
    assert brief.ranked_concerns[0].category == "compliance"
    assert brief.ranked_concerns[0].severity == "critical"


def test_missing_minimum_coverage_is_not_misreported_as_low_risk():
    case = _case(
        include_high_signals=False,
        counterparty_status="professional_credit_investigation_completed",
        include_country=False,
        include_payment=False,
        include_document=False,
        include_calculation=False,
        include_products=False,
    )
    request = _request(
        case,
        country_code=None,
        product_candidate_ids=[],
        consultation_requirement_ids=[],
    )
    brief = build_transaction_decision_brief(case, request)

    assert brief.disposition == "additional_information_required"
    assert any(item.startswith("country_context") for item in brief.missing_information)
    assert any(item.startswith("payment_structure") for item in brief.missing_information)
    assert any(
        item.startswith("financial_capacity_calculation")
        for item in brief.missing_information
    )


def test_complete_clear_case_returns_no_material_flags_with_explicit_limitation():
    case = _case(
        include_high_signals=False,
        counterparty_status="professional_credit_investigation_completed",
    )
    case = case.model_copy(
        update={
            "trade_finance": case.trade_finance.model_copy(
                update={
                    "country_risk_facts": [case.trade_finance.country_risk_facts[0]],
                }
            )
        }
    )
    brief = build_transaction_decision_brief(case, _request(case))

    assert brief.disposition == "no_material_screening_flags"
    assert brief.ranked_concerns == []
    assert any("not an approval" in item.lower() for item in brief.disposition_rationale)
    assert "does not approve or reject" in brief.authority_boundary


def test_action_plan_has_explicit_dependencies_and_product_routes():
    case = _case()
    brief = build_transaction_decision_brief(case, _request(case))
    by_title = {item.title: item for item in brief.action_plan}
    reassessment = by_title["조건 반영 후 거래 사전진단 재실행"]

    assert reassessment.sequence == len(brief.action_plan)
    assert len(reassessment.dependency_action_ids) == len(brief.action_plan) - 1
    assert any("국외기업 신용조사" in title for title in by_title)
    assert any(item.responsible_party == "bank" for item in brief.action_plan)
    assert all(
        dependency != item.action_id
        for item in brief.action_plan
        for dependency in item.dependency_action_ids
    )


def test_selected_product_and_requirement_ids_are_validated():
    case = _case()
    with pytest.raises(ValueError, match="Unknown product candidate IDs"):
        build_transaction_decision_brief(
            case,
            _request(case, product_candidate_ids=["PRODUCT-UNKNOWN"]),
        )
    with pytest.raises(ValueError, match="Unknown consultation requirement IDs"):
        build_transaction_decision_brief(
            case,
            _request(case, consultation_requirement_ids=["CONSULT-UNKNOWN"]),
        )


def test_counterparty_country_conflict_is_rejected():
    case = _case()
    with pytest.raises(ValueError, match="does not match"):
        build_transaction_decision_brief(case, _request(case, country_code="US"))


def test_apply_is_immutable_idempotent_and_replaces_current_transaction_actions():
    case = _case()
    request = _request(case)
    before = case.case_hash

    first, first_brief, first_outcome = apply_transaction_decision_brief(case, request)
    second, second_brief, second_outcome = apply_transaction_decision_brief(first, request)

    assert case.trade_finance.action_plan == []
    assert case.case_hash == before
    assert first.case_hash != before
    assert second.case_hash == first.case_hash
    assert second_outcome.action_ids == first_outcome.action_ids
    assert second_brief.model_dump(mode="json") == first_brief.model_dump(mode="json")
    assert len(second.trade_finance.action_plan) == len(first.trade_finance.action_plan)


def test_max_ranked_concerns_limits_display_not_disposition_logic():
    case = _case(screening_result="potential_match", screening_type="sanctions")
    brief = build_transaction_decision_brief(
        case,
        _request(case, max_ranked_concerns=1),
    )

    assert len(brief.ranked_concerns) == 1
    assert brief.disposition == "specialist_clearance_required"
