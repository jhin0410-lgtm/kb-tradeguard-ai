"""Compact competition-facing product consultation view.

The public demo previously generated governed product candidates but hid them under
a detail expander. This module surfaces the selected candidates without changing the
underlying product-matching authority boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st

from .competition_fx_strategy_view import render_fx_consultation_comparison


_STATUS_LABELS = {
    "consultation_candidate": "상담 후보",
    "insufficient_information": "추가정보 필요",
    "not_applicable": "현재 조건상 비적용",
    "blocked": "채널·조건 확인 필요",
}
_NEED_LABELS = {
    "buyer_credit_investigation": "해외 거래처 신용조사",
    "export_receivable_nonpayment_protection": "수출대금 미회수 위험 보호",
    "pre_shipment_working_capital": "선적 전 운전자금",
    "post_shipment_receivables_financing": "선적 후 수출채권 금융",
    "fx_cashflow_certainty": "외화 현금흐름 확정",
    "import_working_capital": "수입 운전자금",
    "import_advance_payment_protection": "수입 선급금 위험 보호",
    "export_working_capital": "수출 운전자금",
}
_STATUS_PRIORITY = {
    "consultation_candidate": 0,
    "insufficient_information": 1,
    "blocked": 2,
    "not_applicable": 3,
}
_CATEGORY_PRIORITY = {
    "foreign_exchange_hedging": 0,
    "working_capital": 1,
    "trade_credit_insurance": 2,
    "buyer_credit_investigation": 3,
    "receivables_financing": 4,
    "export_guarantee_pre_shipment": 5,
    "export_guarantee_post_shipment": 6,
    "import_finance": 7,
    "other": 8,
}

PRODUCT_VIEW_CSS = """
<style>
.tg-product-boundary {border:1px solid #dce4ef;border-radius:15px;padding:.78rem .88rem;background:#f8fafc;color:#59677c;font-size:.76rem;line-height:1.5;margin-bottom:.62rem;}
.tg-product-card {border:1px solid #dce4ef;border-top:5px solid #0d95aa;border-radius:18px;padding:.9rem;background:#fff;min-height:218px;box-shadow:0 8px 22px rgba(15,36,68,.05);}
.tg-product-card[data-status="insufficient_information"] {border-top-color:#b76800;}
.tg-product-card[data-status="blocked"] {border-top-color:#7554aa;}
.tg-product-card[data-status="not_applicable"] {border-top-color:#8490a3;}
.tg-product-card small {display:block;font-size:.64rem;font-weight:900;letter-spacing:.06em;color:#748198;}
.tg-product-card h3 {margin:.35rem 0 .35rem;font-size:.96rem;line-height:1.36;color:#172033;}
.tg-product-card p {margin:.23rem 0;color:#647084;font-size:.75rem;line-height:1.46;}
.tg-product-card .tg-product-status {display:inline-block;margin-top:.18rem;padding:.26rem .48rem;border-radius:999px;background:#eef4f8;font-size:.64rem;font-weight:900;color:#31506b;}
@media(max-width:760px) {.tg-product-card {min-height:auto;padding:.8rem;}}
</style>
"""


@dataclass(frozen=True)
class ProductConsultationCard:
    candidate_id: str
    provider: str
    product_name: str
    status: str
    status_label: str
    matched_needs: tuple[str, ...]
    next_action: str
    unresolved_conditions: tuple[str, ...]
    official_source_count: int


def _need_labels(raw: str) -> tuple[str, ...]:
    labels = []
    for token in (item.strip() for item in raw.split(",")):
        if not token:
            continue
        labels.append(_NEED_LABELS.get(token, token))
    return tuple(labels)


def selected_product_candidates(run) -> list:
    """Return only candidates selected into the deterministic Decision Brief."""

    selected_ids = list(run.assessment_result.brief.product_candidate_ids)
    candidates_by_id = {
        item.product_candidate_id: item
        for item in run.updated_case.trade_finance.product_candidates
    }
    return [candidates_by_id[item_id] for item_id in selected_ids if item_id in candidates_by_id]


def build_product_consultation_cards(run, *, limit: int = 4) -> list[ProductConsultationCard]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    candidates = selected_product_candidates(run)
    indexed = list(enumerate(candidates))
    indexed.sort(
        key=lambda pair: (
            _STATUS_PRIORITY.get(pair[1].candidate_status, 99),
            _CATEGORY_PRIORITY.get(pair[1].product_category, 99),
            0 if pair[1].provider == "KB Kookmin Bank" else 1,
            pair[0],
        )
    )
    cards = []
    for _, candidate in indexed[:limit]:
        cards.append(
            ProductConsultationCard(
                candidate_id=candidate.product_candidate_id,
                provider=candidate.provider,
                product_name=candidate.product_or_service_name,
                status=candidate.candidate_status,
                status_label=_STATUS_LABELS.get(
                    candidate.candidate_status, candidate.candidate_status
                ),
                matched_needs=_need_labels(candidate.matched_need),
                next_action=candidate.next_action,
                unresolved_conditions=tuple(
                    candidate.unresolved_eligibility_conditions[:2]
                ),
                official_source_count=len(candidate.official_source_ids),
            )
        )
    return cards


def render_product_consultation_section(run, *, presentation_mode: bool) -> None:
    """Render governed financing, insurance, guarantee, and hedge consultation cards."""

    cards = build_product_consultation_cards(run)
    st.markdown(PRODUCT_VIEW_CSS, unsafe_allow_html=True)
    st.markdown('<div id="products" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tg-section-title">05 · 금융·보험·보증 상담 후보</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="tg-product-boundary"><strong>추천의 의미</strong> · 거래 목적과 확인된 조건을 공개 상품정보에 연결한 상담 우선순위입니다. 적격성·승인·금리·한도·보험 인수·환헤지 적합성을 확정하지 않습니다.</div>',
        unsafe_allow_html=True,
    )
    if not cards:
        st.info("현재 Decision Brief에 선택된 상담 후보가 없습니다.")
    else:
        columns = st.columns(min(len(cards), 4))
        for column, card in zip(columns, cards):
            unresolved = " / ".join(card.unresolved_conditions) or "현재 공개정보 재확인"
            needs = " · ".join(card.matched_needs) or "거래 목적"
            with column:
                st.markdown(
                    f"""
                    <article class="tg-product-card" data-status="{escape(card.status)}">
                      <small>{escape(card.provider)} · 공식 출처 {card.official_source_count}건</small>
                      <h3>{escape(card.product_name)}</h3>
                      <span class="tg-product-status">{escape(card.status_label)}</span>
                      <p><strong>연결 필요</strong> · {escape(needs)}</p>
                      <p><strong>확인할 조건</strong> · {escape(unresolved)}</p>
                      <p><strong>다음 행동</strong> · {escape(card.next_action)}</p>
                    </article>
                    """,
                    unsafe_allow_html=True,
                )

    render_fx_consultation_comparison(run, presentation_mode=presentation_mode)
    if not presentation_mode:
        with st.expander("전체 상담 후보와 공식 조건", expanded=False):
            import assessment_app as detailed

            detailed._render_product_tab(run)
