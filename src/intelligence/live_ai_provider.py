"""Optional provider integration for grounded live-AI explanations.

The provider is strictly downstream of the deterministic assessment pipeline. It receives
one bounded ``GroundedLiveAiRequest``, returns a typed explanation payload, and never
updates the case, calculations, findings, disposition, or consultation candidates.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .live_ai_contract import (
    GroundedLiveAiRequest,
    GroundedLiveAiResponse,
    GroundedLiveAiValidation,
    validate_grounded_live_ai_response,
)

_JSON_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


class LiveAiProviderError(RuntimeError):
    """Raised when a provider call cannot produce a reviewable typed response."""


class OpenAiLiveAiSettings(BaseModel):
    """Environment-backed OpenAI Responses API settings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    model_name: str = Field(default="gpt-5-mini", min_length=1)
    timeout_seconds: float = Field(default=45.0, gt=0, le=180)
    max_output_tokens: int = Field(default=1400, ge=200, le=5000)

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "OpenAiLiveAiSettings":
        env = environment if environment is not None else os.environ
        return cls(
            model_name=env.get("OPENAI_MODEL", "gpt-5-mini"),
            timeout_seconds=float(env.get("OPENAI_LIVE_AI_TIMEOUT_SECONDS", "45")),
            max_output_tokens=int(env.get("OPENAI_LIVE_AI_MAX_OUTPUT_TOKENS", "1400")),
        )


class GroundedLiveAiProviderPayload(BaseModel):
    """Strict provider-generated fields before audit metadata is attached locally."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    answer_markdown: str
    cited_reference_ids: list[str]
    limitations: list[str]

    @field_validator("answer_markdown")
    @classmethod
    def answer_is_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("answer_markdown must not be empty")
        return value

    @field_validator("cited_reference_ids", "limitations")
    @classmethod
    def lists_are_nonempty_and_unique(cls, value: list[str], info):
        if not value:
            raise ValueError(f"{info.field_name} must not be empty")
        if len(value) != len(set(value)):
            raise ValueError(f"{info.field_name} must contain unique values")
        return value


class GroundedLiveAiExecution(BaseModel):
    """One provider response together with the local grounding validation result."""

    model_config = ConfigDict(extra="forbid")

    request: GroundedLiveAiRequest
    response: GroundedLiveAiResponse
    validation: GroundedLiveAiValidation
    provider_request_id: str | None = None


_MODE_GUIDANCE = {
    "explain_brief": "Explain why the deterministic brief reached its disposition and summarize the cited concerns.",
    "prepare_consultation": "Prepare a concise bank or K-SURE consultation checklist using only cited actions and missing inputs.",
    "evidence_lookup": "Answer the question by locating and explaining only the cited deterministic records.",
    "compare_reviewed_options": "Compare only options already present in the deterministic context. Do not create alternatives or recommendations beyond the reviewed records.",
}


def openai_live_ai_is_configured(
    environment: Mapping[str, str] | None = None,
) -> bool:
    env = environment if environment is not None else os.environ
    return bool(env.get("OPENAI_API_KEY", "").strip())


def _provider_instructions(request: GroundedLiveAiRequest) -> str:
    allowed = ", ".join(request.allowed_reference_ids)
    return (
        "You are the optional explanation layer of KB TradeGuard AI. "
        "The deterministic assessment records supplied by the application are authoritative. "
        "Do not calculate new financial values, change findings, infer missing evidence, approve or reject a transaction, "
        "give legal advice, clear sanctions or AML obligations, predict bank or K-SURE acceptance, or quote executable terms. "
        "Answer in the same language as the user's question. "
        "Every factual or prescriptive sentence must include at least one inline citation formatted exactly as [REF:ID]. "
        "Use only the allowed reference IDs below. Do not cite any other identifier. "
        "cited_reference_ids must list every unique ID used in answer_markdown and no unused ID. "
        "limitations must preserve at least one concrete authority limitation. "
        f"Mode instruction: {_MODE_GUIDANCE[request.mode]} "
        f"Authority boundary: {request.authority_boundary} "
        f"Allowed reference IDs: {allowed}"
    )


def _provider_input(request: GroundedLiveAiRequest) -> str:
    payload = {
        "request_id": request.request_id,
        "mode": request.mode,
        "user_question": request.user_question,
        "case_hash": request.case_hash,
        "brief_id": request.brief_id,
        "allowed_reference_ids": request.allowed_reference_ids,
        "deterministic_context": request.deterministic_context,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _extract_json_text(output_text: str) -> str:
    text = output_text.strip()
    match = _JSON_FENCE.match(text)
    return match.group(1).strip() if match else text


def _parse_provider_payload(output_text: str) -> GroundedLiveAiProviderPayload:
    try:
        payload = json.loads(_extract_json_text(output_text))
    except json.JSONDecodeError as exc:
        raise LiveAiProviderError("Live AI provider returned malformed JSON") from exc
    try:
        return GroundedLiveAiProviderPayload.model_validate(payload)
    except Exception as exc:
        raise LiveAiProviderError(f"Live AI provider response contract failed: {exc}") from exc


def _create_openai_client(*, api_key: str, timeout_seconds: float):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LiveAiProviderError(
            "The optional openai package is not installed. Run pip install -r requirements.txt."
        ) from exc
    return OpenAI(api_key=api_key, timeout=timeout_seconds)


def run_grounded_openai_live_ai(
    request: GroundedLiveAiRequest,
    *,
    settings: OpenAiLiveAiSettings | None = None,
    environment: Mapping[str, str] | None = None,
    client: Any | None = None,
) -> GroundedLiveAiExecution:
    """Call OpenAI once, attach local audit metadata, and validate all inline references.

    An unaccepted response is returned with ``validation.accepted=False`` so the UI can show
    the rejection reason without displaying the provider answer as trusted output.
    """

    env = environment if environment is not None else os.environ
    resolved = settings or OpenAiLiveAiSettings.from_environment(env)
    api_key = env.get("OPENAI_API_KEY", "").strip()
    if client is None and not api_key:
        raise LiveAiProviderError("OPENAI_API_KEY is not configured")

    resolved_client = client or _create_openai_client(
        api_key=api_key,
        timeout_seconds=resolved.timeout_seconds,
    )
    try:
        raw_response = resolved_client.responses.create(
            model=resolved.model_name,
            instructions=_provider_instructions(request),
            input=_provider_input(request),
            max_output_tokens=resolved.max_output_tokens,
            store=False,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "grounded_live_ai_response",
                    "schema": GroundedLiveAiProviderPayload.model_json_schema(),
                    "strict": True,
                }
            },
        )
    except Exception as exc:
        request_id = getattr(exc, "request_id", None)
        suffix = f"; request_id={request_id}" if request_id else ""
        raise LiveAiProviderError(f"OpenAI Responses API call failed{suffix}: {exc}") from exc

    status = getattr(raw_response, "status", None)
    if status not in {None, "completed"}:
        details = getattr(raw_response, "incomplete_details", None)
        raise LiveAiProviderError(
            f"OpenAI response did not complete: status={status}; details={details}"
        )
    output_text = str(getattr(raw_response, "output_text", "") or "").strip()
    if not output_text:
        raise LiveAiProviderError("OpenAI response contained no output text")

    payload = _parse_provider_payload(output_text)
    response = GroundedLiveAiResponse(
        request_id=request.request_id,
        answer_markdown=payload.answer_markdown,
        cited_reference_ids=payload.cited_reference_ids,
        provider_name="openai",
        model_name=resolved.model_name,
        generated_at=datetime.now(timezone.utc),
        limitations=payload.limitations,
    )
    validation = validate_grounded_live_ai_response(request, response)
    return GroundedLiveAiExecution(
        request=request,
        response=response,
        validation=validation,
        provider_request_id=getattr(raw_response, "_request_id", None),
    )
