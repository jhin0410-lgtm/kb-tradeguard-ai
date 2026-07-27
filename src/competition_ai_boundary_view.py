"""Competition-facing explanation of the AI and deterministic responsibility split."""

from __future__ import annotations

import streamlit as st


AI_BOUNDARY_CSS = """
<style>
.tg-ai-boundary {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.6rem;margin:.55rem 0 .75rem;}
.tg-ai-layer {border:1px solid #dce4ef;border-radius:17px;padding:.86rem;background:#fff;min-height:174px;}
.tg-ai-layer[data-layer="ai"] {border-top:5px solid #7554aa;}
.tg-ai-layer[data-layer="engine"] {border-top:5px solid #1b63e9;}
.tg-ai-layer[data-layer="human"] {border-top:5px solid #147455;}
.tg-ai-layer small {display:block;font-size:.63rem;font-weight:900;letter-spacing:.08em;color:#748198;}
.tg-ai-layer h3 {margin:.34rem 0 .38rem;font-size:.94rem;color:#172033;}
.tg-ai-layer p {margin:.25rem 0;color:#647084;font-size:.75rem;line-height:1.48;}
.tg-ai-mode-note {border:1px dashed #9aabc2;border-radius:14px;padding:.7rem .8rem;background:#f8fafc;color:#59677c;font-size:.74rem;line-height:1.48;}
@media(max-width:760px) {.tg-ai-boundary {grid-template-columns:1fr;}.tg-ai-layer {min-height:auto;}}
</style>
"""


def render_ai_boundary_section(*, presentation_mode: bool) -> None:
    """Explain what AI may do and what remains deterministic or human-controlled."""

    st.markdown(AI_BOUNDARY_CSS, unsafe_allow_html=True)
    st.markdown('<div id="ai" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tg-section-title">04 · AI 적용 구조와 신뢰 경계</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="tg-ai-boundary">
          <article class="tg-ai-layer" data-layer="ai">
            <small>AI ASSIST · 선택형</small>
            <h3>비정형 정보의 구조화와 근거 기반 설명</h3>
            <p>계약·송장·L/C에서 검토 후보 필드를 추출하고, 확정된 룰·계산·근거 ID를 사용해 상담용 자연어 설명을 작성하는 역할입니다.</p>
            <p>금액 계산, 승인, 적격성, 제재 해소 또는 법률 결론을 생성하지 않습니다.</p>
          </article>
          <article class="tg-ai-layer" data-layer="engine">
            <small>DETERMINISTIC ENGINE · 권위 계층</small>
            <h3>문서 정합성·환노출·재무감내·상품 연결</h3>
            <p>버전이 고정된 룰, 공식 데이터 Snapshot, 명시적 계산식과 공개 상품조건만으로 결과와 Action Plan을 생성합니다.</p>
            <p>동일한 검토 입력은 동일한 결과와 감사 식별자를 만들도록 설계했습니다.</p>
          </article>
          <article class="tg-ai-layer" data-layer="human">
            <small>HUMAN REVIEW · 최종 통제</small>
            <h3>원문 확인과 금융기관 상담·의사결정</h3>
            <p>추출 필드 승인, 누락정보 보완, 원문 검토, 바이어 실사, 상품 적격성·가격·한도 확인은 사용자와 전문가가 담당합니다.</p>
            <p>시스템은 상담 준비를 돕지만 거래 또는 금융상품 실행을 대신하지 않습니다.</p>
          </article>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not presentation_mode:
        st.markdown(
            '<div class="tg-ai-mode-note"><strong>현재 공개 모드</strong> · 합성 거래와 결정론적 결과를 재현하는 데 집중하며 외부 생성형 AI 호출은 OFF입니다. 모델이 설정된 상세 검토 환경에서도 완료된 결과를 인용해 설명하는 범위로 제한됩니다.</div>',
            unsafe_allow_html=True,
        )
