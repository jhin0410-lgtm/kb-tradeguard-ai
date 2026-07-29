"""Synthetic end-to-end smoke test for the governed single-transaction pipeline.

Usage:
    python scripts/single_transaction_pipeline_smoke_test.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.copilot_case import (  # noqa: E402
    CaseDataAsset,
    CaseEvidenceItem,
    CaseIdentity,
    UnifiedCopilotCase,
)
from src.intelligence import (  # noqa: E402
    SingleTransactionAssessmentRequest,
    TradeFinanceNeedProfile,
    TransactionCapacityRequest,
    run_single_transaction_assessment,
)
from src.trade_finance_domain import (  # noqa: E402
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


def _source(source_id: str, kind: str = "user_document", tier: str = "user_provided"):
    return SourceReference(
        source_id=source_id,
        source_name=f"Synthetic source {source_id}",
        source_tier=tier,
        source_kind=kind,
        source_locator=f"fixture://{source_id}",
        as_of_date=date(2026, 7, 26),
        effective_date_verified=True,
    )


def _build_case() -> UnifiedCopilotCase:
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
        operating_cash_flow=Decimal("180000000"),
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
            case_id="CASE-PIPELINE-SMOKE",
            company_name=company.legal_name,
            analysis_as_of_date=date.today(),
        ),
        evidence=[
            CaseEvidenceItem(
                evidence_id=contract.evidence_id,
                evidence_type="contract",
                source_name="contract.pdf",
                status="approved",
                linked_transaction_ids=["EXP-001"],
            ),
            CaseEvidenceItem(
                evidence_id=invoice.evidence_id,
                evidence_type="commercial_invoice",
                source_name="invoice.pdf",
                status="approved",
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
            as_of_date=date.today(),
            payload=[{"currency": "USD", "spot_rate_krw": 1350}],
        ),
        trade_finance=TradeFinanceDomainState(
            company_profile=company,
            financial_statements=[statement],
            counterparties=[counterparty],
            country_risk_facts=[
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
            ],
            compliance_screenings=[
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
            ],
            payment_structures=[payment],
            trade_documents=[contract, invoice],
        ),
    )


def main() -> int:
    case = _build_case()
    request = SingleTransactionAssessmentRequest(
        pipeline_id="PIPELINE-EXP-001",
        brief_id="BRIEF-EXP-001",
        transaction_id="EXP-001",
        counterparty_id="BUYER-VN-001",
        country_code="VN",
        capacity_request=TransactionCapacityRequest(
            assessment_id="CAPACITY-EXP-001",
            transaction_id="EXP-001",
            statement_id="FS-2025-CFS",
            payment_structure_id="PAY-EXP-001",
            protection_percent=Decimal("80"),
            pre_shipment_funding_need_krw=Decimal("450000000"),
        ),
        product_profiles=[
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
    )
    updated, result = run_single_transaction_assessment(case, request)
    output = {
        "status": "ok",
        "pipeline_id": result.pipeline_id,
        "pipeline_version": result.pipeline_version,
        "transaction_id": result.transaction_id,
        "authority_boundary": result.authority_boundary,
        "case_before_hash": result.case_before_hash,
        "case_after_hash": result.case_after_hash,
        "stage_traces": [item.model_dump(mode="json") for item in result.stage_traces],
        "disposition": result.brief.disposition,
        "ranked_concerns": [
            item.model_dump(mode="json") for item in result.brief.ranked_concerns
        ],
        "missing_information": result.brief.missing_information,
        "product_candidate_ids": result.brief.product_candidate_ids,
        "action_plan": [
            item.model_dump(mode="json") for item in result.brief.action_plan
        ],
        "final_record_counts": result.final_record_counts,
        "final_calculation_ids": sorted(updated.calculations),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
