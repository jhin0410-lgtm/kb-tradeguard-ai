"""Decision-first public competition UI for KB TradeGuard AI.

This module stays presentation-only: it consumes reviewed deterministic outputs and
never performs financial calculations or provider calls.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

COCKPIT_CSS = """
<style>
.tg-cockpit{border:1px solid #d9e2ee;border-radius:22px;padding:1rem;background:linear-gradient(180deg,#fff,#f7faff);box-shadow:0 12px 34px rgba(15,36,68,.08);margin:.7rem 0 1rem}
.tg-cockpit-head{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;margin-bottom:.8rem}
.tg-cockpit-kicker{font-size:.67rem;letter-spacing:.1em;font-weight:900;color:#6d7b91}
.tg-cockpit-title{font-size:1.32rem;font-weight:900;color:#172033;margin:.22rem 0}
.tg-cockpit-sub{font-size:.78rem;color:#647084;line-height:1.45}
.tg-decision-pill{padding:.48rem .7rem;border-radius:999px;background:#fff1cc;color:#6b4b00;font-size:.72rem;font-weight:900;border:1px solid #f0d37a;white-space:nowrap}
.tg-kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.55rem}
.tg-kpi{border:1px solid #dce4ef;border-radius:15px;padding:.72rem;background:#fff}
.tg-kpi span{display:block;font-size:.64rem;color:#748198;font-weight:800}
.tg-kpi strong{display:block;margin-top:.22rem;font-size:1rem;color:#172033}
.tg-next-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.55rem;margin-top:.65rem}
.tg-next{border-radius:14px;padding:.72rem;background:#07172d;color:#fff;min-height:92px}
.tg-next b{display:block;font-size:.78rem;margin-bottom:.25rem}.tg-next span{font-size:.68rem;opacity:.82;line-height:1.4}
.tg-guide{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.5rem;margin:.8rem 0}
.tg-guide a{display:block;text-decoration:none;border:1px solid #dce4ef;border-radius:14px;padding:.7rem;background:#fff;color:#172033;font-size:.72rem;font-weight:900;text-align:center}
.tg-guide a:hover{border-color:#1b63e9;background:#f3f7ff}
.tg-chart-card{border:1px solid #dce4ef;border-radius:18px;padding:.85rem;background:#fff;margin:.55rem 0}
.tg-impact{border-left:5px solid #0d95aa;background:#f1fbfc;border-radius:12px;padding:.65rem .75rem;font-size:.72rem;color:#52627a;line-height:1.45;margin-top:.5rem}
.tg-handoff{border:1px solid #ead89b;background:#fff9df;border-radius:18px;padding:.9rem;margin:.75rem 0}
.tg-handoff strong{color:#4f3c00}.tg-handoff p{font-size:.74rem;color:#655b3b;margin:.3rem 0 0;line-height:1.48}
@media(max-width:760px){.tg-cockpit-head{display:block}.tg-decision-pill{display:inline-block;margin-top:.55rem}.tg-kpi-grid{grid-template-columns:1fr 1fr}.tg-next-grid{grid-template-columns:1fr}.tg-guide{grid-template-columns:1fr 1fr}.tg-cockpit-title{font-size:1.08rem}.tg-kpi strong{font-size:.88rem}}
</style>
"""


def _fmt_money(value: Any) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "확인 필요"
    if abs(n) >= 1_000_000_000:
        return f"₩{n/1_000_000_000:,.1f}bn"
    if abs(n) >= 1_000_000:
        return f"₩{n/1_000_000:,.1f}m"
    return f"₩{n:,.0f}"


def render_guided_nav() -> None:
    st.markdown(
        """
        <div class="tg-guide">
          <a href="#summary" target="_self">1 · 거래 판정</a>
          <a href="#scenarios" target="_self">2 · 시나리오</a>
          <a href="#products" target="_self">3 · 금융지원</a>
          <a href="#evidence" target="_self">4 · 근거·감사</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision_cockpit(run: Any, scenario_id: str) -> None:
    """Render a compact decision summary from already-reviewed run outputs."""
    case = getattr(run, "case", None) or getattr(run, "reviewed_case", None)
    txs = list(getattr(case, "transactions", []) or []) if case is not None else []
    tx = txs[0] if txs else None
    currency = getattr(tx, "currency", "USD") if tx is not None else "USD"
    amount = getattr(tx, "amount", None) if tx is not None else None
    country = getattr(tx, "counterparty_country", None) or getattr(tx, "country", None) or "해외"
    direction = getattr(tx, "direction", None) or getattr(tx, "trade_direction", None) or "수출입"

    disposition = getattr(run, "disposition", None)
    label = getattr(disposition, "label", None) or getattr(disposition, "title", None) or "조건 보완 후 진행"
    findings = list(getattr(run, "findings", []) or [])
    actions = list(getattr(run, "actions", []) or [])
    evidence = list(getattr(run, "evidence", []) or [])

    st.markdown(COCKPIT_CSS, unsafe_allow_html=True)
    st.markdown('<div id="summary" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <section class="tg-cockpit">
          <div class="tg-cockpit-head">
            <div>
              <div class="tg-cockpit-kicker">TRADE DECISION COCKPIT</div>
              <div class="tg-cockpit-title">{country} · {currency} {direction} 거래 검토</div>
              <div class="tg-cockpit-sub">거래금액 {_fmt_money(amount)} · 시나리오 {scenario_id} · 확정 전 핵심 위험과 다음 행동</div>
            </div>
            <div class="tg-decision-pill">{label}</div>
          </div>
          <div class="tg-kpi-grid">
            <div class="tg-kpi"><span>핵심 위험</span><strong>{min(len(findings), 3)}개 우선</strong></div>
            <div class="tg-kpi"><span>확인된 근거</span><strong>{len(evidence)}건</strong></div>
            <div class="tg-kpi"><span>우선 실행</span><strong>{min(len(actions), 3)}개</strong></div>
            <div class="tg-kpi"><span>신뢰 경계</span><strong>승인 아님</strong></div>
          </div>
          <div class="tg-next-grid">
            <div class="tg-next"><b>1. 거래상대방 확인</b><span>바이어·공급자 신용과 결제조건의 미확인 항목을 먼저 보완합니다.</span></div>
            <div class="tg-next"><b>2. 환노출·현금공백 점검</b><span>자연헤지 후 순노출과 수금 지연 시 유동성 영향을 확인합니다.</span></div>
            <div class="tg-next"><b>3. 금융지원 상담</b><span>보험·보증·외환·무역금융 후보와 필요서류를 상담 단계로 넘깁니다.</span></div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_decision_charts() -> None:
    """Render deterministic explanatory charts using labeled demo values only."""
    st.markdown('<div id="scenarios" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">02 · 시나리오와 현금흐름</div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        st.markdown('<div class="tg-chart-card"><b>FX 스트레스 · 기준 대비 원화가치</b>', unsafe_allow_html=True)
        st.bar_chart({"원화가치": [90, 95, 100, 105, 110]}, x_label="-10%   -5%   기준   +5%   +10%", y_label="지수")
        st.caption("설명용 정규화 지수입니다. 실제 거래 계산값은 Decision Brief의 계산 ID에서 확인합니다.")
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="tg-chart-card"><b>자연헤지 후 순노출 구조</b>', unsafe_allow_html=True)
        st.bar_chart({"금액지수": [100, -35, -15, 50]}, x_label="수출채권   수입채무   외화예금   순노출", y_label="지수")
        st.caption("총노출을 그대로 헤지하지 않고 반대 현금흐름과 외화자산을 먼저 차감합니다.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-chart-card"><b>예상 현금흐름 Timeline</b>', unsafe_allow_html=True)
    st.line_chart({"예상잔액": [100, 88, 61, 54, 96]}, x_label="계약   선적   수입대금   수금대기   수금", y_label="지수")
    st.caption("수금 지연 시 현금공백이 발생하는 구간을 먼저 확인하고 운전자금·채권금융 후보를 연결합니다.")
    st.markdown('</div>', unsafe_allow_html=True)


def render_kb_handoff() -> None:
    st.markdown(
        """
        <div class="tg-handoff">
          <strong>KB 상담 handoff</strong>
          <p><b>고객</b>은 위험과 준비서류를 미리 이해하고, <b>상담직원</b>은 거래·근거·미확인 조건이 정리된 Brief로 상담을 시작합니다. <b>KB</b>는 외환·무역금융·보험·보증 상담을 거래 맥락에 맞게 연결할 수 있습니다. 본 화면은 독립 공모전 prototype이며 실제 승인·금리·한도를 확정하지 않습니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_usability_evidence() -> None:
    with st.expander("사용성 검증 계획과 기록 양식", expanded=False):
        st.markdown(
            """
            **과제:** 사용자가 3분 안에 핵심 위험 3개와 다음 행동을 찾습니다.  
            **기록:** 완료시간, 정확한 행동 선택률, 이해되지 않은 용어, 불필요한 화면, 상담 의향.  
            **현재 상태:** 공개 데모에는 측정 프레임만 제공하며, 실제 참여자 결과를 임의 생성하지 않습니다.
            """
        )
