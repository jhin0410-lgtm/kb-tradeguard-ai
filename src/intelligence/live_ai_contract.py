"""Provider-neutral contract for optional grounded live-AI explanations.

Live AI is deliberately downstream of deterministic assessment. It may explain,
prioritize questions, or summarize cited records, but it cannot create authoritative
financial calculations, alter findings, approve transactions, clear compliance, or
invent missing evidence.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..copilot_case import UnifiedCopilotCase
from .single_transaction_pipeline import SingleTransactionAssessmentResult

LiveAiMode = Literal[
    "explain_brief",
    "prepare_consultation",
    "evidence_lookup",
    "compare_reviewed_options",
]

_REFERENCE_PATTERN = re.compile(r"\[REF:([^\]\s]+)\]")
_SENTENCE_PATTERN = re.compile(
    r".+?(?:[.!?。！？](?:\s*\[REF:[^\]\s]+\])*(?=\s+|$)|$)",
    flags=re.DOTALL,
)


class GroundedLiveAiRequest(BaseModel):
    """Immutable grounding packet passed to an optional model provider."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str
    case_hash: str
    brief_id: str
    mode: LiveAiMode
    user_question: str
    allowed_reference_ids: list[str]
    deterministic_context: dict[str, Any]
    authority_boundary: str = (
        "Explanation only. Deterministic calculations and governed screening records "
        "remain authoritative. The model must not approve or reject a transaction, "
        "provide legal advice, clear sanctions or AML obligations, determine bank or "
        "K-SURE acceptance, quote executable terms, or infer missing evidence."
    )

    @field_validator("case_hash")
    @classmethod
    def case_hash_is_sha256(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError("case_hash must be a lowercase SHA-256 digest")
        return normalized

    @model_validator(mode="after")
    def grounding_is_nonempty_and_unique(self):
        if not self.user_question:
            raise ValueError("user_question must not be empty")
        if not self.allowed_reference_ids:
            raise ValueError("Live AI requires at least one allowed reference ID")
        if len(self.allowed_reference_ids) != len(set(self.allowed_reference_ids)):
            raise ValueError("allowed_reference_ids must be unique")
        reference_records = self.deterministic_context.get("reference_records")
        if not isinstance(reference_records, dict):
            raise ValueError("Live AI deterministic context must include reference_records")
        missing = [
            identifier
            for identifier in self.allowed_reference_ids
            if identifier not in reference_records
        ]
        if missing:
            raise ValueError(
                "Every allowed Live AI reference must have a complete deterministic record: "
                + ", ".join(missing)
            )
        return self


class GroundedLiveAiResponse(BaseModel):
    """One provider response before it is accepted for display."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str
    answer_markdown: str
    cited_reference_ids: list[str]
    provider_name: str
    model_name: str
    generated_at: datetime
    decision_status: Literal["explanation_only"] = "explanation_only"
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def response_contract_is_complete(self):
        if not self.answer_markdown:
            raise ValueError("answer_markdown must not be empty")
        if len(self.cited_reference_ids) != len(set(self.cited_reference_ids)):
            raise ValueError("cited_reference_ids must be unique")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return self


class GroundedLiveAiValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    parsed_reference_ids: list[str] = Field(default_factory=list)
    unknown_reference_ids: list[str] = Field(default_factory=list)
    missing_declared_citations: list[str] = Field(default_factory=list)
    undeclared_inline_citations: list[str] = Field(default_factory=list)
    uncited_segments: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def _record_reference_ids(record: dict[str, Any], candidates: set[str]) -> list[str]:
    identifiers: list[str] = []
    for key, value in record.items():
        if not isinstance(value, (str, int)):
            continue
        key_text = str(key)
        value_text = str(value)
        if value_text not in candidates:
            continue
        if key_text.endswith("_id") or key_text in {
            "source_id",
            "calculation_id",
            "finding_id",
            "signal_id",
            "action_id",
        }:
            identifiers.append(value_text)
    return identifiers


def _index_reference_records(payload: Any, candidates: set[str]) -> dict[str, Any]:
    records: dict[str, Any] = {}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key)
                if key_text in candidates and isinstance(child, dict):
                    records.setdefault(key_text, child)
            for identifier in _record_reference_ids(value, candidates):
                records.setdefault(identifier, value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return records


def _uncited_substantive_segments(answer_markdown: str) -> list[str]:
    uncited: list[str] = []
    in_code_fence = False
    for raw_line in answer_markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence or not line:
            continue
        if line.startswith("#"):
            continue
        normalized = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s*)", "", line)
        for match in _SENTENCE_PATTERN.finditer(normalized):
            segment = match.group(0).strip()
            if not segment:
                continue
            visible = _REFERENCE_PATTERN.sub("", segment)
            visible = re.sub(r"[*_`|:]", "", visible).strip()
            if not re.search(r"[A-Za-z0-9가-힣]", visible):
                continue
            if not _REFERENCE_PATTERN.search(segment):
                uncited.append(segment)
    return uncited


def build_live_ai_grounding_packet(
    case: UnifiedCopilotCase,
    result: SingleTransactionAssessmentResult,
    *,
    request_id: str,
    mode: LiveAiMode,
    user_question: str,
) -> GroundedLiveAiRequest:
    """Build a bounded context packet from an already completed assessment."""

    if case.case_hash != result.case_after_hash:
        raise ValueError("Live AI case hash does not match assessment output")

    brief = result.brief
    candidate_reference_ids: list[str] = []
    candidate_reference_ids.extend(brief.country_fact_ids)
    candidate_reference_ids.extend(brief.compliance_screening_ids)
    candidate_reference_ids.extend(brief.calculation_ids)
    candidate_reference_ids.extend(brief.product_candidate_ids)
    candidate_reference_ids.extend(brief.consultation_requirement_ids)
    candidate_reference_ids.append(brief.source.source_id)
    for concern in brief.ranked_concerns:
        candidate_reference_ids.extend(concern.source_ids)
    for trace in result.stage_traces:
        candidate_reference_ids.extend(trace.generated_record_ids)
    for action in brief.action_plan:
        candidate_reference_ids.append(action.action_id)
        candidate_reference_ids.extend(action.supporting_risk_signal_ids)
    candidate_reference_ids = list(
        dict.fromkeys(identifier for identifier in candidate_reference_ids if identifier)
    )

    transaction = next(
        item
        for item in case.approved_transactions
        if str(item.get("transaction_id")) == result.transaction_id
    )
    searchable_payload = {
        "case": case.model_dump(mode="json"),
        "assessment_result": result.model_dump(mode="json"),
    }
    reference_records = _index_reference_records(
        searchable_payload,
        set(candidate_reference_ids),
    )
    reference_ids = [
        identifier
        for identifier in candidate_reference_ids
        if identifier in reference_records
    ]
    context = {
        "transaction": transaction,
        "brief": brief.model_dump(mode="json"),
        "stage_traces": [item.model_dump(mode="json") for item in result.stage_traces],
        "finding_reviews": [item.model_dump(mode="json") for item in case.finding_reviews],
        "reference_records": reference_records,
        "omitted_unresolved_reference_ids": [
            identifier
            for identifier in candidate_reference_ids
            if identifier not in reference_records
        ],
        "case_limitations": result.limitations,
    }
    return GroundedLiveAiRequest(
        request_id=request_id,
        case_hash=case.case_hash,
        brief_id=brief.brief_id,
        mode=mode,
        user_question=user_question,
        allowed_reference_ids=reference_ids,
        deterministic_context=context,
    )


def validate_grounded_live_ai_response(
    request: GroundedLiveAiRequest,
    response: GroundedLiveAiResponse,
) -> GroundedLiveAiValidation:
    """Reject provider output containing uncited, undeclared, or unknown references."""

    errors: list[str] = []
    if response.request_id != request.request_id:
        errors.append("Response request_id does not match the grounding request")

    parsed = list(dict.fromkeys(_REFERENCE_PATTERN.findall(response.answer_markdown)))
    allowed = set(request.allowed_reference_ids)
    declared = set(response.cited_reference_ids)
    parsed_set = set(parsed)
    unknown = sorted((declared | parsed_set) - allowed)
    missing_declared = sorted(declared - parsed_set)
    undeclared_inline = sorted(parsed_set - declared)
    uncited_segments = _uncited_substantive_segments(response.answer_markdown)

    if not parsed:
        errors.append("Live AI answer must include at least one inline [REF:<id>] citation")
    if unknown:
        errors.append("Live AI answer cites references outside the grounding packet")
    if missing_declared:
        errors.append("Declared citations are missing from inline answer markers")
    if undeclared_inline:
        errors.append("Inline citations are missing from cited_reference_ids")
    if uncited_segments:
        errors.append("Every substantive Live AI sentence or list item must include an inline citation")
    if not response.limitations:
        errors.append("Live AI response must preserve at least one limitation")

    return GroundedLiveAiValidation(
        accepted=not errors,
        parsed_reference_ids=parsed,
        unknown_reference_ids=unknown,
        missing_declared_citations=missing_declared,
        undeclared_inline_citations=undeclared_inline,
        uncited_segments=uncited_segments,
        errors=errors,
    )
