"""V2 product-style Streamlit entrypoint for KB TradeGuard AI.

The V2 UI reuses the governed deterministic pipeline from assessment_app.py and adds
only presentation behavior: a risk-first 60-second cockpit, evidence popovers, a
responsive compact mode, and downloadable visual presentation snapshots.
"""

from __future__ import annotations

import json
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

import assessment_app as detailed
from src.assessment_app_v2 import (
    RiskFirstCard,
    build_evidence_drawer_items,
    build_presentation_snapshot_v2,
    build_risk_first_summary,
    render_presentation_snapshot_html,
)
from src.demo_scenarios import list_demo_scenarios
from src.intelligence.single_transaction_package import (
    SingleTransactionAssessmentPackage,
    SingleTransactionPackageRun,
)


V2_CSS = """
<style>
:root {
  --v2-navy: #06162d;
  --v2-blue: #185ed8;
  --v2-cyan: #0e9fb1;
  --v2-ink: #172033;
  --v2-muted: #637086;
  --v2-border: #dbe4ef;
  --v2-soft: #f4f7fb;
  --v2-danger: #b52431;
  --v2-warning: #b76800;
  --v2-success: #147455;
}
.block-container {max-width: 1480px; padding-top: 1rem; padding-bottom: 3rem;}
[data-testid="stSidebar"] {border-right: 1px solid var(--v2-border);}
.v2-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, .6fr);
  gap: 1rem;
  align-items: stretch;
  margin-bottom: 1rem;
}
.v2-hero-main {
  padding: 1.7rem 1.9rem;
  border-radius: 22px;
  color: #fff;
  background: radial-gradient(circle at 85% 15%, rgba(34,190,204,.45), transparent 35%),
              linear-gradient(126deg, #06162d 0%, #103d79 62%, #0b7188 100%);
  box-shadow: 0 16px 40px rgba(6, 22, 45, .18);
}
.v2-hero-main small {font-size: .74rem; letter-spacing: .14em; font-weight: 800; opacity: .76;}
.v2-hero-main h1 {font-size: 2.15rem; line-height: 1.15; margin: .55rem 0 .65rem;}
.v2-hero-main p {font-size: .98rem; line-height: 1.58; max-width: 900px; margin: 0; opacity: .94;}
.v2-hero-side {
  display: grid;
  grid-template-rows: repeat(3, 1fr);
  gap: .55rem;
}
.v2-chip {
  border: 1px solid var(--v2-border);
  background: #fff;
  border-radius: 15px;
  padding: .78rem .9rem;
  box-shadow: 0 6px 18px rgba(20, 39, 70, .05);
}
.v2-chip strong {display: block; color: var(--v2-ink); font-size: .88rem; margin-bottom: .18rem;}
.v2-chip span {display: block; color: var(--v2-muted); font-size: .76rem; line-height: 1.4;}
.v2-verdict {
  border: 1px solid var(--v2-border);
  border-radius: 20px;
  padding: 1.15rem 1.3rem;
  background: #fff;
  margin: .35rem 0 .8rem;
}
.v2-verdict[data-tone="critical"] {border-left: 8px solid var(--v2-danger); background: #fff5f6;}
.v2-verdict[data-tone="warning"] {border-left: 8px solid var(--v2-warning); background: #fff9ef;}
.v2-verdict[data-tone="info"] {border-left: 8px solid var(--v2-blue); background: #f4f8ff;}
.v2-verdict[data-tone="clear"] {border-left: 8px solid var(--v2-success); background: #f2faf7;}
.v2-verdict small {font-weight: 800; letter-spacing: .08em; color: var(--v2-muted);}
.v2-verdict h2 {margin: .3rem 0 .35rem; font-size: 1.35rem; color: var(--v2-ink);}
.v2-verdict p {margin: 0; color: var(--v2-muted); line-height: 1.5;}
.v2-section-label {margin: 1rem 0 .45rem; font-size: .78rem; font-weight: 800; letter-spacing: .1em; color: var(--v2-muted);}
.v2-risk-card {
  min-height: 204px;
  border: 1px solid var(--v2-border);
  border-radius: 18px;
  padding: 1rem;
  background: #fff;
  box-shadow: 0 8px 22px rgba(15, 36, 68, .055);
}
.v2-risk-card[data-severity="critical"] {border-top: 5px solid var(--v2-danger);}
.v2-risk-card[data-severity="high"] {border-top: 5px solid var(--v2-warning);}
.v2-risk-card[data-severity="medium"] {border-top: 5px solid #7b55b3;}
.v2-risk-card[data-severity="low"] {border-top: 5px solid var(--v2-blue);}
.v2-risk-card h3 {font-size: 1rem; line-height: 1.4; margin: .55rem 0 .4rem; color: var(--v2-ink);}
.v2-risk-card p {font-size: .84rem; color: var(--v2-muted); line-height: 1.48; margin-bottom: .45rem;}
.v2-badge {display:inline-block; padding:.3rem .5rem; border-radius:999px; background:var(--v2-soft); font-size:.68rem; font-weight:800;}
.v2-action-card {border:1px solid var(--v2-border); border-radius:16px; padding:.95rem; background:var(--v2-soft); min-height:150px;}
.v2-action-card h4 {margin:.2rem 0 .35rem; color:var(--v2-ink); font-size:.95rem;}
.v2-action-card p {margin:.2rem 0; color:var(--v2-muted); font-size:.82rem; line-height:1.45;}
.v2-ref {font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size:.73rem; color:#4f6078; word-break:break-all;}
.v2-evidence {border:1px solid var(--v2-border); border-radius:14px; padding:.8rem .9rem; margin:.55rem 0; background:#fff;}
.v2-evidence h4 {margin:0 0 .2rem; font-size:.9rem;}
.v2-evidence p {margin:.2rem 0; color:var(--v2-muted); font-size:.8rem; line-height:1.45;}
.v2-mobile-note {border:1px dashed #97a8c0; border-radius:14px; padding:.8rem 1rem; background:#f8fafc; color:var(--v2-muted); font-size:.82rem;}
@media (max-width: 900px) {
  .block-container {padding-left: .85rem; padding-right: .85rem; padding-top: .7rem;}
  .v2-hero {grid-template-columns: 1fr;}
  .v2-hero-side {grid-template-columns: 1fr 1fr 1fr; grid-template-rows: auto;}
  .v2-hero-main {padding:1.35rem; border-radius:18px;}
  .v2-hero-main h1 {font-size:1.7rem;}
  .v2-chip {padding:.65rem;}
}
@media (max-width: 640px) {
  .block-container {padding-left: .65rem; padding-right: .65rem; padding-bottom: 5rem;}
  .v2-hero-side {grid-template-columns:1fr;}
  .v2-hero-main small {font-size:.65rem; letter-spacing:.09em;}
  .v2-hero-main h1 {font-size:1.52rem;}
  .v2-hero-main p {font-size:.88rem;}
  .v2-verdict {padding:.95rem; border-radius:15px;}
  .v2-verdict h2 {font-size:1.12rem;}
  .v2-risk-card {min-height:auto;}
  [data-testid="stMetric"] {border:1px solid var(--v2-border); border-radius:12px; padding:.45rem .55rem; background:#fff;}
  [data-testid="stHorizontalBlock"] {gap:.55rem;}
  button[kind="primary"] {min-height:46px;}
}
</style>
"""

_SEVERITY_LABELS = {
    "critical": "CRITICAL · 치명",
    "high": "HIGH · 높음",
    "medium": "MEDIUM · 보통",
    "low": "LOW · 낮음",
    "informational": "INFO · 정보",
}
_RESPONSIBLE_LABELS = {
    "customer": "고객사",
    "bank": "은행",
    "ksure": "K-SURE",
    "buyer": "바이어",
    "seller": "수출자",
    "legal_counsel": "법무",
    "logistics_provider": "물류",
    "other": "기타 담당",
}


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _query_view() -> str:
    value = st.query_params.get("view", "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def _render_view_mode_control() -> bool:
    requested_compact = _query_view().lower() == "compact"
    with st.sidebar:
        st.markdown("## 화면 모드")
        label = st.radio(
            "화면 구성",
            ["60초 제품 화면", "상세 검토 화면"],
            index=0 if requested_compact else 1,
            horizontal=True,
            help="휴대폰과 발표 화면은 60초 제품 화면을 권장합니다.",
        )
        compact = label == "60초 제품 화면"
        current = _query_view().lower()
        if compact and current != "compact":
            st.query_params["view"] = "compact"
        elif not compact and current == "compact":
            del st.query_params["view"]
        st.caption("모바일 공유 링크는 현재 URL 뒤에 `?view=compact`를 붙입니다.")
    return compact


def _render_header(compact: bool) -> None:
    st.markdown(detailed.APP_CSS + V2_CSS, unsafe_allow_html=True)
    side = """
      <div class="v2-hero-side">
        <div class="v2-chip"><strong>Risk-first</strong><span>총점 대신 상위 위험과 사실 근거를 우선 표시</span></div>
        <div class="v2-chip"><strong>Evidence Drawer</strong><span>판정 문장 → Reference ID → 원천 레코드 연결</span></div>
        <div class="v2-chip"><strong>Mobile compact</strong><span>스마트폰·발표 화면에 맞춘 반응형 4탭 구성</span></div>
      </div>
    """
    st.markdown(
        f"""
        <section class="v2-hero">
          <div class="v2-hero-main">
            <small>KB TRADEGUARD AI · PRODUCT UI V2</small>
            <h1>60초 안에 거래 전 위험과 다음 행동을 파악합니다</h1>
            <p>기업·거래·바이어·국가·계약조건을 하나의 결정론적 Brief로 연결하고, 모든 핵심 문장을 Evidence Drawer와 감사 식별자로 추적합니다.</p>
          </div>
          {side if not compact else side}
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "사전검사·상담 준비용 프로토타입이며 거래 승인·법률의견·제재 해소·실행 금리·한도·상품 적격성을 확정하지 않습니다."
    )


def _render_evidence_items(items: list[Any]) -> None:
    if not items:
        st.info("선택한 Reference ID와 일치하는 현재 Case 레코드가 없습니다.")
        return
    for item in items:
        locator = item.source_locator or "로컬 레코드"
        as_of = item.as_of_date or "미기재"
        st.markdown(
            f"""
            <div class="v2-evidence">
              <h4>{item.record_type} · {item.title}</h4>
              <div class="v2-ref">{item.reference_id}</div>
              <p>{item.summary}</p>
              <p><strong>상태</strong> {item.status} · <strong>기준일</strong> {as_of}<br><strong>출처</strong> {item.source_name or '-'} · {locator}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if item.linked_reference_ids:
            st.caption("연결 ID · " + ", ".join(item.linked_reference_ids))
        if item.limitations:
            with st.expander("제한사항", expanded=False):
                for limitation in item.limitations:
                    st.write(f"- {limitation}")


def _render_risk_card(run: SingleTransactionPackageRun, risk: RiskFirstCard) -> None:
    st.markdown(
        f"""
        <div class="v2-risk-card" data-severity="{risk.severity}">
          <span class="v2-badge">{_SEVERITY_LABELS.get(risk.severity, risk.severity)}</span>
          <h3>{risk.rank}. {risk.title}</h3>
          <p>{risk.factual_basis}</p>
          <div class="v2-ref">{', '.join(risk.reference_ids) or 'REF 없음'}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.popover("Evidence Drawer", use_container_width=True):
        st.caption("선택 위험의 직접 Reference와 한 단계 연결 레코드만 표시합니다.")
        _render_evidence_items(
            build_evidence_drawer_items(run, risk.reference_ids, include_linked=True)
        )


def _render_global_evidence_drawer(run: SingleTransactionPackageRun) -> None:
    risks = build_risk_first_summary(run).top_risks
    if not risks:
        return
    by_label = {
        f"{item.rank}. {_SEVERITY_LABELS.get(item.severity, item.severity)} · {item.title}": item
        for item in risks
    }
    left, right = st.columns([4, 1])
    with left:
        selected_label = st.selectbox(
            "Evidence Drawer 대상 위험",
            list(by_label),
            label_visibility="collapsed",
        )
    with right:
        with st.popover("근거 열기", use_container_width=True):
            risk = by_label[selected_label]
            st.markdown(f"### {risk.title}")
            st.write(risk.factual_basis)
            _render_evidence_items(
                build_evidence_drawer_items(run, risk.reference_ids, include_linked=True)
            )


def _render_cockpit(run: SingleTransactionPackageRun) -> None:
    summary = build_risk_first_summary(run)
    presentation = detailed.disposition_presentation(summary.disposition)
    st.markdown(
        f"""
        <section class="v2-verdict" data-tone="{presentation.tone}">
          <small>{presentation.eyebrow}</small>
          <h2>{summary.disposition_headline}</h2>
          <p>{summary.disposition_explanation}<br><strong>다음 확인</strong> · {presentation.next_focus}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    metrics = st.columns(4)
    metrics[0].metric("상위 위험", len(summary.top_risks))
    metrics[1].metric("근거 Reference", summary.evidence_reference_count)
    metrics[2].metric("누락정보", len(summary.missing_information))
    metrics[3].metric(
        "Pipeline", f"{summary.completed_stage_count}/{summary.stage_count} 완료"
    )
    detailed._render_stage_stepper(run)

    st.markdown('<div class="v2-section-label">TOP RISKS · 가장 먼저 볼 위험</div>', unsafe_allow_html=True)
    if summary.top_risks:
        columns = st.columns(len(summary.top_risks))
        for column, risk in zip(columns, summary.top_risks):
            with column:
                _render_risk_card(run, risk)
    else:
        st.success("현재 검토자료에서 순위화된 우려사항이 없습니다. 이는 거래 승인 또는 안전 인증이 아닙니다.")

    st.markdown('<div class="v2-section-label">NEXT ACTIONS · 다음 실행 행동</div>', unsafe_allow_html=True)
    if summary.next_actions:
        columns = st.columns(len(summary.next_actions))
        for column, action in zip(columns, summary.next_actions):
            with column:
                dependencies = ", ".join(action.dependency_action_ids) or "없음"
                st.markdown(
                    f"""
                    <div class="v2-action-card">
                      <div class="v2-badge">STEP {action.sequence}</div>
                      <h4>{action.title}</h4>
                      <p><strong>담당</strong> {_RESPONSIBLE_LABELS.get(action.responsible_party, action.responsible_party)} · <strong>상태</strong> {action.status}</p>
                      <p><strong>선행</strong> {dependencies}</p>
                      <div class="v2-ref">{action.action_id}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("생성된 실행계획이 없습니다.")

    if summary.missing_information:
        with st.expander(f"누락정보 {len(summary.missing_information)}건", expanded=False):
            for item in summary.missing_information:
                st.write(f"- {item}")


def _render_snapshot_panel(
    run: SingleTransactionPackageRun,
    source_key: str | None,
) -> None:
    snapshot = build_presentation_snapshot_v2(run, scenario_id=source_key)
    html = render_presentation_snapshot_html(snapshot)
    st.markdown(
        '<div class="v2-mobile-note"><strong>발표 Snapshot V2</strong><br>상위 위험 3개, 다음 행동 3개, Case hash를 한 페이지에 고정한 오프라인 HTML입니다. 휴대폰에서도 같은 파일을 열 수 있습니다.</div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    left.download_button(
        "발표 Snapshot HTML",
        data=html.encode("utf-8"),
        file_name="kb-tradeguard-presentation-snapshot-v2.html",
        mime="text/html",
        use_container_width=True,
    )
    right.download_button(
        "발표 Snapshot JSON",
        data=_json_text(snapshot).encode("utf-8"),
        file_name="kb-tradeguard-presentation-snapshot-v2.json",
        mime="application/json",
        use_container_width=True,
    )
    with st.expander("Snapshot 화면 미리보기", expanded=False):
        components.html(html, height=760, scrolling=True)


def _render_compact_results(
    run: SingleTransactionPackageRun,
    package: SingleTransactionAssessmentPackage,
    source_key: str | None,
) -> None:
    _render_cockpit(run)
    tabs = st.tabs(["① 근거", "② 실행", "③ 문서·재무", "④ 감사·Snapshot"])
    with tabs[0]:
        _render_global_evidence_drawer(run)
        detailed._render_risk_tab(run)
    with tabs[1]:
        detailed._render_action_tab(run)
        st.divider()
        detailed._render_product_tab(run)
    with tabs[2]:
        document_tab, finance_tab = st.tabs(["문서", "재무"])
        with document_tab:
            detailed._render_document_tab(run)
        with finance_tab:
            detailed._render_financial_tab(run)
    with tabs[3]:
        _render_snapshot_panel(run, source_key)
        st.divider()
        detailed._render_audit_tab(run, package, source_key)


def _render_detailed_results(
    run: SingleTransactionPackageRun,
    package: SingleTransactionAssessmentPackage,
    source_key: str | None,
) -> None:
    _render_cockpit(run)
    tabs = st.tabs(
        [
            "① 요약",
            "② Evidence Drawer",
            "③ 위험",
            "④ 문서",
            "⑤ 재무",
            "⑥ 상담 후보",
            "⑦ 실행계획",
            "⑧ 감사·Snapshot",
            "⑨ Live AI",
        ]
    )
    with tabs[0]:
        detailed._render_summary_tab(run)
    with tabs[1]:
        _render_global_evidence_drawer(run)
        st.caption("Reference ID, Source, 기준일, 상태, 연결 ID와 제한사항을 한 곳에서 확인합니다.")
    with tabs[2]:
        detailed._render_risk_tab(run)
    with tabs[3]:
        detailed._render_document_tab(run)
    with tabs[4]:
        detailed._render_financial_tab(run)
    with tabs[5]:
        detailed._render_product_tab(run)
    with tabs[6]:
        detailed._render_action_tab(run)
    with tabs[7]:
        _render_snapshot_panel(run, source_key)
        st.divider()
        detailed._render_audit_tab(run, package, source_key)
    with tabs[8]:
        detailed.render_grounded_live_ai_panel(run)


def _render_landing(source_key: str | None, compact: bool) -> None:
    metadata = next(
        (item for item in list_demo_scenarios() if item.scenario_id == source_key),
        None,
    )
    if metadata is not None:
        detailed._render_scenario_card(metadata)

    st.markdown("### 제품 UI V2 시연 흐름")
    steps = [
        ("1", "거래 입력", "합성 대표 거래 또는 검토된 JSON Package를 선택합니다."),
        ("2", "60초 Brief", "판정, 상위 위험 3개, 다음 행동 3개를 먼저 확인합니다."),
        ("3", "Evidence Drawer", "Reference ID에서 문서·계산·국가·바이어 근거로 내려갑니다."),
        ("4", "감사 Snapshot", "Case hash와 발표용 HTML·JSON을 저장합니다."),
    ]
    columns = st.columns(2 if compact else 4)
    for column, (number, title, text) in zip(columns, steps):
        with column:
            with st.container(border=True):
                st.markdown(f"#### {number} · {title}")
                st.write(text)
    st.info("사이드바에서 ‘5단계 거래 사전진단 실행’을 누르면 Risk-first 제품 화면으로 전환됩니다.")


def main() -> None:
    st.set_page_config(
        page_title="KB TradeGuard AI · Product UI V2",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="auto",
    )
    compact = _render_view_mode_control()
    _render_header(compact)
    package, source_key = detailed._select_package()
    detailed._run_controls(package, source_key)

    run = st.session_state.get("assessment_run")
    executed_package = st.session_state.get("assessment_package")
    executed_source_key = st.session_state.get("assessment_source_key")
    if run is None or executed_package is None:
        _render_landing(source_key, compact)
        return
    if compact:
        _render_compact_results(run, executed_package, executed_source_key)
    else:
        _render_detailed_results(run, executed_package, executed_source_key)


if __name__ == "__main__":
    main()
