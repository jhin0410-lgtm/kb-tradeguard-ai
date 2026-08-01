"""Unified KB TradeGuard AI product entrypoint.

One command exposes the complete product shell. Public deployments default to a
synthetic read-only Decision Desk, while a reviewed-input Analyst Workspace can be
enabled explicitly for local or private environments. Portfolio, official data, and
audit views reuse the currently active governed case instead of unrelated samples.
"""
from __future__ import annotations

import json
import os
from html import escape
from typing import Any

import streamlit as st

import assessment_app as detailed
import competition_app as app
from src.competition_ai_boundary_view import render_ai_boundary_section
from src.competition_case_study_view import render_official_case_study_section
from src.competition_decision_cockpit import (
    render_decision_charts,
    render_decision_cockpit,
    render_guided_nav,
    render_kb_handoff,
    render_usability_evidence,
)
from src.competition_evaluation import build_internal_trade_document_benchmark
from src.competition_portfolio_view import render_portfolio_section, render_workflow_map
from src.competition_product_view import render_product_consultation_section
from src.competition_real_data_view import render_official_data_section
from src.competition_topic6 import prepare_topic6_demo_package
from src.demo_scenarios import DemoScenarioMetadata

PUBLIC_DEMO_URL = "https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/"
_MODE_LABELS = {
    "decision": "Decision Desk",
    "analyst": "Analyst Workspace",
    "portfolio": "Portfolio & Official Data",
    "evidence": "Evidence & Submission",
}

UNIFIED_CSS = """
<style>
:root{--kb-yellow:#ffcc00;--kb-navy:#111827;--kb-blue:#2563eb;--kb-cyan:#0891b2;--kb-line:#d8e0eb;--kb-muted:#64748b;--kb-soft:#f5f7fb}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0b1424,#101c31);border-right:1px solid rgba(255,255,255,.08)}
[data-testid="stSidebar"] *{color:#eaf0fb}
[data-testid="stSidebar"] [data-baseweb="radio"]>div{gap:.35rem}
[data-testid="stSidebar"] label{font-weight:750}
.block-container{max-width:1320px;padding-top:1rem;padding-bottom:6rem}
.tg-product-shell{display:flex;align-items:center;justify-content:space-between;gap:1rem;border:1px solid var(--kb-line);border-radius:18px;padding:.72rem .9rem;background:rgba(255,255,255,.94);box-shadow:0 10px 28px rgba(15,23,42,.07);margin-bottom:.8rem;position:sticky;top:.55rem;z-index:20;backdrop-filter:blur(12px)}
.tg-product-brand{display:flex;align-items:center;gap:.7rem}.tg-product-mark{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,var(--kb-yellow),#ff9d00);display:grid;place-items:center;color:#151515;font-weight:950}.tg-product-brand strong{display:block;font-size:.94rem;color:#152033}.tg-product-brand span{display:block;font-size:.68rem;color:var(--kb-muted);margin-top:.08rem}.tg-mode-pill{border-radius:999px;background:#edf4ff;color:#174ea6;padding:.43rem .7rem;font-size:.69rem;font-weight:900;white-space:nowrap}
.tg-mode-intro{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(260px,.6fr);gap:.75rem;margin:.6rem 0 1rem}.tg-mode-copy,.tg-mode-context{border:1px solid var(--kb-line);border-radius:18px;background:#fff;padding:1rem}.tg-mode-copy small{font-size:.64rem;letter-spacing:.11em;color:#64748b;font-weight:900}.tg-mode-copy h2{margin:.25rem 0 .3rem;font-size:1.25rem;color:#172033}.tg-mode-copy p,.tg-mode-context p{margin:.15rem 0;color:#64748b;font-size:.78rem;line-height:1.5}.tg-mode-context strong{display:block;color:#172033;font-size:.76rem;margin-bottom:.25rem}
.tg-case-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.45rem;margin:.55rem 0 1rem}.tg-case-item{border:1px solid var(--kb-line);border-radius:14px;padding:.68rem;background:#fff}.tg-case-item small{display:block;color:#7b8799;font-size:.61rem;font-weight:900}.tg-case-item strong{display:block;color:#172033;font-size:.79rem;margin-top:.16rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tg-section-panel{border:1px solid var(--kb-line);border-radius:20px;background:#fff;padding:1rem;margin:.8rem 0;box-shadow:0 8px 22px rgba(15,23,42,.045)}
.tg-subnav{display:flex;gap:.4rem;flex-wrap:wrap;margin:.7rem 0 1rem}.tg-subnav a{text-decoration:none;border:1px solid var(--kb-line);border-radius:999px;padding:.48rem .76rem;color:#334155;font-size:.7rem;font-weight:850;background:#fff}.tg-subnav a:hover{border-color:#8eb4ef;background:#f1f6ff}
.tg-private-note{border:1px solid #f0d37a;border-left:6px solid #d49c00;border-radius:16px;padding:.78rem .9rem;background:#fff9df;color:#655b3b;font-size:.75rem;line-height:1.5;margin:.65rem 0}
@media(max-width:760px){.tg-mode-intro{grid-template-columns:1fr}.tg-case-strip{grid-template-columns:1fr 1fr}.tg-product-shell{align-items:flex-start;position:static}.tg-product-brand span{display:none}}
</style>
"""

if not hasattr(DemoScenarioMetadata, "label"):
    DemoScenarioMetadata.label = property(lambda item: item.title)  # type: ignore[attr-defined]


def _secret_to_environment(name: str) -> None:
    if os.getenv(name):
        return
    try:
        value = str(st.secrets.get(name, "")).strip()
    except Exception:
        value = ""
    if value:
        os.environ[name] = value


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _private_workspace_enabled() -> bool:
    """Private upload/review mode is opt-in and disabled on the public demo."""
    return _env_flag("TRADEGUARD_ENABLE_PRIVATE_WORKSPACE")


def _query_value(name: str, default: str = "") -> str:
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        value = value[0] if value else default
    return str(value)


def _available_modes() -> list[str]:
    modes = ["decision", "portfolio", "evidence"]
    if _private_workspace_enabled():
        modes.insert(1, "analyst")
    return modes


def _active_mode() -> str:
    requested = _query_value("mode", "decision").strip().lower()
    if app._flag("presentation"):
        return "decision"
    return requested if requested in _available_modes() else "decision"


def _render_product_shell(mode: str) -> None:
    st.markdown(UNIFIED_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <header class="tg-product-shell">
          <div class="tg-product-brand">
            <div class="tg-product-mark">KB</div>
            <div><strong>KB TradeGuard AI</strong><span>Transaction intelligence · evidence · financial-support workflow</span></div>
          </div>
          <div class="tg-mode-pill">{escape(_MODE_LABELS[mode])}</div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def _render_mode_selector(active: str) -> str:
    options = _available_modes()
    with st.sidebar:
        st.markdown("## KB TradeGuard AI")
        st.caption("하나의 앱에서 거래 판정, 포트폴리오·공식 데이터와 제출 증거까지 이동합니다.")
        selected = st.radio(
            "업무 모드",
            options=options,
            index=options.index(active),
            format_func=lambda item: _MODE_LABELS[item],
            key="unified_product_mode",
        )
        st.divider()
        if _private_workspace_enabled():
            st.success("Private Workspace 활성화")
            st.caption("검토된 JSON Package와 선택형 Live AI는 로컬·제한 배포에서만 사용합니다.")
        else:
            st.info("Public Demo 안전 모드")
            st.caption("문서 업로드·Live AI 입력은 비활성화되어 있습니다.")
        if selected != active:
            st.query_params["mode"] = selected
            st.rerun()
    return selected


def _ensure_topic6_run(scenario_id: str):
    run = st.session_state.get("competition_run")
    active = st.session_state.get("competition_scenario_id")
    package = st.session_state.get("competition_package")
    if run is not None and active == scenario_id and package is not None:
        return run
    package = prepare_topic6_demo_package(app.load_demo_scenario(scenario_id))
    with st.spinner("검토된 합성 거래와 명시적 외환관리 필요를 결정론적으로 분석합니다."):
        run = app.run_single_transaction_package(package)
    st.session_state["competition_run"] = run
    st.session_state["competition_package"] = package
    st.session_state["competition_scenario_id"] = scenario_id
    return run


def _active_governed_context() -> tuple[Any, Any, str, str]:
    """Return the active run, package, source key, and origin for connected modes."""
    if _private_workspace_enabled():
        analyst_run = st.session_state.get("assessment_run")
        analyst_package = st.session_state.get("assessment_package")
        if analyst_run is not None and analyst_package is not None:
            source_key = str(st.session_state.get("assessment_source_key") or "reviewed-package")
            return analyst_run, analyst_package, source_key, "Analyst Workspace"
    scenario_id = app._query_scenario_id()
    run = _ensure_topic6_run(scenario_id)
    package = st.session_state["competition_package"]
    return run, package, scenario_id, "Decision Desk"


def _render_case_strip(run: Any, source_key: str, *, origin: str = "Decision Desk") -> None:
    case = run.updated_case
    identity = getattr(case, "identity", None)
    company = getattr(identity, "company_name", None) or "합성 수출입기업"
    transactions = list(getattr(case, "approved_transactions", []) or [])
    first = transactions[0] if transactions else {}
    country = (
        first.get("counterparty_country")
        or first.get("country_code")
        or first.get("destination_country")
        or first.get("origin_country")
        or "확인 필요"
    )
    disposition = run.assessment_result.brief.disposition
    st.markdown(
        f"""
        <div class="tg-case-strip">
          <div class="tg-case-item"><small>ACTIVE COMPANY</small><strong>{escape(str(company))}</strong></div>
          <div class="tg-case-item"><small>CONTEXT ORIGIN</small><strong>{escape(origin)}</strong></div>
          <div class="tg-case-item"><small>COUNTRY / TRANSACTIONS</small><strong>{escape(str(country))} · {len(transactions)}건</strong></div>
          <div class="tg-case-item"><small>GOVERNED DISPOSITION</small><strong>{escape(str(disposition))}</strong></div>
        </div>
        <div style="display:none">{escape(source_key)}</div>
        """,
        unsafe_allow_html=True,
    )


def _render_internal_benchmark() -> None:
    metrics = build_internal_trade_document_benchmark()
    st.markdown("#### 내부 합성 회귀평가")
    columns = st.columns(4)
    columns[0].metric("Rule-ID 완전일치", f"{metrics.exact_match_rate * 100:.1f}%")
    columns[1].metric("검토 Fixture", metrics.case_count)
    columns[2].metric("추가 탐지", metrics.false_positive_rule_count)
    columns[3].metric("누락 탐지", metrics.false_negative_rule_count)
    st.caption("구조화 합성 Fixture의 회귀 결과이며 외부 원문 정확도나 금융승인을 뜻하지 않습니다.")


def _render_presentation_evidence(run: Any) -> None:
    st.markdown('<div id="final-audit" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">05 · 근거·검증</div>', unsafe_allow_html=True)
    app._render_validation_status()
    st.caption(
        f"입력 Package hash {run.input_package_hash[:16]}… · 출력 Case hash {run.output_case_hash[:16]}… · Hash는 변경 추적 식별자입니다."
    )


def _render_audit(run: Any, package: Any, source_key: str) -> None:
    st.markdown('<div id="final-audit" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">06 · 근거·검증·감사</div>', unsafe_allow_html=True)
    app._render_validation_status()
    _render_internal_benchmark()
    render_usability_evidence()
    snapshot = app.build_presentation_snapshot_v2(run, scenario_id=source_key)
    html = app.render_presentation_snapshot_html(snapshot)
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
        data=(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        file_name="kb-tradeguard-competition-snapshot.json",
        mime="application/json",
        use_container_width=True,
    )
    with st.expander("Case hash·Stage Trace·전체 감사 산출물", expanded=False):
        detailed._render_audit_tab(run, package, source_key)
    app._render_qr()


def _render_connected_detail_tabs(run: Any) -> None:
    st.markdown('<div class="tg-section-title">05 · 문서·재무·실행 상세</div>', unsafe_allow_html=True)
    st.caption("공개 합성 거래에서도 실제 상세 엔진 결과를 확인할 수 있습니다.")
    document_tab, financial_tab, action_tab = st.tabs(["계약·L/C·정합성", "거래·재무 감내", "Action Plan"])
    with document_tab:
        detailed._render_document_tab(run)
    with financial_tab:
        detailed._render_financial_tab(run)
    with action_tab:
        detailed._render_action_tab(run)


def _render_decision_mode() -> None:
    presentation_mode = app._flag("presentation")
    mode_class = "tg-presentation" if presentation_mode else ""
    st.markdown(app.detailed.APP_CSS + app.v2.V2_CSS + app.COMPETITION_CSS, unsafe_allow_html=True)
    if not presentation_mode:
        st.markdown(
            "<style class='tg-unified-sidebar-override'>[data-testid='stSidebar']{display:block !important}[data-testid='stSidebarCollapsedControl']{display:flex !important}</style>",
            unsafe_allow_html=True,
        )
    st.markdown(f'<div class="{mode_class}">', unsafe_allow_html=True)
    app._render_hero()
    render_guided_nav()
    if not presentation_mode:
        with st.expander("거래 검토 전체 흐름", expanded=False):
            render_workflow_map()
    scenario_id = app._query_scenario_id()
    if not presentation_mode:
        scenario_id = app._render_scenario_control(scenario_id)
    run = _ensure_topic6_run(scenario_id)
    package = st.session_state["competition_package"]
    _render_case_strip(run, scenario_id)
    narrative = app.scenario_narrative(scenario_id)
    if narrative is not None and not presentation_mode:
        st.caption(f"결정 질문 · {narrative.decision_question}")
    st.markdown('<div class="tg-section-title">01 · 통합 거래 판정</div>', unsafe_allow_html=True)
    render_decision_cockpit(run, scenario_id)
    app._render_risks(run, presentation_mode=presentation_mode)
    render_decision_charts(run)
    render_product_consultation_section(run, presentation_mode=presentation_mode)
    render_kb_handoff(run)
    if presentation_mode:
        _render_presentation_evidence(run)
    else:
        _render_connected_detail_tabs(run)
        links = ["<a href='?mode=portfolio'>포트폴리오·공식데이터</a>", "<a href='?mode=evidence'>제출 증거</a>"]
        if _private_workspace_enabled():
            links.insert(0, "<a href='?mode=analyst'>검토 Package 열기</a>")
        st.markdown(f"<div class='tg-subnav'>{''.join(links)}</div>", unsafe_allow_html=True)
        _render_audit(run, package, scenario_id)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_analyst_mode() -> None:
    if not _private_workspace_enabled():
        st.error("Analyst Workspace는 로컬·Private 환경에서만 활성화됩니다.")
        st.code("$env:TRADEGUARD_ENABLE_PRIVATE_WORKSPACE='1'\npython -m streamlit run streamlit_app.py", language="powershell")
        return
    st.markdown(detailed.APP_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <section class="tg-mode-intro"><div class="tg-mode-copy"><small>PRIVATE / REVIEWED INPUT WORKSPACE</small><h2>문서·정합성·재무·상품·Action Plan 상세 검토</h2><p>공개 데모와 같은 결정론적 5단계 엔진을 사용하고, 검토된 JSON Package, Human Review Overlay, 상세 감사자료와 선택형 Grounded AI를 연결합니다.</p></div><div class="tg-mode-context"><strong>입력 원칙</strong><p>실제 고객 개인정보·원본문서·API Key는 공개 배포에 입력하지 않습니다. 로컬 또는 접근이 제한된 환경에서만 사용합니다.</p></div></section>
        <div class="tg-private-note"><strong>Private mode</strong> · 이 모드는 공개 Streamlit 배포에서 기본 비활성화됩니다.</div>
        """,
        unsafe_allow_html=True,
    )
    package, source_key = detailed._select_package()
    detailed._run_controls(package, source_key)
    run = st.session_state.get("assessment_run")
    executed_package = st.session_state.get("assessment_package")
    executed_source_key = st.session_state.get("assessment_source_key")
    if run is None or executed_package is None:
        detailed._render_landing(source_key)
        return
    _render_case_strip(run, str(executed_source_key or "reviewed-package"), origin="Analyst Workspace")
    detailed._render_results(run, executed_package, executed_source_key)
    st.markdown("<div class='tg-subnav'><a href='?mode=portfolio'>현재 Case 포트폴리오</a><a href='?mode=evidence'>현재 Case 감사증거</a></div>", unsafe_allow_html=True)


def _render_portfolio_mode() -> None:
    run, package, source_key, origin = _active_governed_context()
    st.markdown(
        f"""
        <section class="tg-mode-intro"><div class="tg-mode-copy"><small>CONNECTED CASE ANALYTICS</small><h2>현재 거래 Case를 포트폴리오·공식 데이터까지 이어서 검토</h2><p>{escape(origin)}에서 생성한 동일 Case를 통화별 노출, 월별 유동성, FX Stress, 금융지원과 공식 데이터 근거로 확장합니다.</p></div><div class="tg-mode-context"><strong>연결 상태</strong><p>별도 샘플을 다시 선택하지 않고 현재 활성 Case를 분석합니다.</p></div></section>
        """,
        unsafe_allow_html=True,
    )
    _render_case_strip(run, source_key, origin=origin)
    portfolio_tab, official_tab, controls_tab = st.tabs(["포트폴리오·외환", "국가·공식 데이터", "AI·통제 구조"])
    with portfolio_tab:
        render_portfolio_section(presentation_mode=False, case=run.updated_case)
    with official_tab:
        render_official_case_study_section(presentation_mode=False)
        previous_package = st.session_state.get("competition_package")
        st.session_state["competition_package"] = package
        try:
            render_official_data_section(presentation_mode=False)
        finally:
            if previous_package is None:
                st.session_state.pop("competition_package", None)
            else:
                st.session_state["competition_package"] = previous_package
    with controls_tab:
        render_ai_boundary_section(presentation_mode=False)


def _render_evidence_mode() -> None:
    run, package, source_key, origin = _active_governed_context()
    st.markdown(
        f"""
        <section class="tg-mode-intro"><div class="tg-mode-copy"><small>SUBMISSION & AUDIT EVIDENCE</small><h2>검증 결과·Case hash·오프라인 산출물을 한곳에서 관리</h2><p>{escape(origin)}의 현재 Case에 대한 재현성 증거와 제출용 파일을 직접 내려받습니다.</p></div><div class="tg-mode-context"><strong>검증 범위</strong><p>저장소 내부 일관성·회귀검증을 증명하며 실제 사용자 효과, 법률 정확성, 은행 승인이나 상품 적격성을 증명하지 않습니다.</p></div></section>
        """,
        unsafe_allow_html=True,
    )
    _render_case_strip(run, source_key, origin=origin)
    _render_audit(run, package, source_key)


def main() -> None:
    st.set_page_config(
        page_title="KB TradeGuard AI",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    for key in (
        "KEXIM_API_KEY",
        "KCS_TRADE_API_KEY",
        "DATA_GO_KR_SERVICE_KEY",
        "TRADEGUARD_PUBLIC_DEMO_URL",
        "TRADEGUARD_ENABLE_PRIVATE_WORKSPACE",
    ):
        _secret_to_environment(key)
    os.environ.setdefault("TRADEGUARD_PUBLIC_DEMO_URL", PUBLIC_DEMO_URL)
    mode = _active_mode()
    _render_product_shell(mode)
    if not app._flag("presentation"):
        mode = _render_mode_selector(mode)
    if mode == "decision":
        _render_decision_mode()
    elif mode == "analyst":
        _render_analyst_mode()
    elif mode == "portfolio":
        _render_portfolio_mode()
    else:
        _render_evidence_mode()


if __name__ == "__main__":
    main()
