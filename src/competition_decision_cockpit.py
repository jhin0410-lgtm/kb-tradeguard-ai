"""Decision-first public competition UI for KB TradeGuard AI.

This module stays presentation-only: it consumes reviewed deterministic outputs and
never performs financial calculations or provider calls.
"""
from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
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
.tg-next b{display:block;font-size:.78rem;margin-bottom:.25rem}.tg-next span{font-size:.68rem;opacity:.82;line-height:1.4}.tg-next small{display:block;margin-top:.35rem;font-size:.59rem;opacity:.68}
.tg-guide{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.5rem;margin:.8rem 0}
.tg-guide a{display:block;text-decoration:none;border:1px solid #dce4ef;border-radius:14px;padding:.7rem;background:#fff;color:#172033;font-size:.72rem;font-weight:900;text-align:center}
.tg-guide a:hover{border-color:#1b63e9;background:#f3f7ff}
.tg-handoff{border:1px solid #ead89b;background:#fff9df;border-radius:18px;padding:.9rem;margin:.75rem 0}
.tg-handoff strong{color:#4f3c00}.tg-handoff p{font-size:.74rem;color:#655b3b;margin:.3rem 0 0;line-height:1.48}
@media(max-width:760px){.tg-cockpit-head{display:block}.tg-decision-pill{display:inline-block;margin-top:.55rem}.tg-kpi-grid{grid-template-columns:1fr 1fr}.tg-next-grid{grid-template-columns:1fr}.tg-guide{grid-template-columns:1fr 1fr}.tg-cockpit-title{font-size:1.08rem}.tg-kpi strong{font-size:.88rem}}
</style>
"""

_DISPOSITION_LABELS = {
    "specialist_clearance_required": "전문가 확인 후 결정",
    "conditions_required_before_commitment": "조건 보완 후 진행",
    "additional_information_required": "추가 정보 필요",
    "review_required": "추가 검토 필요",
    "no_material_screening_flags": "중대한 사전 경고 없음",
}
_DIRECTION_LABELS = {
    "export": "수출",
    "import": "수입",
    "receivable": "수취",
    "payable": "지급",
}
_RESPONSIBLE_LABELS = {
    "customer": "고객사",
    "bank": "은행",
    "ksure": "K-SURE",
    "buyer": "바이어",
    "seller": "수출자",
    "legal_counsel": "법무",
    "logistics_provider": "물류",
    "other": "기타",
}


def _fmt_amount(value: Any, currency: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "확인 필요"
    return f"{currency} {number:,.0f}"


def _transaction_value(transaction: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = transaction.get(key)
        if value not in (None, ""):
            return value
    return default


def _evidence_count(brief: Any) -> int:
    identifiers: set[str] = set()
    for field in (
        "country_fact_ids",
        "compliance_screening_ids",
        "calculation_ids",
        "product_candidate_ids",
        "consultation_requirement_ids",
    ):
        identifiers.update(str(item) for item in getattr(brief, field, []) or [])
    for concern in getattr(brief, "ranked_concerns", []) or []:
        identifiers.update(str(item) for item in getattr(concern, "source_ids", []) or [])
    source = getattr(brief, "source", None)
    source_id = getattr(source, "source_id", None)
    if source_id:
        identifiers.add(str(source_id))
    return len(identifiers)


def render_guided_nav() -> None:
    st.markdown(
        """
        <div class="tg-guide">
          <a href="#summary" target="_self">1 · 거래 판정</a>
          <a href="#scenarios" target="_self">2 · 시나리오</a>
          <a href="#products" target="_self">3 · 금융지원</a>
          <a href="#final-audit" target="_self">4 · 근거·감사</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision_cockpit(run: Any, scenario_id: str) -> None:
    """Render reviewed transaction, brief, and governed action-plan outputs."""
    case = run.updated_case
    brief = run.assessment_result.brief
    transactions = list(case.approved_transactions or [])
    transaction = transactions[0] if transactions else {}

    currency = str(_transaction_value(transaction, "currency", "currency_code", default="FCY"))
    amount = _transaction_value(transaction, "amount_fc", "amount", "transaction_amount")
    country = str(
        _transaction_value(
            transaction,
            "counterparty_country",
            "country_code",
            "destination_country",
            "origin_country",
            default="해외",
        )
    )
    raw_direction = str(
        _transaction_value(transaction, "direction", "trade_direction", "transaction_type", default="수출입")
    ).lower()
    direction = _DIRECTION_LABELS.get(raw_direction, raw_direction)

    findings = list(brief.ranked_concerns or [])
    actions = sorted(list(brief.action_plan or []), key=lambda item: item.sequence)
    disposition_label = _DISPOSITION_LABELS.get(brief.disposition, brief.disposition)
    evidence_count = _evidence_count(brief)

    action_cards: list[str] = []
    for action in actions[:3]:
        action_cards.append(
            '<div class="tg-next">'
            f'<b>{action.sequence}. {escape(action.title)}</b>'
            f'<span>{escape(action.rationale)}</span>'
            f'<small>{escape(_RESPONSIBLE_LABELS.get(action.responsible_party, action.responsible_party))} · {escape(action.status)}</small>'
            "</div>"
        )
    if not action_cards:
        rationale = brief.disposition_rationale[0] if brief.disposition_rationale else "추가 실행 항목이 생성되지 않았습니다."
        action_cards.append(
            '<div class="tg-next"><b>현재 추가 실행 없음</b>'
            f'<span>{escape(rationale)}</span><small>검토 Snapshot 기준</small></div>'
        )

    st.markdown(COCKPIT_CSS, unsafe_allow_html=True)
    st.markdown('<div id="summary" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <section class="tg-cockpit">
          <div class="tg-cockpit-head">
            <div>
              <div class="tg-cockpit-kicker">TRADE DECISION COCKPIT</div>
              <div class="tg-cockpit-title">{escape(country)} · {escape(currency)} {escape(direction)} 거래 검토</div>
              <div class="tg-cockpit-sub">거래금액 {escape(_fmt_amount(amount, currency))} · 시나리오 {escape(scenario_id)} · 확정 전 핵심 위험과 다음 행동</div>
            </div>
            <div class="tg-decision-pill">{escape(disposition_label)}</div>
          </div>
          <div class="tg-kpi-grid">
            <div class="tg-kpi"><span>핵심 위험</span><strong>{min(len(findings), 3)}개 우선</strong></div>
            <div class="tg-kpi"><span>연결된 근거</span><strong>{evidence_count}건</strong></div>
            <div class="tg-kpi"><span>우선 실행</span><strong>{min(len(actions), 3)}개</strong></div>
            <div class="tg-kpi"><span>신뢰 경계</span><strong>승인 아님</strong></div>
          </div>
          <div class="tg-next-grid">{''.join(action_cards)}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_decision_charts() -> None:
    """Render clearly labeled explanatory normalized-index charts."""
    st.markdown('<div id="scenarios" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">02 · 시나리오와 현금흐름</div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("**FX 스트레스 · 기준 대비 원화가치**")
            frame = pd.DataFrame(
                {"원화가치 지수": [90, 95, 100, 105, 110]},
                index=["-10%", "-5%", "기준", "+5%", "+10%"],
            )
            st.bar_chart(frame, y_label="정규화 지수")
            st.caption("설명용 정규화 지수입니다. 실제 거래 계산값은 Decision Brief의 계산 ID에서 확인합니다.")
    with right:
        with st.container(border=True):
            st.markdown("**자연헤지 후 순노출 구조**")
            frame = pd.DataFrame(
                {"금액 지수": [100, -35, -15, 50]},
                index=["수출채권", "수입채무", "외화예금", "순노출"],
            )
            st.bar_chart(frame, y_label="정규화 지수")
            st.caption("총노출을 그대로 헤지하지 않고 반대 현금흐름과 외화자산을 먼저 차감합니다.")
    with st.container(border=True):
        st.markdown("**예상 현금흐름 Timeline**")
        frame = pd.DataFrame(
            {"예상잔액 지수": [100, 88, 61, 54, 96]},
            index=["계약", "선적", "수입대금", "수금대기", "수금"],
        )
        st.line_chart(frame, y_label="정규화 지수")
        st.caption("수금 지연 시 현금공백이 발생하는 구간을 먼저 확인하고 운전자금·채권금융 후보를 연결합니다.")


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
