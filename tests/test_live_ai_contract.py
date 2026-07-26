from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.intelligence.live_ai_contract import (
    GroundedLiveAiResponse,
    build_live_ai_grounding_packet,
    validate_grounded_live_ai_response,
)
from src.intelligence.single_transaction_package import (
    load_single_transaction_package,
    run_single_transaction_package,
)


EXAMPLE = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "single_transaction_assessment_package_minimal.json"
)


def _run():
    package = load_single_transaction_package(EXAMPLE)
    return run_single_transaction_package(package)


def test_grounding_packet_is_bounded_to_completed_assessment_records():
    run = _run()
    request = build_live_ai_grounding_packet(
        run.updated_case,
        run.assessment_result,
        request_id="LIVE-AI-001",
        mode="explain_brief",
        user_question="왜 추가 정보가 필요한지 근거와 함께 설명해 주세요.",
    )

    assert request.case_hash == run.output_case_hash
    assert request.brief_id == run.assessment_result.brief.brief_id
    assert request.allowed_reference_ids
    assert request.deterministic_context["brief"]["disposition"] == (
        "additional_information_required"
    )
    assert "must not approve" in request.authority_boundary


def test_grounded_response_requires_matching_inline_and_declared_references():
    run = _run()
    request = build_live_ai_grounding_packet(
        run.updated_case,
        run.assessment_result,
        request_id="LIVE-AI-002",
        mode="prepare_consultation",
        user_question="상담 전에 무엇을 준비해야 하나요?",
    )
    reference_id = request.allowed_reference_ids[0]
    response = GroundedLiveAiResponse(
        request_id=request.request_id,
        answer_markdown=f"현재 검토결과에는 추가 확인이 필요합니다. [REF:{reference_id}]",
        cited_reference_ids=[reference_id],
        provider_name="test-provider",
        model_name="test-model",
        generated_at=datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc),
        limitations=[request.authority_boundary],
    )

    validation = validate_grounded_live_ai_response(request, response)

    assert validation.accepted is True
    assert validation.parsed_reference_ids == [reference_id]
    assert validation.errors == []


def test_unknown_or_mismatched_citations_are_rejected():
    run = _run()
    request = build_live_ai_grounding_packet(
        run.updated_case,
        run.assessment_result,
        request_id="LIVE-AI-003",
        mode="evidence_lookup",
        user_question="근거를 보여 주세요.",
    )
    known = request.allowed_reference_ids[0]
    response = GroundedLiveAiResponse(
        request_id=request.request_id,
        answer_markdown=f"알 수 없는 근거입니다. [REF:UNKNOWN-REF] [REF:{known}]",
        cited_reference_ids=["UNKNOWN-REF"],
        provider_name="test-provider",
        model_name="test-model",
        generated_at=datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc),
        limitations=["Explanation only."],
    )

    validation = validate_grounded_live_ai_response(request, response)

    assert validation.accepted is False
    assert validation.unknown_reference_ids == ["UNKNOWN-REF"]
    assert validation.undeclared_inline_citations == [known]
    assert any("outside the grounding packet" in item for item in validation.errors)


def test_response_without_inline_citation_or_limitation_is_rejected():
    run = _run()
    request = build_live_ai_grounding_packet(
        run.updated_case,
        run.assessment_result,
        request_id="LIVE-AI-004",
        mode="explain_brief",
        user_question="요약해 주세요.",
    )
    response = GroundedLiveAiResponse(
        request_id=request.request_id,
        answer_markdown="근거 표기 없이 작성된 설명입니다.",
        cited_reference_ids=[],
        provider_name="test-provider",
        model_name="test-model",
        generated_at=datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc),
        limitations=[],
    )

    validation = validate_grounded_live_ai_response(request, response)

    assert validation.accepted is False
    assert len(validation.errors) == 2


def test_grounding_packet_rejects_case_result_hash_mismatch():
    run = _run()
    altered = run.updated_case.model_copy(update={"approved_transactions": []})

    with pytest.raises(ValueError, match="case hash"):
        build_live_ai_grounding_packet(
            altered,
            run.assessment_result,
            request_id="LIVE-AI-005",
            mode="explain_brief",
            user_question="설명해 주세요.",
        )
