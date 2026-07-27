"""Mobile-first presentation entrypoint for KB TradeGuard AI Product UI V2.

This entrypoint reuses the deterministic assessment pipeline and V2 governed view
models. It only changes information density, navigation, and the location of the
primary run control for phone and presentation use.
"""

from __future__ import annotations

import streamlit as st

import assessment_app as detailed
import assessment_app_v2 as v2
from src.assessment_app_presentation import scenario_narrative
from src.demo_scenarios import list_demo_scenarios
from src.intelligence.single_transaction_package import run_single_transaction_package


MOBILE_POLISH_CSS = """
<style>
[data-testid="stAppDeployButton"] {display: none;}
.block-container {
  max-width: 920px;
  padding-top: 1.35rem;
  padding-left: .72rem;
  padding-right: .72rem;
  padding-bottom: 6.5rem;
}
.v21-hero {
  padding: 1.15rem 1.15rem 1.2rem;
  border-radius: 19px;
  color: #fff;
  background: radial-gradient(circle at 88% 12%, rgba(29,196,213,.38), transparent 36%),
              linear-gradient(128deg, #071a34 0%, #114782 62%, #0b7d91 100%);
  box-shadow: 0 12px 30px rgba(6,22,45,.17);
  margin-top: .2rem;
}
.v21-hero small {
  display: block;
  margin-bottom: .5rem;
  font-size: .65rem;
  letter-spacing: .09em;
  font-weight: 800;
  opacity: .76;
}
.v21-hero h1 {
  margin: 0 0 .62rem;
  font-size: 1.72rem;
  line-height: 1.2;
  letter-spacing: -.025em;
}
.v21-hero p {
  margin: 0;
  font-size: .88rem;
  line-height: 1.55;
  opacity: .94;
}
.v21-pill-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: .45rem;
  margin: .62rem 0 .8rem;
}
.v21-pill {
  border: 1px solid #dce4ef;
  border-radius: 13px;
  background: #fff;
  padding: .62rem .65rem;
  min-height: 72px;
}
.v21-pill strong {
  display: block;
  color: #172033;
  font-size: .78rem;
  margin-bottom: .16rem;
}
.v21-pill span {
  display: block;
  color: #66748a;
  font-size: .68rem;
  line-height: 1.38;
}
.v21-scenario {
  border: 1px solid #dce4ef;
  border-left: 5px solid #1a63e8;
  border-radius: 16px;
  background: #fff;
  padding: .9rem .95rem;
  margin: .7rem 0 .65rem;
}
.v21-scenario h3 {
  margin: 0 0 .4rem;
  color: #172033;
  font-size: 1rem;
}
.v21-scenario p {
  margin: .2rem 0;
  color: #5f6e83;
  font-size: .76rem;
  line-height: 1.46;
}
.v21-flow {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: .55rem;
  margin: .8rem 0;
}
.v21-step {
  border: 1px solid #394252;
  border-radius: 15px;
  padding: .8rem;
  min-height: 126px;
  background: rgba(255,255,255,.015);
}
.v21-step strong {
  display: block;
  font-size: .93rem;
  margin-bottom: .38rem;
}
.v21-step span {
  color: #b7beca;
  font-size: .72rem;
  line-height: 1.45;
}
.v21-run-note {
  border: 1px solid rgba(25,99,232,.36);
  border-radius: 13px;
  padding: .68rem .78rem;
  background: rgba(25,99,232,.1);
  color: #b8cdf8;
  font-size: .72rem;
  line-height: 1.45;
  margin-top: .55rem;
}
.v21-mode-label {
  margin: .8rem 0 .35rem;
  color: #7e8da2;
  font-size: .67rem;
  font-weight: 800;
  letter-spacing: .1em;
}
@media (max-width: 640px) {
  .block-container {padding-top: 1.8rem;}
  .v21-hero {padding: 1rem; border-radius: 17px;}
  .v21-hero small {font-size: .59rem; line-height: 1.35;}
  .v21-hero h1 {font-size: 1.52rem; line-height: 1.22;}
  .v21-hero p {font-size: .8rem;}
  .v21-pill-grid {grid-template-columns: 1fr 1fr 1fr; gap: .35rem;}
  .v21-pill {padding: .52rem; min-height: 66px;}
  .v21-pill strong {font-size: .7rem;}
  .v21-pill span {font-size: .6rem;}
  .v21-flow {grid-template-columns: 1fr 1fr; gap: .42rem;}
  .v21-step {padding: .68rem; min-height: 116px;}
  .v21-step strong {font-size: .82rem;}
  .v21-step span {font-size: .65rem;}
  .v2-risk-card {min-height: auto; padding: .84rem;}
  .v2-action-card {min-height: auto; padding: .82rem;}
  .v2-section-label {margin-top: .8rem;}
  [data-testid="stMetricValue"] {font-size: 1.35rem;}
  [data-testid="stMetricLabel"] {font-size: .7rem;}
  button[kind="primary"] {min-height: 49px; font-size: .94rem; font-weight: 800;}
}
</style>
"""


def _clear_live_ai_state() -> None:
    for key in (
        "live_ai_packet",
        "live_ai_execution",
        "live_ai_error",
        "live_ai_case_hash",
    ):
        st.session_state.pop(key, None)


def _execute_from_main(package, source_key: str | None) -> None:
    try:
        with st.spinner("문서·정합성·재무·상품·Brief를 순서대로 실행합니다."):
            run = run_single_transaction_package(package)
    except Exception as exc:
        st.session_state.pop("assessment_run", None)
        st.session_state.pop("assessment_package", None)
        st.error(f"평가 실행이 중단되었습니다: {exc}")
    else:
        st.session_state["assessment_run"] = run
        st.session_state["assessment_package"] = package
        st.session_state["assessment_source_key"] = source_key
        _clear_live_ai_state()


def _render_mobile_header() -> None:
    st.markdown(detailed.APP_CSS + v2.V2_CSS + MOBILE_POLISH_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <section class="v21-hero">
          <small>KB TRADEGUARD AI · PRODUCT UI V2 · MOBILE COMPACT</small>
          <h1>거래 전 위험과 다음 행동을 60초 안에 확인합니다</h1>
          <p>기업·거래·바이어·국가·계약조건을 하나의 결정론적 Brief로 연결하고, 핵심 판단을 Reference ID와 감사 식별자로 추적합니다.</p>
        </section>
        <div class="v21-pill-grid">
          <div class="v21-pill"><strong>Risk-first</strong><span>상위 위험부터</span></div>
          <div class="v21-pill"><strong>Evidence</strong><span>근거 레코드 연결</span></div>
          <div class="v21-pill"><strong>Audit</strong><span>Case hash 보존</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "사전검사·상담 준비용 합성 데모입니다. 승인·법률의견·제재 해소·금리·한도·상품 적격성을 확정하지 않습니다."
    )


def _selected_metadata(source_key: str | None):
    return next(
        (item for item in list_demo_scenarios() if item.scenario_id == source_key),
        None,
    )


def _render_compact_scenario(source_key: str | None) -> None:
    metadata = _selected_metadata(source_key)
    narrative = scenario_narrative(source_key)
    if metadata is None or narrative is None:
        return
    st.markdown(
        f"""
        <section class="v21-scenario">
          <h3>{metadata.highlight}</h3>
          <p><strong>업무 문제</strong> · {narrative.business_problem}</p>
          <p><strong>결정 질문</strong> · {narrative.decision_question}</p>
          <p><strong>심사 포인트</strong> · {narrative.judge_watch}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_mobile_landing(package, source_key: str | None) -> None:
    _render_compact_scenario(source_key)
    if package is not None:
        if st.button(
            "이 거래 5단계 사전진단 시작",
            type="primary",
            use_container_width=True,
        ):
            _execute_from_main(package, source_key)
            st.rerun()
        st.markdown(
            '<div class="v21-run-note">휴대폰에서는 사이드바를 열지 않아도 위 버튼으로 바로 실행할 수 있습니다. 같은 Package는 같은 결정론적 Case·Brief 결과를 생성합니다.</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="v21-mode-label">PRODUCT UI V2 · 4 STEP FLOW</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="v21-flow">
          <div class="v21-step"><strong>1 · 거래 입력</strong><span>합성 대표 거래 또는 검토된 JSON Package 선택</span></div>
          <div class="v21-step"><strong>2 · 60초 Brief</strong><span>판정·상위 위험 3개·다음 행동 3개 우선 확인</span></div>
          <div class="v21-step"><strong>3 · Evidence Drawer</strong><span>Reference ID에서 문서·계산·국가·바이어 근거로 이동</span></div>
          <div class="v21-step"><strong>4 · 감사 Snapshot</strong><span>Case hash와 발표용 HTML·JSON 저장</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="KB TradeGuard AI · Mobile V2",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.query_params["view"] = "compact"
    _render_mobile_header()

    package, source_key = detailed._select_package()
    detailed._run_controls(package, source_key)

    run = st.session_state.get("assessment_run")
    executed_package = st.session_state.get("assessment_package")
    executed_source_key = st.session_state.get("assessment_source_key")
    if run is None or executed_package is None:
        _render_mobile_landing(package, source_key)
        return

    v2._render_compact_results(run, executed_package, executed_source_key)


if __name__ == "__main__":
    main()
