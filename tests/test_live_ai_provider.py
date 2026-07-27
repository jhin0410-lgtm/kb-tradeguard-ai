import json

import pytest

from src.intelligence.live_ai_contract import GroundedLiveAiRequest
from src.intelligence.live_ai_provider import (
    LiveAiProviderError,
    OpenAiLiveAiSettings,
    openai_live_ai_is_configured,
    run_grounded_openai_live_ai,
)


class _FakeRawResponse:
    def __init__(self, output_text: str, *, status: str = "completed"):
        self.output_text = output_text
        self.status = status
        self.incomplete_details = None
        self._request_id = "req_test_123"


class _FakeResponses:
    def __init__(self, raw_response):
        self.raw_response = raw_response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.raw_response


class _FakeClient:
    def __init__(self, raw_response):
        self.responses = _FakeResponses(raw_response)


def _request() -> GroundedLiveAiRequest:
    return GroundedLiveAiRequest(
        request_id="LIVE-TEST-001",
        case_hash="a" * 64,
        brief_id="BRIEF-001",
        mode="explain_brief",
        user_question="왜 추가 정보가 필요한가요?",
        allowed_reference_ids=["RISK-001", "ACTION-001"],
        deterministic_context={
            "brief": {
                "disposition": "additional_information_required",
                "missing_information": ["reviewed_trade_document"],
            }
        },
    )


def _payload(answer: str, references: list[str]) -> str:
    return json.dumps(
        {
            "answer_markdown": answer,
            "cited_reference_ids": references,
            "limitations": ["설명 전용이며 거래 승인이나 법률판단이 아닙니다."],
        },
        ensure_ascii=False,
    )


def test_configuration_requires_nonempty_api_key():
    assert not openai_live_ai_is_configured({})
    assert not openai_live_ai_is_configured({"OPENAI_API_KEY": "  "})
    assert openai_live_ai_is_configured({"OPENAI_API_KEY": "test-key"})


def test_valid_provider_output_is_locally_validated_and_audited():
    client = _FakeClient(
        _FakeRawResponse(
            _payload(
                "검토 문서가 없어 추가 정보가 필요합니다. [REF:RISK-001]",
                ["RISK-001"],
            )
        )
    )

    execution = run_grounded_openai_live_ai(
        _request(),
        settings=OpenAiLiveAiSettings(
            model_name="gpt-5-mini",
            timeout_seconds=10,
            max_output_tokens=600,
        ),
        environment={},
        client=client,
    )

    assert execution.validation.accepted is True
    assert execution.provider_request_id == "req_test_123"
    assert execution.response.provider_name == "openai"
    assert execution.response.model_name == "gpt-5-mini"
    assert execution.response.decision_status == "explanation_only"
    assert client.responses.calls[0]["store"] is False
    assert client.responses.calls[0]["max_output_tokens"] == 600
    assert "RISK-001" in client.responses.calls[0]["instructions"]
    assert "deterministic_context" in client.responses.calls[0]["input"]


def test_unknown_reference_is_rejected_before_display():
    client = _FakeClient(
        _FakeRawResponse(
            _payload(
                "확인되지 않은 근거입니다. [REF:UNKNOWN-999]",
                ["UNKNOWN-999"],
            )
        )
    )

    execution = run_grounded_openai_live_ai(
        _request(), environment={}, client=client
    )

    assert execution.validation.accepted is False
    assert execution.validation.unknown_reference_ids == ["UNKNOWN-999"]


def test_malformed_json_fails_closed():
    client = _FakeClient(_FakeRawResponse("not-json"))

    with pytest.raises(LiveAiProviderError, match="malformed JSON"):
        run_grounded_openai_live_ai(_request(), environment={}, client=client)


def test_incomplete_response_fails_closed():
    client = _FakeClient(_FakeRawResponse("{}", status="incomplete"))

    with pytest.raises(LiveAiProviderError, match="did not complete"):
        run_grounded_openai_live_ai(_request(), environment={}, client=client)


def test_missing_key_is_reported_before_client_creation():
    with pytest.raises(LiveAiProviderError, match="OPENAI_API_KEY"):
        run_grounded_openai_live_ai(_request(), environment={})
