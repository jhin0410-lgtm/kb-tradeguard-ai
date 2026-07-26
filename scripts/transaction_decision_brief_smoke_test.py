"""Synthetic end-to-end smoke test for the transaction decision brief.

Usage:
    python scripts/transaction_decision_brief_smoke_test.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.advisor_tools import _calculation_result  # noqa: E402
from src.copilot_case import CaseEvidenceItem, CaseIdentity, UnifiedCopilotCase  # noqa: E402
from src.intelligence import (  # noqa: E402
    TradeFinanceNeedProfile,
    TransactionDecisionBriefRequest,
    build_transaction_decision_brief,
    match_trade_finance_products,
)
from src.trade_finance_domain import (  # noqa: E402
    ComplianceScreeningResult,
    CounterpartyProfile,
    CountryRiskFact,
    PaymentStructure,
    SourceReference,
    TradeDocumentProfile,
    TradeFinanceDomainState,
    TradeRiskSignal,
)


def _source(source_id: str, kind: str, tier: str) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_name=f"Synthetic source {source_id}",
        source_tier=tier,
        source_kind=kind,
        source_locator=f"fixture://{source_id}",
        as_of_date=date(2026, 7, 26),
        effective_date_verified=True,
    )


def main() -> int:
    counterparty = CounterpartyProfile(
        counterparty_id="BUYER-VN-001",
        legal_name="Vietnam Buyer Co., Ltd.",
        country_code="VN",
        registration_number="VN-REG-001",
        relationship_status="new",
        due_diligence_status="professional_credit_investigation_required",
        prior_payment_history="none",
        source=_source("SRC-BUYER", "user_document", "user_provided"),
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
            interpretation="AML/CFT context flag, not a transaction prohibition.",
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
            source=_source("SRC-UN-SCREEN", "official_publication", "tier_1"),
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
        payment_trigger="90 days after buyer acceptance",
        source=_source("SRC-PAY", "user_document", "user_provided"),
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
        source=_source("SRC-CONTRACT", "user_document", "user_provided"),
        record_status="verified",
    )
    capacity_calculation = _calculation_result(
        "Transaction financial capacity assessment",
        {
            "transaction_id": "EXP-001",
            "statement_id": "FS-2025-CFS",
            "analysis_basis": "gross transaction scale and explicit residual exposure",
        },
        {
            "metrics": {
                "gross_transaction_krw": 675000000,
                "funding_need_to_liquid_assets_pct": 112.5,
            }
        },
        "mixed KRW and percent",
        "2026-07-26",
        "synthetic approved transaction and financial statement",
        ["Synthetic smoke-test calculation."],
    )
    risk_signals = [
        TradeRiskSignal(
            signal_id="RISK-DOC-EXP-001",
            category="contract_document",
            severity="high",
            title="바이어 승인 지급조건 보완 필요",
            factual_trigger="payment depends on buyer acceptance without a reviewed period",
            affected_transaction_ids=["EXP-001"],
            affected_document_ids=[contract.document_id],
            evidence_ids=[contract.evidence_id],
            unresolved_facts=["검수기간, 객관적 기준과 간주승인 조건 확인"],
            source=_source("SRC-DOC-RULE", "project_rule", "derived"),
            record_status="verified",
        ),
        TradeRiskSignal(
            signal_id="RISK-CAPACITY-EXP-001",
            category="liquidity",
            severity="high",
            title="거래 준비자금이 식별 유동성을 초과함",
            factual_trigger="funding_need_to_liquid_assets_pct=112.50% > 100%",
            affected_transaction_ids=["EXP-001"],
            calculation_ids=[capacity_calculation.calculation_id],
            unresolved_facts=["가용한도, 담보·보증과 다른 현금유출 확인"],
            source=_source("SRC-CAPACITY-RULE", "project_rule", "derived"),
            record_status="verified",
        ),
    ]
    profile = TradeFinanceNeedProfile(
        profile_id="NEED-VIETNAM-EXPORT-001",
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
    product_result = match_trade_finance_products([profile])
    case = UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-DECISION-BRIEF-SMOKE",
            company_name="Example Exporter Co., Ltd.",
            analysis_as_of_date=date.today(),
        ),
        evidence=[
            CaseEvidenceItem(
                evidence_id=contract.evidence_id,
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
        calculations={capacity_calculation.calculation_id: capacity_calculation},
        trade_finance=TradeFinanceDomainState(
            counterparties=[counterparty],
            country_risk_facts=country_facts,
            compliance_screenings=screenings,
            payment_structures=[payment],
            trade_documents=[contract],
            risk_signals=risk_signals,
            product_candidates=product_result.product_candidates,
            consultation_requirements=product_result.consultation_requirements,
        ),
    )
    request = TransactionDecisionBriefRequest(
        brief_id="BRIEF-EXP-001",
        transaction_id="EXP-001",
        counterparty_id=counterparty.counterparty_id,
        country_code="VN",
        product_candidate_ids=[
            item.product_candidate_id
            for item in product_result.product_candidates
            if item.candidate_status in {"consultation_candidate", "insufficient_information"}
        ],
        consultation_requirement_ids=[
            item.requirement_id for item in product_result.consultation_requirements
        ],
    )
    brief = build_transaction_decision_brief(case, request)
    output = {
        "status": "ok",
        "authority_boundary": brief.authority_boundary,
        "brief_id": brief.brief_id,
        "transaction_id": brief.transaction_id,
        "disposition": brief.disposition,
        "disposition_rationale": brief.disposition_rationale,
        "ranked_concerns": [item.model_dump(mode="json") for item in brief.ranked_concerns],
        "missing_information": brief.missing_information,
        "product_candidate_ids": brief.product_candidate_ids,
        "action_plan": [item.model_dump(mode="json") for item in brief.action_plan],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
