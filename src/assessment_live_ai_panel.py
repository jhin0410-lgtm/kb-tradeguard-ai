"""Streamlit presentation for optional validated Live AI responses."""

from __future__ import annotations

import json
import os
from uuid import uuid4

import streamlit as st

from .intelligence.live_ai_contract import build_live_ai_grounding_packet
from .intelligence.live_ai_provider import (
    LiveAiProviderError,
    OpenAiLiveAiSettings,
    openai_live_ai_is_configured,
    run_grounded_openai_live_ai,
)
from .intelligence.single_transaction_package import SingleTransactionPackageRun


def _json_bytes(payload) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _clear_stale_live_ai_state(case_hash: str) -> None:
    stored_hash = st.session_state.get("live_ai_case_hash")
    if stored_hash == case_hash:
        return
    for key in ("live_ai_packet", "live_ai_execution", "live_ai_error"):
        st.session_state.pop(key, None)
    st.session_state["live_ai_case_hash"] = case_hash


def render_grounded_live_ai_panel(run: SingleTransactionPackageRun) -> None:
    """Render provider configuration, bounded request creation, call, and validation."""

    _clear_stale_live_ai_state(run.output_case_hash)
    st.subheader("선택형 Grounded Live AI")
    st.caption(
        "결정론적 Brief 이후에만 실행됩니다. 모델은 승인·거절, 계산, Finding 변경, "
        "법률판단 또는 제재·AML 해소를 수행하지 않습니다."
    )
    enabled = st.toggle("Live AI 실험 모드", value=False)
    if not enabled:
        st.info("기본값은 OFF입니다. 분석·보고서·다운로드에는 API가 필요하지 않습니다.")
        return

    configured = openai_live_ai_is_configured()
    model_default = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
    status_left, status_right = st.columns([1, 2])
    status_left.metric("OpenAI API", "연결 가능" if configured else "키 없음")
    model_name = status_right.text_input("모델", value=model_default)
    if not configured:
        st.warning(
            "OPENAI_API_KEY 환경변수가 없어 실제 호출은 비활성화됩니다. "
            "Grounding Packet 생성과 검토는 계속 가능합니다."
        )

    mode = st.selectbox(
        "AI 역할",
        [
            "explain_brief",
            "prepare_consultation",
            "evidence_lookup",
            "compare_reviewed_options",
        ],
    )
    question = st.text_area(
        "질문",
        value="왜 이 사전진단 상태가 나왔고 은행 상담 전에 무엇을 준비해야 하나요?",
        height=110,
    )
    st.warning(
        "Live AI를 실행하면 아래 Grounding Packet의 거래정보가 OpenAI API로 전송됩니다. "
        "실제 고객·계약정보를 사용하기 전 비식별화와 조직 정책 확인이 필요합니다."
    )

    packet_col, call_col = st.columns(2)
    packet_clicked = packet_col.button(
        "Grounding Packet 생성",
        use_container_width=True,
    )
    call_clicked = call_col.button(
        "OpenAI로 근거 답변 생성",
        type="primary",
        disabled=not configured or not question.strip(),
        use_container_width=True,
    )

    if packet_clicked or call_clicked:
        try:
            packet = build_live_ai_grounding_packet(
                run.updated_case,
                run.assessment_result,
                request_id=(
                    f"LIVE-{run.assessment_result.pipeline_id}-{uuid4().hex[:10]}"
                ),
                mode=mode,
                user_question=question,
            )
        except Exception as exc:
            st.session_state["live_ai_error"] = f"Grounding Packet 생성 실패: {exc}"
        else:
            st.session_state["live_ai_packet"] = packet
            st.session_state.pop("live_ai_execution", None)
            st.session_state.pop("live_ai_error", None)
            if call_clicked:
                try:
                    with st.spinner("Grounding Packet으로 OpenAI 응답을 생성하고 인용을 검증합니다."):
                        execution = run_grounded_openai_live_ai(
                            packet,
                            settings=OpenAiLiveAiSettings(model_name=model_name),
                        )
                except LiveAiProviderError as exc:
                    st.session_state["live_ai_error"] = str(exc)
                except Exception as exc:
                    st.session_state["live_ai_error"] = (
                        f"예상하지 못한 Live AI 오류로 결정론적 결과만 유지합니다: {exc}"
                    )
                else:
                    st.session_state["live_ai_execution"] = execution

    error = st.session_state.get("live_ai_error")
    if error:
        st.error(error)

    packet = st.session_state.get("live_ai_packet")
    if packet is not None:
        st.success(
            f"허용된 Reference ID {len(packet.allowed_reference_ids)}개로 Grounding Packet을 고정했습니다."
        )
        with st.expander("Grounding Packet 확인", expanded=False):
            st.json(packet.model_dump(mode="json"))
        st.download_button(
            "Grounding Packet 다운로드",
            data=_json_bytes(packet.model_dump(mode="json")),
            file_name="live_ai_grounding_packet.json",
            mime="application/json",
        )

    execution = st.session_state.get("live_ai_execution")
    if execution is None:
        return
    if not execution.validation.accepted:
        st.error("Provider 응답이 근거 검증을 통과하지 못해 답변을 표시하지 않습니다.")
        for item in execution.validation.errors:
            st.write(f"- {item}")
        with st.expander("거부된 응답 메타데이터"):
            st.json(execution.model_dump(mode="json"))
        return

    st.success("모든 inline Reference ID가 Grounding Packet 범위와 일치했습니다.")
    st.markdown(execution.response.answer_markdown)
    st.caption(
        f"Provider: {execution.response.provider_name} · Model: {execution.response.model_name} · "
        f"Provider request ID: {execution.provider_request_id or '-'}"
    )
    st.markdown("**인용된 Reference ID**")
    st.code("\n".join(execution.response.cited_reference_ids), language="text")
    st.markdown("**제한사항**")
    for limitation in execution.response.limitations:
        st.write(f"- {limitation}")
    st.download_button(
        "검증된 Live AI 응답 다운로드",
        data=_json_bytes(execution.model_dump(mode="json")),
        file_name="validated_live_ai_response.json",
        mime="application/json",
    )
