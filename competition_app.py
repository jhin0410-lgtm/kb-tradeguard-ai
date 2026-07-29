"""Single-screen public competition demo for KB TradeGuard AI.

The app uses synthetic transaction and company fixtures while presenting separately
labelled pinned public-data context. It hides development pages and upload controls,
presents a Korean risk-first workflow, and exposes read-only evidence and audit surfaces.
"""

from __future__ import annotations

import os
from html import escape
from typing import Any

import streamlit as st

import assessment_app as detailed
import assessment_app_v2 as v2
from src.assessment_app_presentation import disposition_presentation, scenario_narrative
from src.assessment_app_v2 import (
    RiskFirstCard,
    build_evidence_drawer_items,
    build_presentation_snapshot_v2,
    build_risk_first_summary,
    render_presentation_snapshot_html,
)
from src.competition_case_study_view import render_official_case_study_section
from src.competition_portfolio_view import render_portfolio_section, render_workflow_map
from src.competition_product_view import render_product_consultation_section
from src.competition_real_data_view import render_official_data_section
from src.competition_demo import (
    build_competition_validation_status,
    build_public_demo_qr_png,
    normalize_public_demo_url,
)
from src.demo_scenarios import list_demo_scenarios, load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


DEFAULT_SCENARIO_ID = "oa_high_risk"

COMPETITION_CSS = """
<style>
:root {
  --tg-navy:#07172d;
  --tg-blue:#1b63e9;
  --tg-cyan:#0d95aa;
  --tg-ink:#172033;
  --tg-muted:#647084;
  --tg-line:#dce4ef;
  --tg-soft:#f5f8fc;
  --tg-red:#b52431;
  --tg-orange:#b76800;
  --tg-green:#147455;
}
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stAppDeployButton"],
#MainMenu,
footer {display:none !important;}
.block-container {
  max-width:1240px;
  padding-top:1.1rem;
  padding-left:1rem;
  padding-right:1rem;
  padding-bottom:7rem;
}
html {scroll-behavior:smooth;}
.tg-hero {
  display:grid;
  grid-template-columns:minmax(0,1.5fr) minmax(250px,.5fr);
  gap:1rem;
  padding:1.45rem 1.55rem;
  border-radius:24px;
  color:#fff;
  background:radial-gradient(circle at 86% 10%,rgba(45,206,216,.42),transparent 34%),linear-gradient(128deg,#07172d,#124a86 63%,#0b7c90);
  box-shadow:0 16px 38px rgba(7,23,45,.18);
}
.tg-hero small {font-size:.69rem;letter-spacing:.13em;font-weight:800;opacity:.76;}
.tg-hero h1 {margin:.48rem 0 .52rem;font-size:2.05rem;line-height:1.18;letter-spacing:-.025em;}
.tg-hero p {margin:0;font-size:.92rem;line-height:1.58;opacity:.94;}
.tg-hero-side {display:grid;gap:.5rem;align-content:center;}
.tg-hero-chip {border:1px solid rgba(255,255,255,.24);border-radius:14px;padding:.72rem .78rem;background:rgba(255,255,255,.09);backdrop-filter:blur(5px);}
.tg-hero-chip strong {display:block;font-size:.82rem;margin-bottom:.14rem;}
.tg-hero-chip span {display:block;font-size:.69rem;line-height:1.4;opacity:.82;}
.tg-boundary {margin:.62rem 0 .88rem;color:#7c8798;font-size:.74rem;line-height:1.5;}
.tg-control {border:1px solid var(--tg-line);border-radius:17px;padding:.8rem .9rem;background:#fff;margin:.75rem 0;}
.tg-section-anchor {height:1px;scroll-margin-top:14px;}
.tg-section-title {margin:1.15rem 0 .52rem;font-size:.78rem;font-weight:900;letter-spacing:.11em;color:#748198;}
.tg-verdict {border:1px solid var(--tg-line);border-left:8px solid var(--tg-blue);border-radius:18px;padding:1rem 1.1rem;background:#fff;}
.tg-verdict[data-tone="critical"] {border-left-color:var(--tg-red);background:#fff5f6;}
.tg-verdict[data-tone="warning"] {border-left-color:var(--tg-orange);background:#fff9ef;}
.tg-verdict[data-tone="clear"] {border-left-color:var(--tg-green);background:#f2faf7;}
.tg-verdict small {font-size:.66rem;font-weight:900;letter-spacing:.09em;color:#77849a;}
.tg-verdict h2 {margin:.28rem 0 .3rem;font-size:1.34rem;color:var(--tg-ink);}
.tg-verdict p {margin:0;color:var(--tg-muted);line-height:1.5;font-size:.84rem;}
.tg-risk {border:1px solid var(--tg-line);border-top:5px solid var(--tg-blue);border-radius:18px;padding:.9rem;background:#fff;min-height:192px;box-shadow:0 8px 22px rgba(15,36,68,.055);}
.tg-risk[data-severity="critical"] {border-top-color:var(--tg-red);}
.tg-risk[data-severity="high"] {border-top-color:var(--tg-orange);}
.tg-risk[data-severity="medium"] {border-top-color:#7554aa;}
.tg-risk h3 {margin:.48rem 0 .36rem;font-size:.96rem;line-height:1.38;color:var(--tg-ink);}
.tg-risk p {margin:.2rem 0 .42rem;color:var(--tg-muted);font-size:.78rem;line-height:1.48;}
.tg-badge {display:inline-block;padding:.27rem .48rem;border-radius:999px;background:var(--tg-soft);font-size:.64rem;font-weight:900;}
.tg-ref-count {font-size:.68rem;color:#52627a;font-weight:700;}
.tg-action {border:1px solid var(--tg-line);border-radius:16px;padding:.86rem;background:var(--tg-soft);min-height:142px;}
.tg-action h4 {margin:.32rem 0 .34rem;font-size:.91rem;color:var(--tg-ink);}
.tg-action p {margin:.18rem 0;color:var(--tg-muted);font-size:.75rem;line-height:1.43;}
.tg-evidence-note {border:1px dashed #9aabc2;border-radius:14px;padding:.72rem .82rem;background:#f8fafc;color:#647084;font-size:.76rem;line-height:1.45;}
.tg-validation {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.55rem;}
.tg-validation-card {border:1px solid var(--tg-line);border-radius:15px;padding:.8rem;background:#fff;text-align:center;}
.tg-validation-card strong {display:block;font-size:1.35rem;color:var(--tg-ink);}
.tg-validation-card span {display:block;margin-top:.16rem;font-size:.68rem;color:var(--tg-muted);}
.tg-bottom-nav {position:fixed;left:50%;bottom:max(12px,env(safe-area-inset-bottom));transform:translateX(-50%);z-index:9999;display:flex;gap:.24rem;padding:.34rem;border:1px solid rgba(135,151,175,.55);border-radius:999px;background:rgba(8,19,36,.92);box-shadow:0 10px 30px rgba(0,0,0,.24);backdrop-filter:blur(14px);}
.tg-bottom-nav a {color:#eef4ff;text-decoration:none;font-size:.72rem;font-weight:800;padding:.62rem .8rem;border-radius:999px;white-space:nowrap;}
.tg-bottom-nav a:hover {background:rgba(255,255,255,.12);}
.tg-qr-wrap {display:grid;grid-template-columns:190px minmax(0,1fr);gap:1rem;align-items:center;border:1px solid var(--tg-line);border-radius:18px;padding:1rem;background:#fff;}
.tg-qr-copy h3 {margin:0 0 .35rem;font-size:1rem;color:var(--tg-ink);}
.tg-qr-copy p {margin:.2rem 0;color:var(--tg-muted);font-size:.78rem;line-height:1.48;}
.tg-presentation [data-testid="stSelectbox"],
.tg-presentation .tg-control,
.tg-presentation .tg-bottom-nav,
.tg-presentation .tg-audit-only {display:none !important;}
@media(max-width:760px) {
  .block-container {padding:.8rem .65rem 7rem;}
  .tg-hero {grid-template-columns:1fr;padding:1rem;border-radius:18px;}
  .tg-hero h1 {font-size:1.48rem;}
  .tg-hero p {font-size:.79rem;}
  .tg-hero-side {grid-template-columns:repeat(3,1fr);gap:.36rem;}
  .tg-hero-chip {padding:.5rem;}
  .tg-hero-chip strong {font-size:.67rem;}
  .tg-hero-chip span {font-size:.57rem;}
  .tg-verdict {padding:.86rem;border-radius:15px;}
  .tg-verdict h2 {font-size:1.08rem;}
  .tg-risk {min-height:auto;padding:.8rem;}
  .tg-action {min-height:auto;padding:.78rem;}
  .tg-validation {grid-template-columns:1fr 1fr;}
  .tg-qr-wrap {grid-template-columns:1fr;text-align:center;}
  .tg-bottom-nav {width:calc(100% - 1rem);justify-content:space-around;}
  .tg-bottom-nav a {padding:.58rem .58rem;font-size:.66rem;}
  [data-testid="stMetricValue"] {font-size:1.3rem;}
  [data-testid="stMetricLabel"] {font-size:.68rem;}
}
</style>
"""

_SEVERITY_LABELS = {
    "critical": "치명",
    "high": "높음",
    "medium": "보통",
    "low": "낮음",
    "informational": "정보",
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


def _flag(name: str) -> bool:
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _query_scenario_id() -> str:
    value = st.query_params.get("scenario", DEFAULT_SCENARIO_ID)
    if isinstance(value, list):
        value = value[0] if value else DEFAULT_SCENARIO_ID
    allowed = {item.scenario_id for item in list_demo_scenarios()}
    return str(value) if str(value) in allowed else DEFAULT_SCENARIO_ID


def _public_demo_url() -> str | None:
    value = os.getenv("TRADEGUARD_PUBLIC_DEMO_URL", "").strip()
    if not value:
        try:
            value = str(st.secrets.get("TRADEGUARD_PUBLIC_DEMO_URL", "")).strip()
        except Exception:
            value = ""
    if not value:
        return None
    try:
        return normalize_public_demo_url(value)
    except ValueError:
        return None


def _ensure_run(scenario_id: str):
    run = st.session_state.get("competition_run")
    active = st.session_state.get("competition_scenario_id")
    if run is not None and active == scenario_id:
        return run
    package = load_demo_scenario(scenario_id)
    with st.spinner("검토된 합성 거래 Package를 결정론적으로 분석합니다."):
        run = run_single_transaction_package(package)
    st.session_state["competition_run"] = run
    st.session_state["competition_package"] = package
    st.session_state["competition_scenario_id"] = scenario_id
    return run


def _render_hero() -> None:
    st.markdown(
        """
        <section class="tg-hero">
          <div>
            <small>KB TRADEGUARD AI · 공모전 공개 데모</small>
            <h1>거래 확정 전에 핵심 위험과 다음 행동을 확인합니다</h1>
            <p>기업·여러 수출입 거래·공식 데이터·문서·환노출·금융지원 후보를 하나의 검토 흐름으로 연결하고, 모든 핵심 판단을 근거 ID와 감사 식별자로 추적합니다.</p>
          </div>
          <div class="tg-hero-side">
            <div class="tg-hero-chip"><strong>핵심 위험 우선</strong><span>총점 대신 상위 위험과 사실 근거 표시</span></div>
            <div class="tg-hero-chip"><strong>판단 근거</strong><span>근거 ID에서 원천 레코드까지 연결</span></div>
            <div class="tg-hero-chip"><strong>검토 기록</strong><span>Case hash와 Snapshot 보존</span></div>
          </div>
        </section>
        <div class="tg-boundary">합성 데이터 기반 사전검사·상담 준비용 프로토타입입니다. 거래 승인·법률의견·제재 해소·금리·한도·상품 적격성을 확정하지 않습니다.</div>
        """,
        unsafe_allow_html=True,
    )


def _render_scenario_control(active_id: str) -> str:
    scenarios = list_demo_scenarios()
    by_label = {item.label: item.scenario_id for item in scenarios}
    active_label = next(item.label for item in scenarios if item.scenario_id == active_id)
    with st.container(border=True):
        st.markdown("**합성 시나리오 변경**")
        selected_label = st.selectbox(
            "시나리오",
            list(by_label),
            index=list(by_label).index(active_label),
            label_visibility="collapsed",
        )
        st.caption("선택 즉시 같은 결정론적 5단계 Pipeline으로 다시 실행합니다.")
    selected_id = by_label[selected_label]
    if selected_id != active_id:
        st.query_params["scenario"] = selected_id
        st.session_state.pop("competition_run", None)
        st.rerun()
    return selected_id


def _render_verdict(run) -> None:
    summary = build_risk_first_summary(run)
    presentation = disposition_presentation(summary.disposition)
    st.markdown('<div id="summary" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">01 · 거래 검토 요약</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <section class="tg-verdict" data-tone="{escape(presentation.tone)}">
          <small>{escape(presentation.eyebrow)}</small>
          <h2>{escape(summary.disposition_headline)}</h2>
          <p>{escape(summary.disposition_explanation)}<br><strong>다음 확인</strong> · {escape(presentation.next_focus)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    metrics = st.columns(4)
    metrics[0].metric("상위 위험", len(summary.top_risks))
    metrics[1].metric("근거 ID", summary.evidence_reference_count)
    metrics[2].metric("누락정보", len(summary.missing_information))
    metrics[3].metric("Pipeline", f"{summary.completed_stage_count}/{summary.stage_count}")
    detailed._render_stage_stepper(run)


def _render_risk_card(run, risk: RiskFirstCard) -> None:
    st.markdown(
        f"""
        <article class="tg-risk" data-severity="{escape(risk.severity)}">
          <span class="tg-badge">{escape(_SEVERITY_LABELS.get(risk.severity, risk.severity))}</span>
          <h3>{risk.rank}. {escape(risk.title)}</h3>
          <p>{escape(risk.factual_basis)}</p>
          <div class="tg-ref-count">판단 근거 {len(risk.reference_ids)}건</div>
        </article>
        """,
        unsafe_allow_html=True,
    )
    with st.popover("판단 근거 열기", use_container_width=True):
        st.caption("직접 근거와 한 단계 연결 레코드만 표시합니다.")
        v2._render_evidence_items(
            build_evidence_drawer_items(run, risk.reference_ids, include_linked=True)
        )


def _render_risks(run, *, presentation_mode: bool) -> None:
    summary = build_risk_first_summary(run)
    st.markdown('<div id="evidence" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">02 · 가장 먼저 볼 위험과 판단 근거</div>', unsafe_allow_html=True)
    if summary.top_risks:
        columns = st.columns(len(summary.top_risks))
        for column, risk in zip(columns, summary.top_risks):
            with column:
                _render_risk_card(run, risk)
    else:
        st.success("현재 자료에서 순위화된 중대한 사전검사 경보가 없습니다. 이는 거래 승인 또는 안전 인증이 아닙니다.")
    if not presentation_mode:
        st.markdown(
            '<div class="tg-evidence-note">카드의 ‘판단 근거 열기’를 누르면 위험 문장 → 근거 ID → 문서·계산·국가·바이어 레코드 순서로 확인할 수 있습니다.</div>',
            unsafe_allow_html=True,
        )
        with st.expander("전체 위험 및 근거 목록", expanded=False):
            detailed._render_risk_tab(run)


def _render_actions(run, *, presentation_mode: bool) -> None:
    summary = build_risk_first_summary(run)
    st.markdown('<div id="actions" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">03 · 다음 실행 행동</div>', unsafe_allow_html=True)
    if summary.next_actions:
        columns = st.columns(len(summary.next_actions))
        for column, action in zip(columns, summary.next_actions):
            dependencies = ", ".join(action.dependency_action_ids) or "없음"
            with column:
                st.markdown(
                    f"""
                    <article class="tg-action">
                      <span class="tg-badge">순서 {action.sequence}</span>
                      <h4>{escape(action.title)}</h4>
                      <p><strong>담당</strong> · {escape(_RESPONSIBLE_LABELS.get(action.responsible_party, action.responsible_party))}</p>
                      <p><strong>상태</strong> · {escape(action.status)} / <strong>선행</strong> · {escape(dependencies)}</p>
                    </article>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("생성된 실행계획이 없습니다.")
    if not presentation_mode:
        with st.expander("전체 실행계획과 상담 후보", expanded=False):
            detailed._render_action_tab(run)
            st.divider()
            detailed._render_product_tab(run)


def _render_validation_status() -> None:
    status = build_competition_validation_status()
    st.markdown(
        f"""
        <div class="tg-validation">
          <div class="tg-validation-card"><strong>{status.governed_rule_count}</strong><span>결정론적 Rule</span></div>
          <div class="tg-validation-card"><strong>{status.gold_case_count}</strong><span>명시적 Gold Case</span></div>
          <div class="tg-validation-card"><strong>{status.mutation_case_count}</strong><span>의미보존 Mutation</span></div>
          <div class="tg-validation-card"><strong>{status.demo_scenario_count}</strong><span>대표 시나리오</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(status.authority_boundary)


def _render_qr() -> None:
    public_url = _public_demo_url()
    if public_url is None:
        st.info(
            "HTTPS 공개 주소가 설정되면 이 영역에 모바일 접속 QR이 표시됩니다. "
            "배포 환경에 `TRADEGUARD_PUBLIC_DEMO_URL`을 설정하십시오."
        )
        return
    qr_png = build_public_demo_qr_png(public_url)
    normalized = normalize_public_demo_url(public_url)
    left, right = st.columns([1, 3])
    with left:
        st.image(qr_png, width=170)
    with right:
        st.markdown("### 모바일 공개 데모")
        st.write("QR을 스캔하면 HTTPS 합성 데모를 휴대폰에서 바로 엽니다.")
        st.code(normalized, language=None)
        st.caption("공개 데모에서는 실제 문서 업로드, Live AI, API Key 입력과 고객정보 저장을 제공하지 않습니다.")


def _render_audit(run, scenario_id: str) -> None:
    st.markdown('<div id="audit" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">08 · 검증 현황과 감사 Snapshot</div>', unsafe_allow_html=True)
    _render_validation_status()
    st.divider()
    snapshot = build_presentation_snapshot_v2(run, scenario_id=scenario_id)
    html = render_presentation_snapshot_html(snapshot)
    left, right = st.columns(2)
    left.download_button(
        "발표용 HTML 저장",
        data=html.encode("utf-8"),
        file_name="kb-tradeguard-competition-snapshot.html",
        mime="text/html",
        use_container_width=True,
    )
    right.download_button(
        "감사 JSON 저장",
        data=(
            __import__("json").dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8"),
        file_name="kb-tradeguard-competition-snapshot.json",
        mime="application/json",
        use_container_width=True,
    )
    with st.expander("Case hash 및 전체 감사 산출물", expanded=False):
        package = st.session_state.get("competition_package")
        if package is not None:
            detailed._render_audit_tab(run, package, scenario_id)
    st.divider()
    _render_qr()


def _render_bottom_nav() -> None:
    st.markdown(
        """
        <nav class="tg-bottom-nav" aria-label="공모전 데모 주요 구역">
          <a href="#summary" target="_self">요약</a>
          <a href="#evidence" target="_self">근거</a>
          <a href="#actions" target="_self">실행</a>
          <a href="#portfolio" target="_self">포트폴리오</a>
          <a href="#products" target="_self">금융지원</a>
          <a href="#data" target="_self">공식데이터</a>
          <a href="#audit" target="_self">감사</a>
        </nav>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="KB TradeGuard AI · 공모전 데모",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    presentation_mode = _flag("presentation")
    mode_class = "tg-presentation" if presentation_mode else ""
    st.markdown(detailed.APP_CSS + v2.V2_CSS + COMPETITION_CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="{mode_class}">', unsafe_allow_html=True)
    _render_hero()
    render_workflow_map()

    scenario_id = _query_scenario_id()
    if not presentation_mode:
        scenario_id = _render_scenario_control(scenario_id)
    run = _ensure_run(scenario_id)
    narrative = scenario_narrative(scenario_id)
    if narrative is not None and not presentation_mode:
        st.caption(f"결정 질문 · {narrative.decision_question}")

    _render_verdict(run)
    _render_risks(run, presentation_mode=presentation_mode)
    _render_actions(run, presentation_mode=presentation_mode)
    render_portfolio_section(presentation_mode=presentation_mode)
    render_product_consultation_section(run, presentation_mode=presentation_mode)
    render_official_case_study_section(presentation_mode=presentation_mode)
    render_official_data_section(presentation_mode=presentation_mode)
    if not presentation_mode:
        _render_audit(run, scenario_id)
        _render_bottom_nav()
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
