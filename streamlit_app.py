"""Canonical isolated deployment entrypoint for the competition demo."""

from __future__ import annotations

import json
import os

import streamlit as st

import competition_app as app
from src.competition_ai_boundary_view import render_ai_boundary_section
from src.competition_case_study_view import render_official_case_study_section
from src.competition_portfolio_view import render_portfolio_section, render_workflow_map
from src.competition_evaluation import build_internal_trade_document_benchmark
from src.competition_product_view import render_product_consultation_section
from src.competition_real_data_view import render_official_data_section
from src.competition_topic6 import prepare_topic6_demo_package
from src.demo_scenarios import DemoScenarioMetadata


PUBLIC_DEMO_URL = "https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/"

# The public URL is not a secret. An explicit deployment environment value can still
# override it if the app is moved or renamed later.
os.environ.setdefault("TRADEGUARD_PUBLIC_DEMO_URL", PUBLIC_DEMO_URL)

# competition_app originally called the display field ``label`` while the governed
# metadata contract names it ``title``. Keep the deployment entrypoint backward
# compatible without changing scenario content or deterministic assessment behavior.
if not hasattr(DemoScenarioMetadata, "label"):
    DemoScenarioMetadata.label = property(lambda item: item.title)  # type: ignore[attr-defined]


def _secret_to_environment(name: str) -> None:
    """Expose an explicitly configured Streamlit secret to read-only providers."""

    if os.getenv(name):
        return
    try:
        value = str(st.secrets.get(name, "")).strip()
    except Exception:
        value = ""
    if value:
        os.environ[name] = value


def _ensure_topic6_run(scenario_id: str):
    run = st.session_state.get("competition_run")
    active = st.session_state.get("competition_scenario_id")
    if run is not None and active == scenario_id:
        return run
    package = prepare_topic6_demo_package(app.load_demo_scenario(scenario_id))
    with st.spinner("검토된 합성 거래와 명시적 외환관리 필요를 결정론적으로 분석합니다."):
        run = app.run_single_transaction_package(package)
    st.session_state["competition_run"] = run
    st.session_state["competition_package"] = package
    st.session_state["competition_scenario_id"] = scenario_id
    return run


def _render_internal_benchmark() -> None:
    metrics = build_internal_trade_document_benchmark()
    st.markdown("#### 내부 합성 회귀평가")
    exact_rate = f"{metrics.exact_match_rate * 100:.1f}%"
    columns = st.columns(4)
    columns[0].metric("Rule-ID 완전일치", exact_rate)
    columns[1].metric("검토 Fixture", metrics.case_count)
    columns[2].metric("추가 탐지", metrics.false_positive_rule_count)
    columns[3].metric("누락 탐지", metrics.false_negative_rule_count)
    st.caption(
        "프로젝트가 작성하고 사람이 검토한 구조화 합성 Fixture에 대한 회귀 결과입니다. "
        "외부 원문 문서 정확도, 법률 검토 일치율, 신용성과 또는 운영 적합성을 뜻하지 않습니다."
    )


def _render_audit(run, scenario_id: str) -> None:
    st.markdown('<div id="audit" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tg-section-title">08 · 검증 현황과 감사 기록</div>',
        unsafe_allow_html=True,
    )
    app._render_validation_status()
    _render_internal_benchmark()
    st.divider()
    snapshot = app.build_presentation_snapshot_v2(run, scenario_id=scenario_id)
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
        data=(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
        file_name="kb-tradeguard-competition-snapshot.json",
        mime="application/json",
        use_container_width=True,
    )
    with st.expander("Case hash 및 전체 감사 산출물", expanded=False):
        package = st.session_state.get("competition_package")
        if package is not None:
            app.detailed._render_audit_tab(run, package, scenario_id)
    st.divider()
    app._render_qr()


def _render_bottom_nav() -> None:
    st.markdown(
        """
        <nav class="tg-bottom-nav" aria-label="공모전 데모 주요 구역">
          <a href="#summary" target="_self">요약</a>
          <a href="#evidence" target="_self">근거</a>
          <a href="#actions" target="_self">실행</a>
          <a href="#ai" target="_self">AI</a>
          <a href="#products" target="_self">상품</a>
          <a href="#data" target="_self">데이터</a>
          <a href="#audit" target="_self">감사</a>
        </nav>
        """,
        unsafe_allow_html=True,
    )


def _render_competition_page() -> None:
    presentation_mode = app._flag("presentation")
    mode_class = "tg-presentation" if presentation_mode else ""
    st.markdown(
        app.detailed.APP_CSS + app.v2.V2_CSS + app.COMPETITION_CSS,
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="{mode_class}">', unsafe_allow_html=True)
    app._render_hero()
    render_workflow_map()

    scenario_id = app._query_scenario_id()
    if not presentation_mode:
        scenario_id = app._render_scenario_control(scenario_id)
    run = _ensure_topic6_run(scenario_id)
    narrative = app.scenario_narrative(scenario_id)
    if narrative is not None and not presentation_mode:
        st.caption(f"결정 질문 · {narrative.decision_question}")

    app._render_verdict(run)
    app._render_risks(run, presentation_mode=presentation_mode)
    app._render_actions(run, presentation_mode=presentation_mode)
    render_portfolio_section(presentation_mode=presentation_mode)
    render_ai_boundary_section(presentation_mode=presentation_mode)
    render_product_consultation_section(run, presentation_mode=presentation_mode)
    render_official_case_study_section(presentation_mode=presentation_mode)
    render_official_data_section(presentation_mode=presentation_mode)
    if not presentation_mode:
        _render_audit(run, scenario_id)
        _render_bottom_nav()
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    # Explicit navigation prevents Streamlit from auto-publishing legacy modules in
    # pages/. Only this governed competition page is registered in the deployment.
    st.set_page_config(
        page_title="KB TradeGuard AI · 공모전 데모",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    for key in ("KEXIM_API_KEY", "KCS_TRADE_API_KEY", "DATA_GO_KR_SERVICE_KEY"):
        _secret_to_environment(key)
    page = st.Page(
        _render_competition_page,
        title="KB TradeGuard AI",
        icon="🛡️",
        default=True,
    )
    st.navigation([page], position="hidden").run()


if __name__ == "__main__":
    main()
