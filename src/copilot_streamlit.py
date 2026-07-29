"""Streamlit renderer for the governed Global Trade Copilot workspace.

The renderer consumes the client-neutral ``CopilotWorkspace`` contract. It does not
perform financial arithmetic, approve transactions, or execute scenarios.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from .copilot_workspace import CopilotWorkspace


STATUS_LABELS = {
    "ready": "준비됨",
    "review_required": "검토 필요",
    "blocked": "차단됨",
    "empty": "자료 없음",
    "completed": "완료",
    "not_run": "미실행",
}


def workspace_summary_rows(workspace: CopilotWorkspace) -> list[dict[str, Any]]:
    """Return compact section summaries for cards or table rendering."""

    return [
        {
            "section": section.title,
            "status": STATUS_LABELS.get(section.status, section.status),
            "summary": section.summary,
        }
        for section in workspace.sections
    ]


def workspace_trace_rows(workspace: CopilotWorkspace) -> list[dict[str, Any]]:
    """Return a stable, human-readable trace table."""

    return [
        {
            "순서": step.sequence,
            "구성요소": step.component,
            "작업": step.action,
            "상태": STATUS_LABELS.get(step.status, step.status),
            "권한": step.authority,
            "누락 입력": ", ".join(step.missing_inputs),
            "출력 ID": ", ".join(step.output_ids),
        }
        for step in workspace.trace
    ]


def _render_section(section) -> None:
    status = STATUS_LABELS.get(section.status, section.status)
    with st.container(border=True):
        left, right = st.columns([4, 1])
        left.markdown(f"### {section.title}")
        right.markdown(f"**{status}**")
        st.write(section.summary)
        if section.related_ids:
            st.caption("관련 ID: " + ", ".join(section.related_ids))
        if section.limitations:
            with st.expander("제한사항"):
                for limitation in section.limitations:
                    st.write("- " + limitation)
        if section.payload is not None:
            with st.expander("구조화 상세"):
                st.json(section.payload)


def render_copilot_workspace(workspace: CopilotWorkspace) -> None:
    """Render the primary governed workspace in Streamlit."""

    st.subheader("Global Trade Copilot Workspace")
    st.info(workspace.disclaimer)
    st.warning(workspace.authority_boundary)

    a, b, c, d = st.columns(4)
    a.metric("Workspace", workspace.workspace_id)
    b.metric("Case", workspace.case_id)
    c.metric("문서 준비도", f"{workspace.readiness.readiness_percent}%")
    d.metric("실행 준비 시나리오", len(workspace.scenarios.ready_candidates))

    st.markdown("### 상담 목적")
    st.write(workspace.user_objective)

    st.markdown("### 전체 상태")
    st.dataframe(
        pd.DataFrame(workspace_summary_rows(workspace)),
        width="stretch",
        hide_index=True,
    )

    for section in workspace.sections:
        _render_section(section)

    st.markdown("### 실행 추적")
    st.dataframe(
        pd.DataFrame(workspace_trace_rows(workspace)),
        width="stretch",
        hide_index=True,
    )

    audit_json = json.dumps(
        workspace.audit_export,
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    st.download_button(
        "Copilot 감사 JSON 내보내기",
        audit_json,
        "kb_tradeguard_copilot_audit.json",
        "application/json",
    )
    st.caption("시나리오 실행과 금융 의사결정에는 별도의 명시적 사람 검토가 필요합니다.")
