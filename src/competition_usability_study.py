"""Low-risk usability-study instrumentation for the public competition UI.

The study mode stores only an optional participant code and task answers in the current
Streamlit session. It does not collect names, contact details, customer documents, or
production analytics.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import streamlit as st

from .assessment_app_v2 import RiskFirstSummary, build_risk_first_summary


@dataclass(frozen=True)
class UsabilityResult:
    participant_code: str
    elapsed_seconds: float
    selected_risk_id: str
    selected_action_id: str
    expected_risk_id: str
    expected_action_id: str
    risk_correct: bool
    action_correct: bool

    @property
    def task_success(self) -> bool:
        return self.risk_correct and self.action_correct

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "tradeguard-usability/1.0",
            "participant_code": self.participant_code,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "selected_risk_id": self.selected_risk_id,
            "selected_action_id": self.selected_action_id,
            "expected_risk_id": self.expected_risk_id,
            "expected_action_id": self.expected_action_id,
            "risk_correct": self.risk_correct,
            "action_correct": self.action_correct,
            "task_success": self.task_success,
            "privacy_boundary": "No name, contact detail, customer document, or production telemetry is collected.",
        }


def evaluate_usability_response(
    *,
    participant_code: str,
    elapsed_seconds: float,
    selected_risk_id: str,
    selected_action_id: str,
    expected_risk_id: str,
    expected_action_id: str,
) -> UsabilityResult:
    if elapsed_seconds < 0:
        raise ValueError("elapsed_seconds must be non-negative")
    return UsabilityResult(
        participant_code=participant_code.strip() or "anonymous",
        elapsed_seconds=elapsed_seconds,
        selected_risk_id=selected_risk_id,
        selected_action_id=selected_action_id,
        expected_risk_id=expected_risk_id,
        expected_action_id=expected_action_id,
        risk_correct=selected_risk_id == expected_risk_id,
        action_correct=selected_action_id == expected_action_id,
    )


def build_neutral_study_options(
    summary: RiskFirstSummary,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return alphabetized, unranked labels so the UI does not reveal the answers."""

    risk_options = {
        item.title: item.concern_id
        for item in sorted(summary.top_risks, key=lambda item: (item.title, item.concern_id))
    }
    action_options = {
        item.title: item.action_id
        for item in sorted(summary.next_actions, key=lambda item: (item.title, item.action_id))
    }
    return risk_options, action_options


def study_mode_enabled() -> bool:
    value = st.query_params.get("study", "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def render_usability_study(run) -> None:
    """Render a timed two-question task when ``?study=true`` is present."""

    if not study_mode_enabled():
        return
    summary = build_risk_first_summary(run)
    if not summary.top_risks or not summary.next_actions:
        st.warning("사용성 과제를 구성할 위험 또는 실행 행동이 없습니다.")
        return

    risk_options, action_options = build_neutral_study_options(summary)
    expected_risk = summary.top_risks[0].concern_id
    expected_action = summary.next_actions[0].action_id

    with st.container(border=True):
        st.markdown("### 사용성 검증 모드")
        st.caption(
            "과제: 이 거래에서 가장 먼저 볼 위험과 첫 번째 실행 행동을 찾으세요. "
            "선택지는 우선순위를 숨긴 중립 순서이며, 이름·연락처·실제 고객자료는 수집하지 않습니다."
        )
        participant_code = st.text_input(
            "참가자 코드(선택)",
            value="",
            placeholder="예: P01",
            key="usability_participant_code",
        )
        if "usability_started_at" not in st.session_state:
            if st.button("과제 시작", use_container_width=True, key="usability_start"):
                st.session_state["usability_started_at"] = time.monotonic()
                st.session_state.pop("usability_result", None)
                st.rerun()
            return

        risk_label = st.selectbox(
            "가장 먼저 볼 위험",
            list(risk_options),
            index=None,
            placeholder="위험을 선택하세요",
            key="usability_risk",
        )
        action_label = st.selectbox(
            "첫 번째 실행 행동",
            list(action_options),
            index=None,
            placeholder="행동을 선택하세요",
            key="usability_action",
        )
        selections_complete = risk_label is not None and action_label is not None
        if st.button(
            "과제 완료",
            use_container_width=True,
            key="usability_complete",
            disabled=not selections_complete,
        ):
            elapsed = time.monotonic() - float(st.session_state["usability_started_at"])
            result = evaluate_usability_response(
                participant_code=participant_code,
                elapsed_seconds=elapsed,
                selected_risk_id=risk_options[str(risk_label)],
                selected_action_id=action_options[str(action_label)],
                expected_risk_id=expected_risk,
                expected_action_id=expected_action,
            )
            st.session_state["usability_result"] = result.as_dict()
            st.session_state.pop("usability_started_at", None)

        payload = st.session_state.get("usability_result")
        if payload:
            if payload["task_success"]:
                st.success(f"과제 성공 · {payload['elapsed_seconds']:.2f}초")
            else:
                st.warning(f"과제 미완료 · {payload['elapsed_seconds']:.2f}초 · 선택 경로를 다시 확인하세요.")
            st.download_button(
                "사용성 결과 JSON 저장",
                data=(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
                file_name=f"tradeguard-usability-{payload['participant_code']}.json",
                mime="application/json",
                use_container_width=True,
            )
