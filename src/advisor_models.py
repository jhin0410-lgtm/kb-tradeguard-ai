"""Structured intent, tool-result, and advisory-answer contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .citation_models import CalculationCitation, DocumentCitation

AdvisorIntent = Literal[
    "portfolio_summary",
    "fx_exposure",
    "cashflow_risk",
    "settlement_delay",
    "natural_hedge",
    "maturity_mismatch",
    "hedge_comparison",
    "forward_rate_explanation",
    "import_funding",
    "document_provenance",
    "policy_information",
    "bank_consultation_preparation",
    "unsupported_or_sensitive_request",
]


class IntentClassification(BaseModel):
    primary_intent: AdvisorIntent
    required_tools: list[str]
    extracted_parameters: dict[str, Any] = Field(default_factory=dict)
    parameter_sources: dict[str, str] = Field(default_factory=dict)
    missing_parameters: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    clarification_required: bool = False


class CalculationResult(BaseModel):
    calculation_name: str
    input_assumptions: dict[str, Any]
    result: Any
    unit: str
    as_of_date: str | None
    data_source: str
    limitations: list[str]
    calculation_id: str
    calculation_engine_version: str
    normalized_input_hash: str
    calculation_timestamp: str
    source_data_identifiers: list[str]
    selected_analysis_basis: str

    @property
    def citation(self) -> CalculationCitation:
        return CalculationCitation(
            calculation_id=self.calculation_id,
            calculation_name=self.calculation_name,
        )


class NumericalClaim(BaseModel):
    description: str
    value: float
    unit: str
    calculation_id: str
    analysis_basis: str
    as_of_date: str | None = None


class AdvisoryAnswer(BaseModel):
    provider_mode: str
    intent: IntentClassification
    direct_answer: str
    key_findings: list[str] = Field(default_factory=list)
    calculations_used: list[CalculationCitation] = Field(default_factory=list)
    documents_used: list[DocumentCitation] = Field(default_factory=list)
    numerical_claims: list[NumericalClaim] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    considerations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    follow_up_question: str | None = None
    risk_notice: str
