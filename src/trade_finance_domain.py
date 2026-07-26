"""Typed domain contracts for evidence-backed trade-finance assessments.

These models define the business objects that sit between raw source adapters and the
copilot's reasoning layer.  They deliberately separate facts, screening signals,
consultation candidates, and institution-specific decisions.  No model in this module
approves credit, confirms insurance acceptance, or represents a live bank quotation.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RecordStatus = Literal["verified", "partial", "unverified", "stale", "not_available"]
SourceTier = Literal["tier_1", "tier_2", "tier_3", "user_provided", "derived"]
SourceKind = Literal[
    "user_document",
    "official_api",
    "official_publication",
    "institution_product_disclosure",
    "derived_calculation",
    "project_rule",
    "other",
]
RiskSeverity = Literal["critical", "high", "medium", "low", "informational"]
AuthorityType = Literal[
    "fact",
    "calculation",
    "screening_flag",
    "inference",
    "institution_specific_decision",
]


class StrictDomainModel(BaseModel):
    """Shared strict configuration for externally auditable domain records."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceReference(StrictDomainModel):
    """Traceable origin metadata retained by every substantive domain record."""

    source_id: str
    source_name: str
    source_tier: SourceTier
    source_kind: SourceKind
    source_locator: str | None = None
    as_of_date: date | None = None
    retrieved_at: datetime | None = None
    content_hash: str | None = None
    effective_date_verified: bool = False


class EvidenceBackedRecord(StrictDomainModel):
    """Base record that makes provenance, status, and limitations mandatory."""

    source: SourceReference
    record_status: RecordStatus = "unverified"
    limitations: list[str] = Field(default_factory=list)


class CompanyProfile(EvidenceBackedRecord):
    company_id: str
    legal_name: str
    business_registration_number: str | None = None
    corporate_registration_number: str | None = None
    country_code: str = "KR"
    industry_code: str | None = None
    industry_name: str | None = None
    sme_status: Literal["confirmed", "self_declared", "unknown", "not_sme"] = "unknown"

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        value = value.upper()
        if len(value) != 2 or not value.isalpha():
            raise ValueError("country_code must be a two-letter ISO-style code")
        return value


class FinancialStatementSnapshot(EvidenceBackedRecord):
    """Normalized financial statement values used only for pre-screening."""

    statement_id: str
    company_id: str
    period_start: date | None = None
    period_end: date
    report_type: Literal["annual", "semiannual", "quarterly", "other"]
    consolidation_scope: Literal["consolidated", "separate", "unknown"] = "unknown"
    currency: str = "KRW"
    unit_multiplier: Decimal = Field(default=Decimal("1"), gt=0)
    cash_and_cash_equivalents: Decimal | None = Field(default=None, ge=0)
    short_term_financial_assets: Decimal | None = Field(default=None, ge=0)
    trade_receivables: Decimal | None = Field(default=None, ge=0)
    inventories: Decimal | None = Field(default=None, ge=0)
    current_assets: Decimal | None = Field(default=None, ge=0)
    current_liabilities: Decimal | None = Field(default=None, ge=0)
    short_term_borrowings: Decimal | None = Field(default=None, ge=0)
    current_portion_of_long_term_debt: Decimal | None = Field(default=None, ge=0)
    total_borrowings: Decimal | None = Field(default=None, ge=0)
    total_liabilities: Decimal | None = Field(default=None, ge=0)
    total_assets: Decimal | None = Field(default=None, ge=0)
    equity: Decimal | None = None
    revenue: Decimal | None = None
    operating_profit: Decimal | None = None
    operating_cash_flow: Decimal | None = None
    interest_expense: Decimal | None = Field(default=None, ge=0)
    original_account_names: dict[str, str] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("currency must be a three-letter code")
        return value

    @model_validator(mode="after")
    def period_is_chronological(self):
        if self.period_start and self.period_start > self.period_end:
            raise ValueError("period_start must not be after period_end")
        return self


class CounterpartyProfile(EvidenceBackedRecord):
    counterparty_id: str
    legal_name: str
    country_code: str
    registration_number: str | None = None
    address: str | None = None
    website: str | None = None
    relationship_status: Literal["new", "existing", "former", "unknown"] = "unknown"
    due_diligence_status: Literal[
        "not_started",
        "identity_only",
        "public_information_checked",
        "professional_credit_investigation_required",
        "professional_credit_investigation_completed",
    ] = "not_started"
    parent_or_guarantor: str | None = None
    prior_payment_history: Literal[
        "positive", "mixed", "adverse", "none", "unknown"
    ] = "unknown"

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        value = value.upper()
        if len(value) != 2 or not value.isalpha():
            raise ValueError("country_code must be a two-letter ISO-style code")
        return value


class CountryRiskFact(EvidenceBackedRecord):
    fact_id: str
    country_code: str
    dimension: Literal[
        "sovereign_transfer",
        "macroeconomic",
        "political",
        "sanctions_aml",
        "currency",
        "trade_operational",
        "recovery_enforcement",
    ]
    metric_name: str
    value: Decimal | str | bool
    unit: str | None = None
    observation_date: date | None = None
    risk_direction: Literal["higher_is_worse", "lower_is_worse", "categorical", "neutral"]
    interpretation: str
    benchmark_or_threshold: str | None = None

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        value = value.upper()
        if len(value) != 2 or not value.isalpha():
            raise ValueError("country_code must be a two-letter ISO-style code")
        return value


class ComplianceMatch(StrictDomainModel):
    matched_name: str
    list_name: str
    match_score: Decimal | None = Field(default=None, ge=0, le=1)
    identifiers: dict[str, str] = Field(default_factory=dict)
    source_entry_locator: str | None = None


class ComplianceScreeningResult(EvidenceBackedRecord):
    screening_id: str
    subject_type: Literal["company", "counterparty", "bank", "vessel", "person", "country"]
    subject_id: str | None = None
    subject_name: str
    screening_type: Literal["sanctions", "aml_country", "export_control", "restricted_party"]
    result: Literal["clear", "potential_match", "confirmed_match", "not_screened"]
    method: Literal["exact", "configured_fuzzy", "manual", "not_applicable"]
    matched_entries: list[ComplianceMatch] = Field(default_factory=list)
    reviewed_by_human: bool = False

    @model_validator(mode="after")
    def matches_require_entries(self):
        if self.result in {"potential_match", "confirmed_match"} and not self.matched_entries:
            raise ValueError("A compliance match must include at least one matched entry")
        if self.result == "confirmed_match" and not self.reviewed_by_human:
            raise ValueError("A confirmed compliance match requires human review")
        return self


class PaymentStructure(EvidenceBackedRecord):
    payment_structure_id: str
    transaction_id: str
    method: Literal[
        "advance_payment",
        "open_account",
        "documentary_collection_dp",
        "documentary_collection_da",
        "letter_of_credit",
        "standby_letter_of_credit",
        "other",
    ]
    tenor_days: int | None = Field(default=None, ge=0)
    advance_payment_percent: Decimal | None = Field(default=None, ge=0, le=100)
    deferred_payment_percent: Decimal | None = Field(default=None, ge=0, le=100)
    issuing_bank: str | None = None
    confirming_bank: str | None = None
    irrevocable: bool | None = None
    confirmed: bool | None = None
    payment_trigger: str | None = None
    governing_rules: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def percentages_do_not_exceed_total(self):
        advance = self.advance_payment_percent or Decimal("0")
        deferred = self.deferred_payment_percent or Decimal("0")
        if advance + deferred > Decimal("100"):
            raise ValueError("Payment percentages must not exceed 100")
        return self


class TradeDocumentProfile(EvidenceBackedRecord):
    document_id: str
    evidence_id: str
    document_type: Literal[
        "contract",
        "purchase_order",
        "commercial_invoice",
        "letter_of_credit",
        "packing_list",
        "bill_of_lading",
        "insurance_document",
        "inspection_certificate",
        "certificate_of_origin",
        "other",
    ]
    document_reference: str | None = None
    issuer_name: str | None = None
    party_names: list[str] = Field(default_factory=list)
    currency: str | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    issue_date: date | None = None
    shipment_date: date | None = None
    expiry_date: date | None = None
    incoterms_rule: str | None = None
    incoterms_year: int | None = Field(default=None, ge=1900, le=2100)
    named_place: str | None = None
    payment_structure_id: str | None = None
    linked_transaction_ids: list[str] = Field(default_factory=list)
    reviewed_fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def normalize_optional_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("currency must be a three-letter code")
        return value


class ContractClauseFinding(EvidenceBackedRecord):
    clause_finding_id: str
    document_id: str
    evidence_ids: list[str]
    clause_locator: str
    clause_excerpt: str
    issue_type: Literal[
        "missing_term",
        "ambiguous_term",
        "buyer_controlled_condition",
        "timing_conflict",
        "document_discrepancy_risk",
        "incoterms_mismatch",
        "payment_risk",
        "broad_liability",
        "unilateral_right",
        "governing_law_or_dispute",
        "sanctions_or_export_control",
        "other",
    ]
    severity: RiskSeverity
    failure_path: str
    suggested_clarification_or_revision: str
    specialist_review: list[
        Literal["legal", "bank", "insurer", "logistics", "customs", "none"]
    ] = Field(default_factory=list)

    @field_validator("evidence_ids")
    @classmethod
    def evidence_is_required(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("A clause finding must reference evidence")
        return value


class MaterialityMeasure(StrictDomainModel):
    metric_name: str
    value: Decimal
    unit: str
    comparator: str | None = None
    threshold: Decimal | None = None
    calculation_id: str | None = None


class TradeRiskSignal(EvidenceBackedRecord):
    signal_id: str
    category: Literal[
        "counterparty",
        "country_transfer",
        "payment_instrument",
        "contract_document",
        "company_capacity",
        "liquidity",
        "concentration",
        "foreign_exchange",
        "compliance",
        "operational",
    ]
    severity: RiskSeverity
    title: str
    factual_trigger: str
    authority_type: Literal["screening_flag", "inference"] = "screening_flag"
    affected_transaction_ids: list[str] = Field(default_factory=list)
    affected_document_ids: list[str] = Field(default_factory=list)
    materiality: list[MaterialityMeasure] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)
    country_fact_ids: list[str] = Field(default_factory=list)
    clause_finding_ids: list[str] = Field(default_factory=list)
    mitigating_facts: list[str] = Field(default_factory=list)
    unresolved_facts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def material_signal_requires_grounding(self):
        references = (
            self.evidence_ids
            + self.calculation_ids
            + self.country_fact_ids
            + self.clause_finding_ids
        )
        if self.severity != "informational" and not references:
            raise ValueError("A material trade-risk signal must reference evidence or calculations")
        return self


class MitigationOption(EvidenceBackedRecord):
    option_id: str
    title: str
    risk_categories_addressed: list[str]
    transaction_stage: Literal[
        "pre_contract",
        "pre_shipment",
        "post_shipment",
        "pre_payment",
        "ongoing",
    ]
    mechanism: str
    residual_risks: list[str] = Field(default_factory=list)
    verified_public_conditions: list[str] = Field(default_factory=list)
    unresolved_conditions: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    official_source_ids: list[str] = Field(default_factory=list)
    operational_next_step: str


class ProductCandidate(EvidenceBackedRecord):
    """A consultation candidate, never an eligibility or approval decision."""

    product_candidate_id: str
    provider: str
    product_or_service_name: str
    product_category: Literal[
        "buyer_credit_investigation",
        "trade_credit_insurance",
        "export_guarantee_pre_shipment",
        "export_guarantee_post_shipment",
        "receivables_financing",
        "working_capital",
        "import_finance",
        "foreign_exchange_hedging",
        "other",
    ]
    matched_need: str
    candidate_status: Literal[
        "consultation_candidate", "insufficient_information", "not_applicable", "blocked"
    ]
    match_reasons: list[str] = Field(default_factory=list)
    verified_public_conditions: list[str] = Field(default_factory=list)
    unresolved_eligibility_conditions: list[str] = Field(default_factory=list)
    disqualifying_conditions: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    official_source_ids: list[str] = Field(default_factory=list)
    source_effective_date: date | None = None
    next_action: str

    @model_validator(mode="after")
    def usable_candidate_requires_public_source(self):
        if self.candidate_status == "consultation_candidate" and not self.official_source_ids:
            raise ValueError("A consultation candidate must cite an official source")
        return self


class ConsultationRequirement(EvidenceBackedRecord):
    requirement_id: str
    consultation_route: Literal[
        "bank_relationship_manager",
        "trade_finance_specialist",
        "foreign_exchange_specialist",
        "ksure",
        "legal",
        "customs",
        "logistics",
        "other",
    ]
    purpose: str
    questions_to_confirm: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    blocked_by_missing_inputs: list[str] = Field(default_factory=list)


class ActionPlanItem(EvidenceBackedRecord):
    action_id: str
    sequence: int = Field(ge=1)
    title: str
    rationale: str
    responsible_party: Literal[
        "customer",
        "bank",
        "ksure",
        "buyer",
        "seller",
        "legal_counsel",
        "logistics_provider",
        "other",
    ]
    dependency_action_ids: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    supporting_risk_signal_ids: list[str] = Field(default_factory=list)
    status: Literal["proposed", "ready", "blocked", "completed", "rejected"] = "proposed"

    @model_validator(mode="after")
    def action_cannot_depend_on_itself(self):
        if self.action_id in self.dependency_action_ids:
            raise ValueError("An action cannot depend on itself")
        return self


class TradeFinanceDomainState(StrictDomainModel):
    """Typed domain state ready to be attached to the unified audit case."""

    company_profile: CompanyProfile | None = None
    financial_statements: list[FinancialStatementSnapshot] = Field(default_factory=list)
    counterparties: list[CounterpartyProfile] = Field(default_factory=list)
    country_risk_facts: list[CountryRiskFact] = Field(default_factory=list)
    compliance_screenings: list[ComplianceScreeningResult] = Field(default_factory=list)
    payment_structures: list[PaymentStructure] = Field(default_factory=list)
    trade_documents: list[TradeDocumentProfile] = Field(default_factory=list)
    clause_findings: list[ContractClauseFinding] = Field(default_factory=list)
    risk_signals: list[TradeRiskSignal] = Field(default_factory=list)
    mitigation_options: list[MitigationOption] = Field(default_factory=list)
    product_candidates: list[ProductCandidate] = Field(default_factory=list)
    consultation_requirements: list[ConsultationRequirement] = Field(default_factory=list)
    action_plan: list[ActionPlanItem] = Field(default_factory=list)
    domain_version: str = "trade-finance-domain/1.0"

    @model_validator(mode="after")
    def record_identifiers_and_action_sequences_are_unique(self):
        collections = {
            "statement_id": (self.financial_statements, "statement_id"),
            "counterparty_id": (self.counterparties, "counterparty_id"),
            "fact_id": (self.country_risk_facts, "fact_id"),
            "screening_id": (self.compliance_screenings, "screening_id"),
            "payment_structure_id": (self.payment_structures, "payment_structure_id"),
            "document_id": (self.trade_documents, "document_id"),
            "clause_finding_id": (self.clause_findings, "clause_finding_id"),
            "signal_id": (self.risk_signals, "signal_id"),
            "option_id": (self.mitigation_options, "option_id"),
            "product_candidate_id": (self.product_candidates, "product_candidate_id"),
            "requirement_id": (self.consultation_requirements, "requirement_id"),
            "action_id": (self.action_plan, "action_id"),
        }
        for label, (records, attribute) in collections.items():
            identifiers = [getattr(record, attribute) for record in records]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"Duplicate {label} values are not allowed")

        sequences = [item.sequence for item in self.action_plan]
        if len(sequences) != len(set(sequences)):
            raise ValueError("Action-plan sequence values must be unique")
        return self

    def record_counts(self) -> dict[str, int]:
        return {
            "financial_statements": len(self.financial_statements),
            "counterparties": len(self.counterparties),
            "country_risk_facts": len(self.country_risk_facts),
            "compliance_screenings": len(self.compliance_screenings),
            "payment_structures": len(self.payment_structures),
            "trade_documents": len(self.trade_documents),
            "clause_findings": len(self.clause_findings),
            "risk_signals": len(self.risk_signals),
            "mitigation_options": len(self.mitigation_options),
            "product_candidates": len(self.product_candidates),
            "consultation_requirements": len(self.consultation_requirements),
            "action_plan": len(self.action_plan),
        }
