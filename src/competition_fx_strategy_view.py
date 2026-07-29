"""Competition-facing FX risk-management consultation comparison.

The comparison does not choose a hedge ratio, forecast exchange rates, or provide an
executable quote. It organizes reviewed transaction facts into questions that a user
can take to a bank or K-SURE specialist.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

import streamlit as st


FX_STRATEGY_CSS = """
<style>
.tg-fx-summary {border:1px solid #dce4ef;border-radius:15px;padding:.78rem .88rem;background:#f8fafc;color:#52627a;font-size:.76rem;line-height:1.5;margin:.7rem 0 .55rem;}
.tg-fx-option {border:1px solid #dce4ef;border-radius:16px;padding:.82rem;background:#fff;min-height:196px;}
.tg-fx-option small {display:block;font-size:.63rem;font-weight:900;letter-spacing:.06em;color:#748198;}
.tg-fx-option h4 {margin:.32rem 0 .34rem;font-size:.9rem;color:#172033;}
.tg-fx-option p {margin:.22rem 0;color:#647084;font-size:.73rem;line-height:1.46;}
@media(max-width:760px) {.tg-fx-option {min-height:auto;}}
</style>
"""


@dataclass(frozen=True)
class FXConsultationOption:
    option_id: str
    title: str
    route: str
    purpose: str
    tradeoff: str
    required_inputs: tuple[str, ...]
    official_source_ids: tuple[str, ...] = ()


def _transaction(run) -> dict[str, Any] | None:
    transaction_id = run.assessment_result.transaction_id
    for item in run.updated_case.approved_transactions:
        if str(item.get("transaction_id")) == transaction_id:
            return item
    return None


def build_fx_consultation_options(run) -> list[FXConsultationOption]:
    """Build a comparison set only when the reviewed transaction has FX exposure."""

    transaction = _transaction(run)
    if transaction is None:
        return []
    currency = str(transaction.get("currency") or "").upper()
    if currency in {"", "KRW"}:
        return []

    options = [
        FXConsultationOption(
            option_id="UNHEDGED-BASELINE",
            title="미헤지 기준선",
            route="내부 현금흐름 검토",
            purpose="결제일까지 환율 변동이 원화 수취·지급액에 미치는 범위를 비교하는 기준선",
            tradeoff="상승·하락을 모두 그대로 부담하며 확정 원화금액이 없음",
            required_inputs=("통화·금액", "결제예정일", "손익분기 환율", "기존 외화잔액"),
        ),
        FXConsultationOption(
            option_id="KB-FORWARD-CONSULTATION",
            title="KB 선물환 상담",
            route="KB 외환 전문상담",
            purpose="미래 결제일의 적용환율을 사전에 약정하는 구조의 조건과 비용 확인",
            tradeoff="실제 체결환율·스왑포인트·한도·중도변경 비용과 반대방향 기회비용은 상담 시점에 확인 필요",
            required_inputs=("통화·금액", "결제예정일", "수출입 계약", "기존 헤지계약"),
            official_source_ids=("KB-INTERNET-FORWARD-SPOT-FX",),
        ),
        FXConsultationOption(
            option_id="KSURE-FX-INSURANCE-CONSULTATION",
            title="K-SURE 환변동보험 상담",
            route="K-SURE 또는 외환 전문상담",
            purpose="수출입 외화금액의 원화가치를 관리하는 보험 유형별 보상·상승이익 처리 비교",
            tradeoff="일반형·옵션형별 보험료, 보상구조, 상승이익 납부와 청약 가능기간이 다름",
            required_inputs=("통화·금액", "결제예정일", "기업규모", "기존 선물환·보험"),
            official_source_ids=("KSURE-FX-FLUCTUATION-INSURANCE",),
        ),
        FXConsultationOption(
            option_id="STAGED-HEDGE-DESIGN",
            title="분할 헤지 검토",
            route="사용자 정책 + 전문가 확인",
            purpose="발주·선적·매출채권 확정도에 맞춰 상담 시점과 대상금액을 나누는 운영안 검토",
            tradeoff="임의 헤지비율을 자동 제안하지 않으며 거래 확정도와 기존 자연헤지를 먼저 검증해야 함",
            required_inputs=("거래 확정도", "선적 일정", "외화 매입·매출 상계", "허용 가능한 원화 변동폭"),
        ),
    ]
    return options


def render_fx_consultation_comparison(run, *, presentation_mode: bool) -> None:
    options = build_fx_consultation_options(run)
    if not options:
        return
    transaction = _transaction(run) or {}
    currency = str(transaction.get("currency") or "")
    amount = transaction.get("amount_fc")
    expected_date = transaction.get("expected_date") or "미확정"

    st.markdown(FX_STRATEGY_CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div class="tg-fx-summary"><strong>환노출 상담 기준</strong> · {escape(currency)} {escape(str(amount))} · 결제예정일 {escape(str(expected_date))}. 아래 항목은 비교할 상담 경로이며 자동 최적화·환율전망·체결지시가 아닙니다.</div>',
        unsafe_allow_html=True,
    )
    columns = st.columns(4)
    for column, option in zip(columns, options):
        inputs = " · ".join(option.required_inputs)
        sources = " · ".join(option.official_source_ids) or "내부 검토 기준선"
        with column:
            st.markdown(
                f"""
                <article class="tg-fx-option">
                  <small>{escape(option.route)}</small>
                  <h4>{escape(option.title)}</h4>
                  <p><strong>목적</strong> · {escape(option.purpose)}</p>
                  <p><strong>주의</strong> · {escape(option.tradeoff)}</p>
                  <p><strong>필요 입력</strong> · {escape(inputs)}</p>
                  <p><strong>근거</strong> · {escape(sources)}</p>
                </article>
                """,
                unsafe_allow_html=True,
            )
    if not presentation_mode:
        st.caption(
            "헤지 비율과 실행수단은 외화 현금흐름, 자연헤지, 거래 확정도, 신용한도, 비용과 위험선호를 확인한 뒤 결정해야 합니다."
        )
