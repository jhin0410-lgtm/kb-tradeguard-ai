"""Deterministic showcase scenarios for the assessment Streamlit application.

The scenarios intentionally separate presentation fixtures from real customer data. They use
synthetic reviewed transaction records plus clearly labelled official-source-style snapshots so
that the complete pipeline can be demonstrated without exposing confidential documents or
claiming that a real institution approved the transaction.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict

from .copilot_case import (
    CaseDataAsset,
    CaseEvidenceItem,
    CaseIdentity,
    UnifiedCopilotCase,
)
from .intelligence.product_matching import TradeFinanceNeedProfile
from .intelligence.single_transaction_package import (
    SingleTransactionAssessmentPackage,
    load_single_transaction_package,
)
from .intelligence.single_transaction_pipeline import SingleTransactionAssessmentRequest
from .intelligence.transaction_capacity import TransactionCapacityRequest
from .trade_finance_domain import (
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

DemoDisposition = Literal[
    "specialist_clearance_required",
    "conditions_required_before_commitment",
    "additional_information_required",
    "review_required",
    "no_material_screening_flags",
]

ROOT = Path(__file__).resolve().parents[1]
MINIMAL_PACKAGE = ROOT / "examples" / "single_transaction_assessment_package_minimal.json"


class DemoScenarioMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str
    title: str
    summary: str
    expected_disposition: DemoDisposition
    source_modes: list[str]
    highlight: str


def _source(
    source_id: str,
    *,
    name: str | None = None,
    kind: str = "user_document",
    tier: str = "user_provided",
    locator_prefix: str = "demo",
) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_name=name or f"Synthetic reviewed source {source_id}",
        source_tier=tier,
        source_kind=kind,
        source_locator=f"{locator_prefix}://{source_id}",
        as_of_date=date(2026, 7, 27),
        effective_date_verified=True,
    )


def _company_and_statement(
    *,
    company_id: str,
    statement_id: str,
    legal_name: str,
    cash: str,
    short_term_financial_assets: str,
    current_assets: str,
    current_liabilities: str,
    equity: str,
    revenue: str,
    operating_cash_flow: str,
) -> tuple[CompanyProfile, FinancialStatementSnapshot]:
    company = CompanyProfile(
        company_id=company_id,
        legal_name=legal_name,
        sme_status="confirmed",
        source=_source(
            f"SRC-{company_id}",
            name="Synthetic OpenDART-style company snapshot",
            kind="official_api",
            tier="tier_1",
            locator_prefix="synthetic-official-snapshot",
        ),
        record_status="verified",
        limitations=[
            "Synthetic demonstration company; not a real customer or OpenDART conclusion."
        ],
    )
    statement = FinancialStatementSnapshot(
        statement_id=statement_id,
        company_id=company_id,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        report_type="annual",
        consolidation_scope="consolidated",
        cash_and_cash_equivalents=Decimal(cash),
        short_term_financial_assets=Decimal(short_term_financial_assets),
        current_assets=Decimal(current_assets),
        current_liabilities=Decimal(current_liabilities),
        equity=Decimal(equity),
        revenue=Decimal(revenue),
        operating_cash_flow=Decimal(operating_cash_flow),
        source=_source(
            f"SRC-{statement_id}",
            name="Synthetic OpenDART-style financial snapshot",
            kind="official_api",
            tier="tier_1",
            locator_prefix="synthetic-official-snapshot",
        ),
        record_status="verified",
        limitations=[
            "Synthetic financial values for deterministic demonstration only."
        ],
    )
    return company, statement


def _counterparty(
    *,
    counterparty_id: str,
    legal_name: str,
    country_code: str,
    registration_number: str,
    due_diligence_status: str,
    prior_payment_history: str,
) -> CounterpartyProfile:
    return CounterpartyProfile(
        counterparty_id=counterparty_id,
        legal_name=legal_name,
        country_code=country_code,
        registration_number=registration_number,
        relationship_status="new",
        due_diligence_status=due_diligence_status,
        prior_payment_history=prior_payment_history,
        source=_source(f"SRC-{counterparty_id}"),
        record_status="verified",
        limitations=["Synthetic counterparty record for demonstration only."],
    )


def _country_context(
    *,
    country_code: str,
    counterparty: CounterpartyProfile,
    include_fatf_context: bool,
) -> tuple[list[CountryRiskFact], list[ComplianceScreeningResult]]:
    facts = [
        CountryRiskFact(
            fact_id=f"COUNTRY-{country_code}-MACRO-DEMO",
            country_code=country_code,
            dimension="macroeconomic",
            metric_name="GDP growth",
            value=Decimal("6.50"),
            unit="% annual growth",
            observation_date=date(2025, 12, 31),
            risk_direction="lower_is_worse",
            interpretation="Synthetic macroeconomic context; no standalone risk grade.",
            source=_source(
                f"SRC-{country_code}-MACRO",
                name="Synthetic World Bank-style country snapshot",
                kind="official_api",
                tier="tier_1",
                locator_prefix="synthetic-official-snapshot",
            ),
            record_status="verified",
            limitations=["Demonstration value, not a live country-risk observation."],
        )
    ]
    screenings = [
        ComplianceScreeningResult(
            screening_id=f"SCREEN-{counterparty.counterparty_id}-DEMO",
            subject_type="counterparty",
            subject_id=counterparty.counterparty_id,
            subject_name=counterparty.legal_name,
            screening_type="sanctions",
            result="clear",
            method="exact",
            source=_source(
                f"SRC-{counterparty.counterparty_id}-SCREEN",
                name="Synthetic sanctions-screening snapshot",
                kind="official_publication",
                tier="tier_1",
                locator_prefix="synthetic-official-snapshot",
            ),
            record_status="verified",
            limitations=["Synthetic clear result; not sanctions or AML clearance."],
        )
    ]
    if include_fatf_context:
        facts.append(
            CountryRiskFact(
                fact_id=f"COUNTRY-{country_code}-FATF-DEMO",
                country_code=country_code,
                dimension="sanctions_aml",
                metric_name="FATF public-list status",
                value="increased_monitoring",
                observation_date=date(2026, 6, 19),
                risk_direction="categorical",
                interpretation=(
                    "Synthetic increased-monitoring context used to demonstrate a review flag; "
                    "it is not a transaction prohibition."
                ),
                source=_source(
                    f"SRC-{country_code}-FATF",
                    name="Synthetic FATF-style public-list snapshot",
                    kind="official_publication",
                    tier="tier_1",
                    locator_prefix="synthetic-official-snapshot",
                ),
                record_status="verified",
                limitations=["Demonstration status; verify the current official FATF list."],
            )
        )
        screenings.append(
            ComplianceScreeningResult(
                screening_id=f"SCREEN-{country_code}-FATF-DEMO",
                subject_type="country",
                subject_id=country_code,
                subject_name=country_code,
                screening_type="aml_country",
                result="clear",
                method="exact",
                source=_source(
                    f"SRC-{country_code}-FATF-SCREEN",
                    name="Synthetic country-policy screening snapshot",
                    kind="official_publication",
                    tier="tier_1",
                    locator_prefix="synthetic-official-snapshot",
                ),
                record_status="verified",
                limitations=[
                    "Clear means no additional configured match in this fixture, not AML clearance."
                ],
            )
        )
    return facts, screenings


def _fx_asset(rate: str) -> CaseDataAsset:
    return CaseDataAsset(
        asset_name="Reviewed USD/KRW reference",
        status="available",
        source="synthetic official FX snapshot",
        as_of_date=date(2026, 7, 27),
        source_hash="synthetic-demo-fx",
        payload=[{"currency": "USD", "spot_rate_krw": Decimal(rate)}],
        limitations=["Synthetic rate for deterministic demonstration only."],
    )


def _approved_evidence(*documents: TradeDocumentProfile) -> list[CaseEvidenceItem]:
    return [
        CaseEvidenceItem(
            evidence_id=document.evidence_id,
            evidence_type=document.document_type,
            source_name=f"{document.document_id}.json",
            status="approved",
            source_locator=document.source.source_locator,
            linked_transaction_ids=list(document.linked_transaction_ids),
            warnings=["Synthetic reviewed-field fixture; no original customer document attached."],
        )
        for document in documents
    ]


def _package(
    *,
    case: UnifiedCopilotCase,
    request: SingleTransactionAssessmentRequest,
    notes: list[str],
) -> SingleTransactionAssessmentPackage:
    return SingleTransactionAssessmentPackage(
        case=case,
        request=request,
        expected_input_case_hash=case.case_hash,
        notes=notes,
    )


def _missing_information_package() -> SingleTransactionAssessmentPackage:
    return load_single_transaction_package(MINIMAL_PACKAGE)


def _oa_high_risk_package() -> SingleTransactionAssessmentPackage:
    transaction_id = "EXP-DEMO-OA-001"
    company, statement = _company_and_statement(
        company_id="COMP-DEMO-OA",
        statement_id="FS-DEMO-OA-2025",
        legal_name="Hanbit Components Co., Ltd.",
        cash="300000000",
        short_term_financial_assets="100000000",
        current_assets="1000000000",
        current_liabilities="600000000",
        equity="500000000",
        revenue="5000000000",
        operating_cash_flow="180000000",
    )
    buyer = _counterparty(
        counterparty_id="BUYER-DEMO-VN-OA",
        legal_name="Vietnam Demo Buyer Co., Ltd.",
        country_code="VN",
        registration_number="VN-DEMO-REG-001",
        due_diligence_status="professional_credit_investigation_required",
        prior_payment_history="none",
    )
    country_facts, screenings = _country_context(
        country_code="VN", counterparty=buyer, include_fatf_context=True
    )
    payment = PaymentStructure(
        payment_structure_id="PAY-DEMO-OA-001",
        transaction_id=transaction_id,
        method="open_account",
        tenor_days=90,
        deferred_payment_percent=Decimal("100"),
        payment_trigger="90 days after shipment",
        source=_source("SRC-PAY-DEMO-OA"),
        record_status="verified",
    )
    contract = TradeDocumentProfile(
        document_id="DOC-DEMO-OA-CONTRACT",
        evidence_id="EVID-DEMO-OA-CONTRACT",
        document_type="contract",
        currency="USD",
        amount=Decimal("500000"),
        incoterms_rule="FCA",
        incoterms_year=2020,
        named_place=None,
        payment_structure_id=payment.payment_structure_id,
        linked_transaction_ids=[transaction_id],
        reviewed_fields={
            "seller_name": company.legal_name,
            "buyer_name": buyer.legal_name,
            "governing_law": "Republic of Korea",
            "dispute_resolution": "KCAB International arbitration in Seoul",
            "acceptance_period_days": 10,
            "buyer_unilateral_setoff_right": False,
            "buyer_unilateral_amendment_right": False,
        },
        source=_source("SRC-DOC-DEMO-OA-CONTRACT"),
        record_status="verified",
    )
    invoice = TradeDocumentProfile(
        document_id="DOC-DEMO-OA-INVOICE",
        evidence_id="EVID-DEMO-OA-INVOICE",
        document_type="commercial_invoice",
        currency="EUR",
        amount=Decimal("510000"),
        incoterms_rule="FCA",
        incoterms_year=2020,
        named_place="Busan New Port, Republic of Korea",
        linked_transaction_ids=[transaction_id],
        reviewed_fields={
            "seller_name": company.legal_name,
            "buyer_name": buyer.legal_name,
        },
        source=_source("SRC-DOC-DEMO-OA-INVOICE"),
        record_status="verified",
    )
    case = UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-DEMO-OA-HIGH-RISK",
            company_name=company.legal_name,
            analysis_as_of_date=date(2026, 7, 27),
        ),
        evidence=_approved_evidence(contract, invoice),
        approved_transactions=[
            {
                "transaction_id": transaction_id,
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "expected_date": "2026-10-31",
            }
        ],
        official_fx_reference=_fx_asset("1350"),
        trade_finance=TradeFinanceDomainState(
            company_profile=company,
            financial_statements=[statement],
            counterparties=[buyer],
            country_risk_facts=country_facts,
            compliance_screenings=screenings,
            payment_structures=[payment],
            trade_documents=[contract, invoice],
        ),
    )
    request = SingleTransactionAssessmentRequest(
        pipeline_id="PIPELINE-DEMO-OA-001",
        brief_id="BRIEF-DEMO-OA-001",
        transaction_id=transaction_id,
        counterparty_id=buyer.counterparty_id,
        country_code="VN",
        capacity_request=TransactionCapacityRequest(
            assessment_id="CAPACITY-DEMO-OA-001",
            transaction_id=transaction_id,
            statement_id=statement.statement_id,
            payment_structure_id=payment.payment_structure_id,
            protection_percent=Decimal("80"),
            pre_shipment_funding_need_krw=Decimal("450000000"),
        ),
        product_profiles=[
            TradeFinanceNeedProfile(
                profile_id="NEED-DEMO-OA-001",
                transaction_id=transaction_id,
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
        max_ranked_concerns=8,
    )
    return _package(
        case=case,
        request=request,
        notes=[
            "Synthetic high-risk O/A showcase.",
            "Demonstrates buyer due diligence, FATF context, document discrepancy, liquidity, and product consultation workflows.",
        ],
    )


def _complex_lc_package() -> SingleTransactionAssessmentPackage:
    transaction_id = "EXP-DEMO-LC-001"
    company, statement = _company_and_statement(
        company_id="COMP-DEMO-LC",
        statement_id="FS-DEMO-LC-2025",
        legal_name="Korea Precision Systems Co., Ltd.",
        cash="250000000",
        short_term_financial_assets="150000000",
        current_assets="1500000000",
        current_liabilities="850000000",
        equity="650000000",
        revenue="6000000000",
        operating_cash_flow="220000000",
    )
    buyer = _counterparty(
        counterparty_id="BUYER-DEMO-LC",
        legal_name="Overseas Industrial Buyer Ltd.",
        country_code="VN",
        registration_number="VN-DEMO-REG-LC",
        due_diligence_status="public_information_checked",
        prior_payment_history="unknown",
    )
    country_facts, screenings = _country_context(
        country_code="VN", counterparty=buyer, include_fatf_context=False
    )
    payment = PaymentStructure(
        payment_structure_id="PAY-DEMO-LC-001",
        transaction_id=transaction_id,
        method="letter_of_credit",
        tenor_days=90,
        deferred_payment_percent=Decimal("100"),
        issuing_bank="Example International Bank",
        irrevocable=True,
        confirmed=False,
        payment_trigger="90 days after bill_of_lading_date",
        governing_rules=["UCP 600"],
        source=_source("SRC-PAY-DEMO-LC"),
        record_status="verified",
    )
    contract = TradeDocumentProfile(
        document_id="DOC-DEMO-LC-CONTRACT",
        evidence_id="EVID-DEMO-LC-CONTRACT",
        document_type="contract",
        currency="USD",
        amount=Decimal("750000"),
        incoterms_rule="CIP",
        incoterms_year=2020,
        named_place="Ho Chi Minh City, Vietnam",
        payment_structure_id=payment.payment_structure_id,
        linked_transaction_ids=[transaction_id],
        reviewed_fields={
            "seller_name": company.legal_name,
            "buyer_name": buyer.legal_name,
            "governing_law": "Republic of Korea",
            "dispute_resolution": "KCAB International arbitration in Seoul",
            "acceptance_period_days": 7,
            "buyer_unilateral_setoff_right": False,
            "buyer_unilateral_amendment_right": False,
        },
        source=_source("SRC-DOC-DEMO-LC-CONTRACT"),
        record_status="verified",
    )
    invoice = TradeDocumentProfile(
        document_id="DOC-DEMO-LC-INVOICE",
        evidence_id="EVID-DEMO-LC-INVOICE",
        document_type="commercial_invoice",
        currency="USD",
        amount=Decimal("750000"),
        incoterms_rule="CIP",
        incoterms_year=2020,
        named_place="Ho Chi Minh City, Vietnam",
        linked_transaction_ids=[transaction_id],
        reviewed_fields={
            "seller_name": company.legal_name,
            "buyer_name": buyer.legal_name,
        },
        source=_source("SRC-DOC-DEMO-LC-INVOICE"),
        record_status="verified",
    )
    letter_of_credit = TradeDocumentProfile(
        document_id="DOC-DEMO-LC-CREDIT",
        evidence_id="EVID-DEMO-LC-CREDIT",
        document_type="letter_of_credit",
        currency="USD",
        amount=Decimal("740000"),
        expiry_date=date(2026, 9, 15),
        payment_structure_id=payment.payment_structure_id,
        linked_transaction_ids=[transaction_id],
        reviewed_fields={
            "latest_shipment_date": "2026-10-01",
            "presentation_period_days": 0,
            "buyer_controlled_document_requirements": [
                "Certificate of acceptance issued and signed only by the applicant"
            ],
            "expiry_place": None,
            "availability_type": "acceptance",
            "tenor_days": 90,
            "tenor_start_event": "bill_of_lading_date",
            "draft_required": True,
            "draft_tenor_text": "90 days after B/L date",
            "acceptance_party": None,
            "beneficiary_name": company.legal_name,
            "applicant_name": buyer.legal_name,
        },
        source=_source("SRC-DOC-DEMO-LC-CREDIT"),
        record_status="verified",
    )
    case = UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-DEMO-LC-COMPLEX",
            company_name=company.legal_name,
            analysis_as_of_date=date(2026, 7, 27),
        ),
        evidence=_approved_evidence(contract, invoice, letter_of_credit),
        approved_transactions=[
            {
                "transaction_id": transaction_id,
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 750000,
                "expected_date": "2026-10-31",
            }
        ],
        official_fx_reference=_fx_asset("1350"),
        trade_finance=TradeFinanceDomainState(
            company_profile=company,
            financial_statements=[statement],
            counterparties=[buyer],
            country_risk_facts=country_facts,
            compliance_screenings=screenings,
            payment_structures=[payment],
            trade_documents=[contract, invoice, letter_of_credit],
        ),
    )
    request = SingleTransactionAssessmentRequest(
        pipeline_id="PIPELINE-DEMO-LC-001",
        brief_id="BRIEF-DEMO-LC-001",
        transaction_id=transaction_id,
        counterparty_id=buyer.counterparty_id,
        country_code="VN",
        capacity_request=TransactionCapacityRequest(
            assessment_id="CAPACITY-DEMO-LC-001",
            transaction_id=transaction_id,
            statement_id=statement.statement_id,
            payment_structure_id=payment.payment_structure_id,
            protection_percent=Decimal("50"),
            pre_shipment_funding_need_krw=Decimal("500000000"),
        ),
        product_profiles=[
            TradeFinanceNeedProfile(
                profile_id="NEED-DEMO-LC-001",
                transaction_id=transaction_id,
                transaction_direction="export",
                transaction_stage="post_shipment",
                declared_needs=[
                    "buyer_credit_investigation",
                    "post_shipment_receivables_financing",
                    "fx_cashflow_certainty",
                ],
                company_size="sme",
                payment_method="letter_of_credit",
                tenor_days=90,
                preferred_bank="KB국민은행",
                available_documents=["수출계약", "상업송장", "신용장"],
            )
        ],
        max_ranked_concerns=10,
    )
    return _package(
        case=case,
        request=request,
        notes=[
            "Synthetic complex acceptance L/C showcase.",
            "Demonstrates expiry conflict, zero presentation period, applicant-controlled document, acceptance-party gap, amount discrepancy, and financial-capacity review.",
        ],
    )


def _reviewed_clean_package() -> SingleTransactionAssessmentPackage:
    transaction_id = "EXP-DEMO-CLEAN-001"
    company, statement = _company_and_statement(
        company_id="COMP-DEMO-CLEAN",
        statement_id="FS-DEMO-CLEAN-2025",
        legal_name="Korea Export Solutions Co., Ltd.",
        cash="500000000",
        short_term_financial_assets="200000000",
        current_assets="3000000000",
        current_liabilities="900000000",
        equity="2000000000",
        revenue="10000000000",
        operating_cash_flow="600000000",
    )
    buyer = _counterparty(
        counterparty_id="BUYER-DEMO-CLEAN",
        legal_name="Reviewed Overseas Buyer Ltd.",
        country_code="SG",
        registration_number="SG-DEMO-REG-001",
        due_diligence_status="professional_credit_investigation_completed",
        prior_payment_history="positive",
    )
    country_facts, screenings = _country_context(
        country_code="SG", counterparty=buyer, include_fatf_context=False
    )
    payment = PaymentStructure(
        payment_structure_id="PAY-DEMO-CLEAN-001",
        transaction_id=transaction_id,
        method="letter_of_credit",
        issuing_bank="Example Singapore Bank",
        confirming_bank="Example Korean Confirming Bank",
        irrevocable=True,
        confirmed=True,
        payment_trigger="at sight",
        governing_rules=["UCP 600"],
        source=_source("SRC-PAY-DEMO-CLEAN"),
        record_status="verified",
    )
    common_reviewed = {
        "seller_name": company.legal_name,
        "buyer_name": buyer.legal_name,
    }
    contract = TradeDocumentProfile(
        document_id="DOC-DEMO-CLEAN-CONTRACT",
        evidence_id="EVID-DEMO-CLEAN-CONTRACT",
        document_type="contract",
        currency="USD",
        amount=Decimal("250000"),
        incoterms_rule="FCA",
        incoterms_year=2020,
        named_place="Busan New Port, Republic of Korea",
        payment_structure_id=payment.payment_structure_id,
        linked_transaction_ids=[transaction_id],
        reviewed_fields={
            **common_reviewed,
            "governing_law": "Republic of Korea",
            "dispute_resolution": "KCAB International arbitration in Seoul",
            "acceptance_period_days": 7,
            "buyer_unilateral_setoff_right": False,
            "buyer_unilateral_amendment_right": False,
        },
        source=_source("SRC-DOC-DEMO-CLEAN-CONTRACT"),
        record_status="verified",
    )
    invoice = TradeDocumentProfile(
        document_id="DOC-DEMO-CLEAN-INVOICE",
        evidence_id="EVID-DEMO-CLEAN-INVOICE",
        document_type="commercial_invoice",
        currency="USD",
        amount=Decimal("250000"),
        incoterms_rule="FCA",
        incoterms_year=2020,
        named_place="Busan New Port, Republic of Korea",
        linked_transaction_ids=[transaction_id],
        reviewed_fields=common_reviewed,
        source=_source("SRC-DOC-DEMO-CLEAN-INVOICE"),
        record_status="verified",
    )
    letter_of_credit = TradeDocumentProfile(
        document_id="DOC-DEMO-CLEAN-CREDIT",
        evidence_id="EVID-DEMO-CLEAN-CREDIT",
        document_type="letter_of_credit",
        currency="USD",
        amount=Decimal("250000"),
        expiry_date=date(2026, 12, 31),
        payment_structure_id=payment.payment_structure_id,
        linked_transaction_ids=[transaction_id],
        reviewed_fields={
            "latest_shipment_date": "2026-11-30",
            "presentation_period_days": 21,
            "buyer_controlled_document_requirements": [],
            "expiry_place": "Seoul, Republic of Korea",
            "availability_type": "sight",
            "tenor_days": None,
            "tenor_start_event": "unknown",
            "draft_required": False,
            "draft_tenor_text": None,
            "acceptance_party": None,
            "beneficiary_name": company.legal_name,
            "applicant_name": buyer.legal_name,
        },
        source=_source("SRC-DOC-DEMO-CLEAN-CREDIT"),
        record_status="verified",
    )
    case = UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-DEMO-REVIEWED-CLEAN",
            company_name=company.legal_name,
            analysis_as_of_date=date(2026, 7, 27),
        ),
        evidence=_approved_evidence(contract, invoice, letter_of_credit),
        approved_transactions=[
            {
                "transaction_id": transaction_id,
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 250000,
                "expected_date": "2026-11-30",
            }
        ],
        official_fx_reference=_fx_asset("1350"),
        trade_finance=TradeFinanceDomainState(
            company_profile=company,
            financial_statements=[statement],
            counterparties=[buyer],
            country_risk_facts=country_facts,
            compliance_screenings=screenings,
            payment_structures=[payment],
            trade_documents=[contract, invoice, letter_of_credit],
        ),
    )
    request = SingleTransactionAssessmentRequest(
        pipeline_id="PIPELINE-DEMO-CLEAN-001",
        brief_id="BRIEF-DEMO-CLEAN-001",
        transaction_id=transaction_id,
        counterparty_id=buyer.counterparty_id,
        country_code="SG",
        capacity_request=TransactionCapacityRequest(
            assessment_id="CAPACITY-DEMO-CLEAN-001",
            transaction_id=transaction_id,
            statement_id=statement.statement_id,
            payment_structure_id=payment.payment_structure_id,
            protection_percent=Decimal("100"),
            pre_shipment_funding_need_krw=Decimal("100000000"),
        ),
        product_profiles=[],
        max_ranked_concerns=5,
    )
    return _package(
        case=case,
        request=request,
        notes=[
            "Synthetic reviewed-clean showcase.",
            "No material screening flags is not an approval, low-risk certification, or compliance clearance.",
        ],
    )


_SCENARIOS: list[tuple[DemoScenarioMetadata, Callable[[], SingleTransactionAssessmentPackage]]] = [
    (
        DemoScenarioMetadata(
            scenario_id="missing_information",
            title="① 필수정보 부족",
            summary="결제구조·문서·재무감내 입력이 없어 추정하지 않고 보완 요청을 생성합니다.",
            expected_disposition="additional_information_required",
            source_modes=["synthetic_gold"],
            highlight="없는 정보를 만들어내지 않는 fail-closed 동작",
        ),
        _missing_information_package,
    ),
    (
        DemoScenarioMetadata(
            scenario_id="oa_high_risk",
            title="② O/A 90일 고위험 수출",
            summary="신규 바이어, 문서 통화·금액 불일치, 자금수요 초과와 상담 후보를 통합합니다.",
            expected_disposition="conditions_required_before_commitment",
            source_modes=["synthetic_gold", "synthetic_official_snapshot"],
            highlight="거래·문서·재무·상품을 연결한 메인 데모",
        ),
        _oa_high_risk_package,
    ),
    (
        DemoScenarioMetadata(
            scenario_id="complex_lc",
            title="③ 복합 Acceptance L/C",
            summary="유효기일 충돌, 제시기간 0일, 바이어 통제서류와 인수주체 누락을 점검합니다.",
            expected_disposition="specialist_clearance_required",
            source_modes=["synthetic_gold", "synthetic_official_snapshot"],
            highlight="Sight·Usance·Acceptance 및 L/C 조항 전문성",
        ),
        _complex_lc_package,
    ),
    (
        DemoScenarioMetadata(
            scenario_id="reviewed_clean",
            title="④ 검토완료 정상 근접 사례",
            summary="문서 정합성·바이어 실사·재무감내 Coverage가 갖춰진 비교 기준입니다.",
            expected_disposition="no_material_screening_flags",
            source_modes=["synthetic_gold", "synthetic_official_snapshot"],
            highlight="시스템이 무조건 경고만 생성하지 않음을 검증",
        ),
        _reviewed_clean_package,
    ),
]


def list_demo_scenarios() -> list[DemoScenarioMetadata]:
    """Return stable presentation metadata without building the scenario packages."""

    return [metadata for metadata, _ in _SCENARIOS]


def load_demo_scenario(scenario_id: str) -> SingleTransactionAssessmentPackage:
    """Build one deterministic demo package by ID."""

    for metadata, builder in _SCENARIOS:
        if metadata.scenario_id == scenario_id:
            return builder()
    raise KeyError(f"Unknown demo scenario: {scenario_id}")
