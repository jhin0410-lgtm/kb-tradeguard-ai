"""Grounding validator for numerical, policy, and prohibited advisory claims."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .advisor_guardrails import detect_prohibited_wording
from .advisor_models import AdvisoryAnswer, CalculationResult

CALCULATION_ID_PATTERN = re.compile(r"\bCALC-[A-Z0-9-]+\b")
DOCUMENT_CITATION_PATTERN = re.compile(r"\[[A-Z0-9-]+,\s*[^,\]]+,\s*[^\]]+\]")
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9-])[-+]?\d[\d,]*(?:\.\d+)?%?")
POLICY_KEYWORDS = (
    "보험",
    "보증",
    "대출",
    "금융",
    "financing",
    "insurance",
    "guarantee",
    "required document",
    "필요 서류",
)
REFUSAL_MARKERS = (
    "제공하지 않습니다",
    "지원할 수 없습니다",
    "아닙니다",
    "not provide",
    "cannot provide",
    "is not",
    "are not",
)


class AnswerValidationReport(BaseModel):
    numerical_claims_detected: list[str] = Field(default_factory=list)
    calculation_references_found: list[str] = Field(default_factory=list)
    policy_claims_detected: list[str] = Field(default_factory=list)
    document_references_found: list[str] = Field(default_factory=list)
    prohibited_wording_detected: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    validation_result: bool


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text)
        if sentence.strip()
    ]


def _is_negated(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def _numeric_values(value) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [
            number
            for item in value.values()
            for number in _numeric_values(item)
        ]
    if isinstance(value, (list, tuple)):
        return [number for item in value for number in _numeric_values(item)]
    return []


def validate_advisory_answer(
    answer: AdvisoryAnswer,
    available_calculations: list[CalculationResult] | None = None,
) -> AnswerValidationReport:
    """Fail closed when advisory claims lack grounding or cross scope boundaries."""
    text_parts = [
        answer.direct_answer,
        *answer.key_findings,
        *answer.assumptions,
        *answer.considerations,
        *answer.limitations,
    ]
    text = "\n".join(text_parts)
    sentences = _sentences(text)
    numerical_sentences = [
        sentence for sentence in sentences if NUMBER_PATTERN.search(sentence)
    ]
    calculation_refs = sorted(set(CALCULATION_ID_PATTERN.findall(text)))
    document_refs = sorted(set(DOCUMENT_CITATION_PATTERN.findall(text)))
    policy_sentences = [
        statement
        for statement in text_parts
        if any(keyword.lower() in statement.lower() for keyword in POLICY_KEYWORDS)
        and not _is_negated(statement)
    ]
    prohibited = sorted(
        {
            category
            for sentence in sentences
            if not _is_negated(sentence)
            for category in detect_prohibited_wording(sentence)
        }
    )

    errors: list[str] = []
    declared_calc_ids = {
        citation.calculation_id for citation in answer.calculations_used
    }
    available_by_id = {
        calculation.calculation_id: calculation
        for calculation in (available_calculations or [])
    }
    for reference in calculation_refs:
        if reference not in declared_calc_ids:
            errors.append(
                f"Calculation reference is not declared by the answer: {reference}"
            )
    if available_calculations is not None:
        for reference in declared_calc_ids:
            if reference not in available_by_id:
                errors.append(
                    f"Calculation reference is unrelated to tool output: {reference}"
                )
    for claim in answer.numerical_claims:
        if claim.calculation_id not in declared_calc_ids:
            errors.append(
                f"Numerical claim lacks declared calculation citation: {claim.description}"
            )
            continue
        if available_calculations is not None:
            calculation = available_by_id.get(claim.calculation_id)
            if calculation is None:
                errors.append(
                    f"Numerical claim cites unrelated calculation: {claim.description}"
                )
                continue
            allowed_values = _numeric_values(calculation.result)
            allowed_values.extend(_numeric_values(calculation.input_assumptions))
            if not any(
                abs(float(claim.value) - value)
                <= 1e-9 * max(1.0, abs(value))
                for value in allowed_values
            ):
                errors.append(
                    f"Numerical claim value is absent from cited tool output: "
                    f"{claim.description}"
                )
    for sentence in numerical_sentences:
        if not (
            CALCULATION_ID_PATTERN.search(sentence)
            or DOCUMENT_CITATION_PATTERN.search(sentence)
        ):
            errors.append(f"Uncited numerical claim: {sentence}")
    if policy_sentences and not answer.documents_used:
        errors.append("Policy-related claim lacks bundled document citation")
    for sentence in policy_sentences:
        if not DOCUMENT_CITATION_PATTERN.search(sentence):
            errors.append(f"Policy-related statement lacks inline citation: {sentence}")

    selected_basis = answer.intent.extracted_parameters.get("analysis_basis")
    selected_view = answer.intent.extracted_parameters.get("cash_flow_view")
    for claim in answer.numerical_claims:
        claim_basis = claim.analysis_basis.lower()
        if selected_basis and claim.analysis_basis != selected_basis:
            errors.append(
                "Numerical claim contradicts selected hedge basis: "
                f"{claim.description}"
            )
        if selected_view and selected_view.lower() not in claim_basis:
            errors.append(
                "Numerical claim contradicts selected cash-flow view: "
                f"{claim.description}"
            )

    affirmative_quote_claim = any(
        not _is_negated(sentence)
        and bool(
            re.search(
                r"\b(?:is|are)\s+(?:an?\s+)?(?:actual\s+KB|executable)\s+quote\b"
                r"|(?:은|는|이|가)\s*(?:실제\s*KB|실행\s*가능한)\s*견적",
                sentence,
                flags=re.IGNORECASE,
            )
        )
        for sentence in sentences
    )
    if affirmative_quote_claim:
        errors.append("Theoretical forward rate is described as an executable quote")
    if prohibited:
        errors.append("Prohibited wording detected: " + ", ".join(prohibited))

    return AnswerValidationReport(
        numerical_claims_detected=numerical_sentences,
        calculation_references_found=calculation_refs,
        policy_claims_detected=policy_sentences,
        document_references_found=document_refs,
        prohibited_wording_detected=prohibited,
        errors=errors,
        validation_result=not errors,
    )
