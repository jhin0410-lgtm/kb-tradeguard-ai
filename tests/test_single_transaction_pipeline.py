from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.copilot_case import CaseDataAsset, CaseEvidenceItem, CaseIdentity, UnifiedCopilotCase
from src.intelligence.single_transaction_pipeline import (
    SingleTransactionAssessmentRequest,
    TransactionAssessmentPipelineError,
    load_single_transaction_pipeline_manifest,
    run_single_transaction_assessment,
)
from src.intelligence.product_matching import TradeFinanceNeedProfile
from src.intelligence.transaction_capacity import TransactionCapacityRequest
from src.trade_finance_domain import (
    CompanyProfile,
    ComplianceScreeningResult,
    CounterpartyProfile,
    CountryRiskFact,
    FinancialStatementSnapshot,
    PaymentStructure,
    SourceReference,
    TradeDocumentProfile,
    TradeFinanceDomainState,
)


def _source(source_id, kind="user_document", tier="user_provided"):
    return SourceReference(
        source_id=source_id,
        source_name=f"Synthetic source {source_id}",
        source_tier=tier,
        source_kind=kind,
        source_locator=f"fixture://{source_id}",
        as_of_date=date(2026, 7, 26),
        effective_date_verified=True,
    )


def _full_case(evidence_status="approved"):
    company = CompanyProfile(
        company_id="COMPANY-001",
        legal_name="Example Exporter Co., Ltd.",
        sme_status="confirmed",
        source=_source("SRC-COMPANY", "official_api", "tier_1"),
        record_status="verified",
    )
    statement = FinancialStatementSnapshot(
        statement_id="FS-2025-CFS",
        company_id=company.company_id,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        report_type="annual",
        consolidation_scope="consolidated",
        cash_and_cash_equivalents=Decimal("300000000"),
        short_term_financial_assets=Decimal("100000000"),
        current_assets=Decimal("1000000000"),
        current_liabilities=Decimal("600000000"),
        equity=Decimal("500000000"),
        revenue=Decimal("5000000000"),
        source=_source("SRC-FS", "official_api", "tier_1"),
        record_status="verified",
    )
    counterparty = CounterpartyProfile(
        counterparty_id="BUYER-VN-001",
        legal_name="Vietnam Buyer Co., Ltd.",
        country_code="VN",
        registration_number="VN-REG-001",
        relationship_status="new",
        due_diligence_status="professional_credit_investigation_required",
        prior_payment_history="none",
        source=_source("SRC-BUYER"),
        record_status="verified",
    )
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
    screenings = [
        ComplianceScreeningResult(
            screening_id="SCREEN-BUYER-VN-001",
            subject_type="counterparty",
            subject_id=counterparty.counterparty_id,
            subject_name=counterparty.legal_name,
            screening_type="sanctions",
            result="clear",
            method="exact",
            source=_source("SRC-SANCTIONS", "official_publication", "tier_1"),
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
    payment = PaymentStructure(
        payment_structure_id="PAY-EXP-001",
        transaction_id="EXP-001",
        method="open_account",
        tenor_days=90,
        deferred_payment_percent=Decimal("100"),
        payment_trigger="90 days after shipment",
        source=_source("SRC-PAY"),
        record_status="verified",
    )
    contract = TradeDocumentProfile(
        document_id="DOC-CONTRACT-001",
        evidence_id="EVID-CONTRACT-001",
        document_type="contract",
        currency="USD",
        amount=Decimal("500000"),
        incoterms_rule="FCA",
        incoterms_year=2020,
        named_place=None,
        payment_structure_id=payment.payment_structure_id,
        linked_transaction_ids=["EXP-001"],
        reviewed_fields={
            "seller_name": company.legal_name,
            "buyer_name": counterparty.legal_name,
            "governing_law": "Republic of Korea",
            "dispute_resolution": "KCAB International arbitration",
            "acceptance_period_days": 10,
            "buyer_unilateral_setoff_right": False,
            "buyer_unilateral_amendment_right": False,
        },
        source=_source("SRC-CONTRACT"),
        record_status="verified",
    )
    invoice = TradeDocumentProfile(
        document_id="DOC-INVOICE-001",
        evidence_id="EVID-INVOICE-001",
        document_type="commercial_invoice",
        currency="EUR",
        amount=Decimal("510000"),
        incoterms_rule="FCA",
        incoterms_year=2020,
        named_place="Busan New Port, Republic of Korea",
        linked_transaction_ids=["EXP-001"],
        reviewed_fields={
            "seller_name": company.legal_name,
            "buyer_name": counterparty.legal_name,
        },
        source=_source("SRC-INVOICE"),
        record_status="verified",
    )
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-SINGLE-PIPELINE",
            company_name=company.legal_name,
            analysis_as_of_date=date(2026, 7, 26),
        ),
        evidence=[
            CaseEvidenceItem(
                evidence_id=contract.evidence_id,
                evidence_type="contract",
                source_name="contract.pdf",
                status=evidence_status,
                linked_transaction_ids=["EXP-001"],
            ),
            CaseEvidenceItem(
                evidence_id=invoice.evidence_id,
                evidence_type="commercial_invoice",
                source_name="invoice.pdf",
                status=evidence_status,
                linked_transaction_ids=["EXP-001"],
            ),
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
        official_fx_reference=CaseDataAsset(
            asset_name="reviewed FX reference",
            status="available",
            source="synthetic FX fixture",
            as_of_date=date(2026, 7, 26),
            payload=[{"currency": "USD", "spot_rate_krw": 1350}],
        ),
        trade_finance=TradeFinanceDomainState(
            company_profile=company,
            financial_statements=[statement],
            counterparties=[counterparty],
            country_risk_facts=country_facts,
            compliance_screenings=screenings,
            payment_structures=[payment],
            trade_documents=[contract, invoice],
        ),
    )


def _request(**updates):
    payload = {
        "pipeline_id": "PIPELINE-EXP-001",
        "brief_id": "BRIEF-EXP-001",
        "transaction_id": "EXP-001",
        "counterparty_id": "BUYER-VN-001",
        "country_code": "VN",
        "capacity_request": TransactionCapacityRequest(
            assessment_id="CAPACITY-EXP-001",
            transaction_id="EXP-001",
            statement_id="FS-2025-CFS",
            payment_structure_id="PAY-EXP-001",
            protection_percent=Decimal("80"),
            pre_shipment_funding_need_krw=Decimal("450000000"),
        ),
        "product_profiles": [
            TradeFinanceNeedProfile(
                profile_id="NEED-EXP-001",
                transaction_id="EXP-001",
                transaction_direction="export",
                transaction_stage="pre_shipment",
                declared_needs=[
                    "buyer_credit_investigation",
                    "export_receivable_nonpayment_protection",
                    "pre_shipment_working_capital",
                ],
                company_size="sme",
                payment_method="open_account",
                tenor_days=90,
                preferred_bank="KB국민은행",
                available_documents=["수출계약 또는 발주서"],
            )
        ],
    }
    payload.update(updates)
    return SingleTransactionAssessmentRequest(**payload)


def test_manifest_fixes_single_transaction_scope_and_stage_order():
    manifest = load_single_transaction_pipeline_manifest()

    assert manifest.pipeline_version == "single-transaction-assessment/1.0"
    assert manifest.single_transaction_case_required is True
    assert manifest.stage_order == [
        "trade_document_screening",
        "document_reconciliation",
        "transaction_capacity",
        "product_matching",
        "transaction_decision_brief",
    ]
    assert "does not approve or reject" in manifest.authority_boundary


def test_full_pipeline_runs_all_stages_and_builds_integrated_case():
    case = _full_case()
    before = case.case_hash

    updated, result = run_single_transaction_assessment(case, _request())

    assert case.case_hash == before
    assert case.trade_finance.risk_signals == []
    assert case.calculations == {}
    assert result.case_before_hash == before
    assert result.case_after_hash == updated.case_hash
    assert [item.status for item in result.stage_traces] == ["completed"] * 5
    assert [item.sequence for item in result.stage_traces] == [1, 2, 3, 4, 5]
    assert result.brief.disposition == "conditions_required_before_commitment"
    assert updated.trade_finance.clause_findings
    assert updated.trade_finance.risk_signals
    assert updated.calculations
    assert updated.trade_finance.product_candidates
    assert updated.trade_finance.consultation_requirements
    assert updated.trade_finance.action_plan
    assert any(
        "CONTRACT-INVOICE-CURRENCY" in item.clause_finding_id
        for item in updated.trade_finance.clause_findings
    )
    assert any(
        "FUNDING-NEED-EXCEEDS-LIQUID-ASSETS" in item.signal_id
        for item in updated.trade_finance.risk_signals
    )


def test_brief_selects_only_usable_candidates_generated_by_pipeline():
    updated, result = run_single_transaction_assessment(_full_case(), _request())
    selected = set(result.brief.product_candidate_ids)
    candidates = {
        item.product_candidate_id: item
        for item in updated.trade_finance.product_candidates
    }

    assert selected
    assert all(
        candidates[identifier].candidate_status
        in {"consultation_candidate", "insufficient_information"}
        for identifier in selected
    )
    assert not any(
        item.candidate_status in {"blocked", "not_applicable"}
        and item.product_candidate_id in selected
        for item in updated.trade_finance.product_candidates
    )


def test_pipeline_is_idempotent_for_same_reviewed_case_and_request():
    first, first_result = run_single_transaction_assessment(_full_case(), _request())
    second, second_result = run_single_transaction_assessment(first, _request())

    assert second.case_hash == first.case_hash
    assert second_result.brief.model_dump(mode="json") == first_result.brief.model_dump(
        mode="json"
    )
    assert len(second.trade_finance.clause_findings) == len(
        first.trade_finance.clause_findings
    )
    assert len(second.trade_finance.risk_signals) == len(first.trade_finance.risk_signals)
    assert len(second.trade_finance.action_plan) == len(first.trade_finance.action_plan)


def test_optional_stages_are_explicitly_skipped_and_brief_reports_gaps():
    case = _full_case()
    domain = case.trade_finance.model_copy(
        update={"payment_structures": [], "trade_documents": []}
    )
    case = case.model_copy(update={"trade_finance": domain, "evidence": []})
    request = _request(capacity_request=None, product_profiles=[])

    _, result = run_single_transaction_assessment(case, request)

    assert [item.status for item in result.stage_traces[:4]] == [
        "skipped",
        "skipped",
        "skipped",
        "skipped",
    ]
    assert result.stage_traces[-1].status == "completed"
    assert result.brief.disposition == "additional_information_required"
    assert any(
        item.startswith("payment_structure")
        for item in result.brief.missing_information
    )
    assert any(
        item.startswith("reviewed_trade_document")
        for item in result.brief.missing_information
    )
    assert any(
        item.startswith("financial_capacity_calculation")
        for item in result.brief.missing_information
    )


def test_pipeline_rejects_multi_transaction_case_before_running_stages():
    case = _full_case()
    case = case.model_copy(
        update={
            "approved_transactions": case.approved_transactions
            + [
                {
                    "transaction_id": "EXP-002",
                    "transaction_type": "export",
                    "currency": "USD",
                    "amount_fc": 100000,
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="exactly one approved transaction"):
        run_single_transaction_assessment(case, _request())


def test_nested_capacity_and_product_transactions_must_match_pipeline_request():
    with pytest.raises(ValidationError, match="Capacity request transaction"):
        _request(
            capacity_request=TransactionCapacityRequest(
                assessment_id="CAPACITY-OTHER",
                transaction_id="EXP-OTHER",
                statement_id="FS-2025-CFS",
            )
        )

    with pytest.raises(ValidationError, match="Product profiles do not match"):
        _request(
            product_profiles=[
                TradeFinanceNeedProfile(
                    profile_id="NEED-OTHER",
                    transaction_id="EXP-OTHER",
                    transaction_direction="export",
                    transaction_stage="pre_shipment",
                    declared_needs=["buyer_credit_investigation"],
                )
            ]
        )


def test_stage_failure_is_identified_and_no_partial_case_is_returned():
    case = _full_case(evidence_status="review_required")
    before = case.case_hash

    with pytest.raises(TransactionAssessmentPipelineError) as caught:
        run_single_transaction_assessment(case, _request())

    assert caught.value.stage_name == "trade_document_screening"
    assert caught.value.case_hash == before
    assert "approved case evidence" in str(caught.value)
    assert case.trade_finance.clause_findings == []
    assert case.trade_finance.risk_signals == []
