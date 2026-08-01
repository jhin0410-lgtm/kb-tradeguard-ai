"""Decision-first public competition UI for KB TradeGuard AI.

The module consumes reviewed deterministic outputs and invokes only the existing
portfolio aggregation engine against the governed case snapshot.
"""
from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from .intelligence.portfolio_assessment import analyze_trade_portfolio

COCKPIT_CSS = """
<style>
.tg-cockpit{border:1px solid #d9e2ee;border-radius:22px;padding:1rem;background:linear-gradient(180deg,#fff,#f7faff);box-shadow:0 12px 34px rgba(15,36,68,.08);margin:.7rem 0 1rem}
.tg-cockpit-head{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;margin-bottom:.8rem}.tg-cockpit-kicker{font-size:.67rem;letter-spacing:.1em;font-weight:900;color:#6d7b91}.tg-cockpit-title{font-size:1.32rem;font-weight:900;color:#172033;margin:.22rem 0}.tg-cockpit-sub{font-size:.78rem;color:#647084;line-height:1.45}.tg-decision-pill{padding:.48rem .7rem;border-radius:999px;background:#fff1cc;color:#6b4b00;font-size:.72rem;font-weight:900;border:1px solid #f0d37a;white-space:nowrap}
.tg-kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.55rem}.tg-kpi{border:1px solid #dce4ef;border-radius:15px;padding:.72rem;background:#fff}.tg-kpi span{display:block;font-size:.64rem;color:#748198;font-weight:800}.tg-kpi strong{display:block;margin-top:.22rem;font-size:1rem;color:#172033}
.tg-next-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.55rem;margin-top:.65rem}.tg-next{border-radius:14px;padding:.72rem;background:#07172d;color:#fff;min-height:92px}.tg-next b{display:block;font-size:.78rem;margin-bottom:.25rem}.tg-next span{font-size:.68rem;opacity:.82;line-height:1.4}.tg-next small{display:block;margin-top:.35rem;font-size:.59rem;opacity:.68}
.tg-guide{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.5rem;margin:.8rem 0}.tg-guide a{display:block;text-decoration:none;border:1px solid #dce4ef;border-radius:14px;padding:.7rem;background:#fff;color:#172033;font-size:.72rem;font-weight:900;text-align:center}.tg-guide a:hover{border-color:#1b63e9;background:#f3f7ff}
.tg-handoff{border:1px solid #ead89b;background:#fff9df;border-radius:18px;padding:.95rem;margin:.75rem 0}.tg-handoff strong{color:#4f3c00}.tg-handoff p{font-size:.74rem;color:#655b3b;margin:.3rem 0 0;line-height:1.48}.tg-handoff-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.45rem;margin-top:.65rem}.tg-handoff-item{border:1px solid rgba(125,94,0,.18);border-radius:12px;padding:.62rem;background:rgba(255,255,255,.62)}.tg-handoff-item small{display:block;font-size:.58rem;font-weight:900;color:#806600}.tg-handoff-item span{display:block;font-size:.68rem;color:#4f4a38;margin-top:.12rem;line-height:1.35}
@media(max-width:760px){.tg-cockpit-head{display:block}.tg-decision-pill{display:inline-block;margin-top:.55rem}.tg-kpi-grid{grid-template-columns:1fr 1fr}.tg-next-grid,.tg-handoff-grid{grid-template-columns:1fr}.tg-guide{grid-template-columns:1fr 1fr}.tg-cockpit-title{font-size:1.08rem}.tg-kpi strong{font-size:.88rem}}
</style>
"""

_DISPOSITION_LABELS = {
    "specialist_clearance_required": "전문가 확인 후 결정",
    "conditions_required_before_commitment": "조건 보완 후 진행",
    "additional_information_required": "추가 정보 필요",
    "review_required": "추가 검토 필요",
    "no_material_screening_flags": "중대한 사전 경고 없음",
}
_DIRECTION_LABELS = {"export": "수출", "import": "수입", "receivable": "수취", "payable": "지급"}
_RESPONSIBLE_LABELS = {
    "customer": "고객사", "bank": "은행", "ksure": "K-SURE", "buyer": "바이어",
    "seller": "수출자", "legal_counsel": "법무", "logistics_provider": "물류", "other": "기타",
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
    for field in ("country_fact_ids", "compliance_screening_ids", "calculation_ids", "product_candidate_ids", "consultation_requirement_ids"):
        identifiers.update(str(item) for item in getattr(brief, field, []) or [])
    for concern in getattr(brief, "ranked_concerns", []) or []:
        identifiers.update(str(item) for item in getattr(concern, "source_ids", []) or [])
    source_id = getattr(getattr(brief, "source", None), "source_id", None)
    if source_id:
        identifiers.add(str(source_id))
    return len(identifiers)


def render_guided_nav() -> None:
    st.markdown(
        """<div class="tg-guide"><a href="#summary" target="_self">1 · 거래 판정</a><a href="#evidence" target="_self">2 · 위험 근거</a><a href="#scenarios" target="_self">3 · FX·유동성</a><a href="#products" target="_self">4 · 금융지원</a><a href="#final-audit" target="_self">5 · 감사</a></div>""",
        unsafe_allow_html=True,
    )


def render_decision_cockpit(run: Any, scenario_id: str) -> None:
    case = run.updated_case
    brief = run.assessment_result.brief
    transactions = list(case.approved_transactions or [])
    transaction = transactions[0] if transactions else {}
    currency = str(_transaction_value(transaction, "currency", "currency_code", default="FCY"))
    amount = _transaction_value(transaction, "amount_fc", "amount", "transaction_amount")
    country = str(_transaction_value(transaction, "counterparty_country", "country_code", "destination_country", "origin_country", default="해외"))
    raw_direction = str(_transaction_value(transaction, "direction", "trade_direction", "transaction_type", default="수출입")).lower()
    direction = _DIRECTION_LABELS.get(raw_direction, raw_direction)
    findings = list(brief.ranked_concerns or [])
    actions = sorted(list(brief.action_plan or []), key=lambda item: item.sequence)
    disposition_label = _DISPOSITION_LABELS.get(brief.disposition, brief.disposition)
    action_cards: list[str] = []
    for action in actions[:3]:
        action_cards.append(
            '<div class="tg-next">'
            f'<b>{action.sequence}. {escape(action.title)}</b><span>{escape(action.rationale)}</span>'
            f'<small>{escape(_RESPONSIBLE_LABELS.get(action.responsible_party, action.responsible_party))} · {escape(action.status)}</small></div>'
        )
    if not action_cards:
        rationale = brief.disposition_rationale[0] if brief.disposition_rationale else "추가 실행 항목이 생성되지 않았습니다."
        action_cards.append(f'<div class="tg-next"><b>현재 추가 실행 없음</b><span>{escape(rationale)}</span><small>검토 Snapshot 기준</small></div>')
    st.markdown(COCKPIT_CSS, unsafe_allow_html=True)
    st.markdown('<div id="summary" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""<section class="tg-cockpit"><div class="tg-cockpit-head"><div><div class="tg-cockpit-kicker">TRADE DECISION COCKPIT</div><div class="tg-cockpit-title">{escape(country)} · {escape(currency)} {escape(direction)} 거래 검토</div><div class="tg-cockpit-sub">거래금액 {escape(_fmt_amount(amount, currency))} · 시나리오 {escape(scenario_id)} · 확정 전 핵심 위험과 다음 행동</div></div><div class="tg-decision-pill">{escape(disposition_label)}</div></div><div class="tg-kpi-grid"><div class="tg-kpi"><span>핵심 위험</span><strong>{min(len(findings), 3)}개 우선</strong></div><div class="tg-kpi"><span>연결된 근거</span><strong>{_evidence_count(brief)}건</strong></div><div class="tg-kpi"><span>우선 실행</span><strong>{min(len(actions), 3)}개</strong></div><div class="tg-kpi"><span>신뢰 경계</span><strong>승인 아님</strong></div></div><div class="tg-next-grid">{''.join(action_cards)}</div></section>""",
        unsafe_allow_html=True,
    )


def build_decision_chart_frames(run: Any) -> tuple[dict[str, pd.DataFrame], list[str]]:
    try:
        assessment = analyze_trade_portfolio(run.updated_case)
    except (TypeError, ValueError) as exc:
        return {}, [str(exc)]
    exposure_rows = [{"통화": item.currency, "수출채권": float(item.export_receivables_fc), "수입채무": -float(item.import_payables_fc), "외화현금": float(item.foreign_cash_fc), "순노출": float(item.net_exposure_fc)} for item in assessment.currency_exposures]
    stress_rows = [{"환율충격(%)": float(item.shock_percent), "추정가치변화(KRW)": float(item.estimated_fx_value_change_krw)} for item in assessment.stress_points if item.impacted_currencies]
    if stress_rows:
        stress_rows.append({"환율충격(%)": 0.0, "추정가치변화(KRW)": 0.0})
        stress_rows.sort(key=lambda item: item["환율충격(%)"])
    liquidity_rows = [{"월": item.period, "기말현금(KRW)": float(item.ending_cash_krw)} for item in assessment.liquidity_buckets if item.ending_cash_krw is not None]
    return {"exposure": pd.DataFrame(exposure_rows), "stress": pd.DataFrame(stress_rows), "liquidity": pd.DataFrame(liquidity_rows)}, list(assessment.missing_inputs)


def render_decision_charts(run: Any) -> None:
    st.markdown('<div id="scenarios" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">03 · FX·유동성 위험 시나리오</div>', unsafe_allow_html=True)
    frames, missing_inputs = build_decision_chart_frames(run)
    if not frames:
        st.info("검토된 거래 입력만으로 차트를 생성할 수 없습니다. 누락값을 추정하지 않습니다.")
        if missing_inputs:
            st.caption("확인 필요 · " + " / ".join(missing_inputs))
        return
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("**FX 스트레스 · 순노출 가치변화**")
            stress = frames["stress"]
            if stress.empty:
                st.info("검토된 기준환율이 없어 원화 FX 민감도를 표시하지 않습니다.")
            else:
                st.bar_chart(stress.set_index("환율충격(%)")[["추정가치변화(KRW)"]], y_label="원화 가치변화")
                st.caption("검토된 순외환노출에 동일 비율 충격을 적용한 민감도입니다. 환율 예측이나 체결 견적이 아닙니다.")
    with right:
        with st.container(border=True):
            st.markdown("**자연헤지 후 실제 통화별 순노출**")
            exposure = frames["exposure"]
            if exposure.empty:
                st.info("검토 완료 거래의 통화 노출을 찾지 못했습니다.")
            else:
                st.bar_chart(exposure.set_index("통화")[["수출채권", "수입채무", "외화현금", "순노출"]], y_label="외화 금액")
                st.caption("검토 완료 거래와 외화현금만 집계합니다. 법적 상계권과 결제시점 일치는 별도 확인 대상입니다.")
    with st.container(border=True):
        st.markdown("**검토된 월별 예상 기말현금**")
        liquidity = frames["liquidity"]
        if liquidity.empty:
            st.info("결제예정일·기준환율·현금 가정이 충분하지 않아 현금흐름을 표시하지 않습니다.")
        else:
            st.line_chart(liquidity.set_index("월")[["기말현금(KRW)"]], y_label="원화 기말현금")
            st.caption("검토 완료 거래 일정, 검토된 환율과 명시적 현금·고정비 가정만 사용한 결정론적 시나리오입니다.")
    if missing_inputs:
        st.caption("추가 확인 입력 · " + " / ".join(missing_inputs))


def render_kb_handoff(run: Any | None = None) -> None:
    brief = getattr(getattr(run, "assessment_result", None), "brief", None)
    actions = sorted(list(getattr(brief, "action_plan", []) or []), key=lambda item: item.sequence)
    candidates = list(getattr(brief, "product_candidate_ids", []) or [])
    concerns = list(getattr(brief, "ranked_concerns", []) or [])
    first_action = actions[0].title if actions else "필수 확인사항과 준비서류 정리"
    st.markdown(COCKPIT_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""<div class="tg-handoff"><strong>KB 상담 handoff · 현재 Case 기반</strong><p>고객은 위험과 준비서류를 미리 이해하고, 상담직원은 거래·근거·미확인 조건이 정리된 Decision Brief로 상담을 시작합니다. 실제 승인·금리·한도를 확정하지 않습니다.</p><div class="tg-handoff-grid"><div class="tg-handoff-item"><small>우선 위험</small><span>{len(concerns)}건 중 상위 항목 검토</span></div><div class="tg-handoff-item"><small>금융지원 후보</small><span>{len(candidates)}개 Candidate 연결</span></div><div class="tg-handoff-item"><small>첫 상담 행동</small><span>{escape(first_action)}</span></div></div></div>""",
        unsafe_allow_html=True,
    )


def render_usability_evidence() -> None:
    with st.expander("사용성 검증 계획과 기록 양식", expanded=False):
        st.markdown("**과제:** 사용자가 3분 안에 핵심 위험 3개와 다음 행동을 찾습니다.  \n**기록:** 완료시간, 정확한 행동 선택률, 이해되지 않은 용어, 불필요한 화면, 상담 의향.  \n**현재 상태:** 실제 참여자 결과는 없으며 임의 생성하지 않습니다.")
