"""Competition-facing workflow for company, transactions, portfolio risk, and products."""
from __future__ import annotations

from decimal import Decimal
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from .intelligence.portfolio_assessment import (
    CompanyPortfolioWorkspace,
    PortfolioAssessment,
    analyze_trade_portfolio,
    match_portfolio_products,
)
from .portfolio_demo import build_demo_company_workspace

PORTFOLIO_CSS = """
<style>
.tg-workflow-map{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:.45rem;margin:.7rem 0 1rem}.tg-workflow-step{border:1px solid #dce4ef;border-radius:14px;padding:.66rem .7rem;background:#fff;min-height:74px}.tg-workflow-step strong{display:block;font-size:.72rem;color:#172033;margin-bottom:.14rem}.tg-workflow-step span{display:block;color:#647084;font-size:.63rem;line-height:1.35}.tg-portfolio-boundary{border:1px solid #dce4ef;border-left:6px solid #0d95aa;border-radius:16px;padding:.82rem .9rem;background:#f5fbfc;color:#52627a;font-size:.76rem;line-height:1.52;margin-bottom:.7rem}.tg-portfolio-card{border:1px solid #dce4ef;border-radius:16px;padding:.82rem;background:#fff;min-height:140px}.tg-portfolio-card small{display:block;color:#748198;font-size:.64rem;font-weight:900}.tg-portfolio-card h3{margin:.28rem 0;font-size:1rem;color:#172033}.tg-portfolio-card p{margin:.18rem 0;color:#647084;font-size:.72rem;line-height:1.43}.tg-connected-badge{display:inline-block;border-radius:999px;padding:.34rem .58rem;background:#e9f8f7;color:#08756d;font-size:.64rem;font-weight:900;margin-bottom:.55rem}@media(max-width:760px){.tg-workflow-map{grid-template-columns:1fr 1fr}.tg-workflow-step,.tg-portfolio-card{min-height:auto}}
</style>
"""


def render_workflow_map() -> None:
    st.markdown(PORTFOLIO_CSS, unsafe_allow_html=True)
    st.markdown(
        """<div class="tg-workflow-map" aria-label="TradeGuard workflow"><div class="tg-workflow-step"><strong>1 · 기업</strong><span>기업 식별·재무·사업자 상태</span></div><div class="tg-workflow-step"><strong>2 · 거래</strong><span>수출입 방향·통화·금액·결제일</span></div><div class="tg-workflow-step"><strong>3 · 공식 데이터</strong><span>환율·국가·무역·기업 Snapshot</span></div><div class="tg-workflow-step"><strong>4 · 위험·시나리오</strong><span>문서·유동성·환노출·스트레스</span></div><div class="tg-workflow-step"><strong>5 · 금융지원</strong><span>상품·보험·보증 상담 후보</span></div><div class="tg-workflow-step"><strong>6 · 실행계획</strong><span>담당·선행조건·감사 ID</span></div></div>""",
        unsafe_allow_html=True,
    )


def _to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def build_currency_exposure_frame(assessment: PortfolioAssessment) -> pd.DataFrame:
    return pd.DataFrame([
        {"통화": item.currency, "수출채권": _to_float(item.export_receivables_fc), "수입채무": _to_float(item.import_payables_fc), "외화현금": _to_float(item.foreign_cash_fc), "순노출": _to_float(item.net_exposure_fc), "방향": {"long":"외화 순유입","short":"외화 순지급","flat":"중립"}[item.net_direction], "자연헤지율(%)": _to_float(item.natural_hedge_ratio_percent), "기준환율(KRW)": _to_float(item.reference_rate_krw), "순노출(KRW)": _to_float(item.net_exposure_krw), "거래": ", ".join(item.transaction_ids)}
        for item in assessment.currency_exposures
    ])


def build_liquidity_frame(assessment: PortfolioAssessment) -> pd.DataFrame:
    return pd.DataFrame([
        {"월": item.period, "기대유입(KRW)": _to_float(item.expected_inflow_krw), "기대유출(KRW)": _to_float(item.expected_outflow_krw), "고정비(KRW)": _to_float(item.fixed_cost_krw), "순현금흐름(KRW)": _to_float(item.net_cashflow_krw), "기말현금(KRW)": _to_float(item.ending_cash_krw), "거래": ", ".join(item.transaction_ids), "누락환율": ", ".join(item.missing_currency_rates)}
        for item in assessment.liquidity_buckets
    ])


def build_stress_frame(assessment: PortfolioAssessment) -> pd.DataFrame:
    return pd.DataFrame([
        {"환율충격(%)": _to_float(item.shock_percent), "추정가치변화(KRW)": _to_float(item.estimated_fx_value_change_krw), "영향통화": ", ".join(item.impacted_currencies)}
        for item in assessment.stress_points
    ])


def build_official_data_frame(case: Any) -> pd.DataFrame:
    return pd.DataFrame([
        {"데이터": key, "상태": asset.status, "출처": asset.source, "기준일": asset.as_of_date.isoformat() if asset.as_of_date else None, "Source hash": f"{asset.source_hash[:16]}…" if asset.source_hash else None}
        for key, asset in sorted(case.official_data_assets.items())
    ])


def _company_labels(workspace: CompanyPortfolioWorkspace) -> dict[str, str]:
    return {company_id: case.identity.company_name or company_id for company_id, case in workspace.companies.items()}


def _render_product_candidates(case: Any) -> None:
    _, result = match_portfolio_products(case)
    usable = [item for item in result.product_candidates if item.candidate_status in {"consultation_candidate", "insufficient_information"}]
    usable.sort(key=lambda item: (0 if item.provider == "KB Kookmin Bank" else 1, item.product_category, item.product_or_service_name))
    st.caption(f"현재 Case의 거래 {len(result.profile_ids)}건에서 상담 후보 {len(usable)}건을 생성했습니다. 동일 상품도 거래별 ID로 분리됩니다.")
    if not usable:
        st.info("현재 거래정보로 생성된 금융지원 상담 후보가 없습니다.")
        return
    columns = st.columns(min(3, len(usable)))
    for index, candidate in enumerate(usable[:6]):
        with columns[index % len(columns)]:
            linked = ", ".join(candidate.linked_transaction_ids)
            unresolved = candidate.unresolved_eligibility_conditions[0] if candidate.unresolved_eligibility_conditions else "현재 공식 조건 재확인"
            st.markdown(
                f"""<article class="tg-portfolio-card"><small>{escape(candidate.provider)} · {escape(candidate.candidate_status)}</small><h3>{escape(candidate.product_or_service_name)}</h3><p><strong>연결 거래</strong> · {escape(linked)}</p><p><strong>확인 조건</strong> · {escape(unresolved)}</p><p><strong>다음 행동</strong> · {escape(candidate.next_action)}</p></article>""",
                unsafe_allow_html=True,
            )


def _resolve_case(case: Any | None, presentation_mode: bool) -> tuple[Any, str, bool]:
    if case is not None:
        company_name = getattr(getattr(case, "identity", None), "company_name", None) or "현재 거래 Case"
        return case, company_name, True
    workspace = build_demo_company_workspace()
    labels = _company_labels(workspace)
    selected_id = workspace.active_company_id
    if not presentation_mode:
        selected_label = st.selectbox("기업 포트폴리오", options=[labels[key] for key in labels], key="competition_portfolio_company")
        selected_id = next(key for key, label in labels.items() if label == selected_label)
    workspace = workspace.switch_company(selected_id)
    return workspace.active_case, labels[selected_id], False


def render_portfolio_section(*, presentation_mode: bool, case: Any | None = None) -> None:
    """Render deterministic portfolio analytics for the active governed case.

    When ``case`` is provided the view stays connected to Decision Desk instead of
    switching to an unrelated demo workspace.
    """
    active_case, company_name, connected = _resolve_case(case, presentation_mode)
    assessment = analyze_trade_portfolio(active_case)
    st.markdown(PORTFOLIO_CSS, unsafe_allow_html=True)
    st.markdown('<div id="portfolio" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">04 · 기업·거래 포트폴리오</div>', unsafe_allow_html=True)
    if connected:
        st.markdown(f'<span class="tg-connected-badge">Decision Desk 연결 · {escape(company_name)}</span>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tg-portfolio-boundary"><strong>분석 범위</strong> · 검토 완료 거래를 통화·결제월·외화현금 기준으로 집계합니다. 공개 화면의 기업과 거래는 합성 사례이며 사용자 인증·tenant isolation을 구현한 운영형 다중기업 SaaS를 의미하지 않습니다.</div>',
        unsafe_allow_html=True,
    )
    metrics = st.columns(4)
    metrics[0].metric("검토 완료 거래", assessment.transaction_count)
    metrics[1].metric("거래 통화", assessment.currency_count)
    metrics[2].metric("총 거래노출", f"{float(assessment.gross_exposure_krw)/100_000_000:.1f}억원" if assessment.gross_exposure_krw is not None else "환율 확인 필요")
    metrics[3].metric("순 외환노출", f"{float(assessment.net_exposure_krw)/100_000_000:+.1f}억원" if assessment.net_exposure_krw is not None else "환율 확인 필요")
    exposure_tab, liquidity_tab, stress_tab, product_tab, data_tab = st.tabs(["통화 순노출", "월별 유동성", "FX 스트레스", "금융지원", "데이터 상태"])
    with exposure_tab:
        frame = build_currency_exposure_frame(assessment)
        st.dataframe(frame, hide_index=True, use_container_width=True)
        if not frame.empty:
            st.bar_chart(frame.set_index("통화")[["수출채권", "수입채무", "외화현금"]])
        st.caption("자연헤지율은 동일통화 수출채권과 수입채무의 단순 상계 가능 규모입니다. 법적 상계권과 결제시점 일치는 별도 확인 대상입니다.")
    with liquidity_tab:
        frame = build_liquidity_frame(assessment)
        st.dataframe(frame, hide_index=True, use_container_width=True)
        if not frame.empty:
            st.line_chart(frame.set_index("월")[["기말현금(KRW)"]])
        if assessment.missing_inputs:
            st.warning("누락 입력 · " + " / ".join(assessment.missing_inputs))
    with stress_tab:
        st.dataframe(build_stress_frame(assessment), hide_index=True, use_container_width=True)
        st.caption("모든 통화의 원화환율이 같은 비율로 움직인다는 민감도이며 예측값이나 체결 가능한 선물환 견적이 아닙니다.")
    with product_tab:
        _render_product_candidates(active_case)
    with data_tab:
        frame = build_official_data_frame(active_case)
        if frame.empty:
            st.info("첨부된 공식 데이터 Snapshot이 없습니다.")
        else:
            st.dataframe(frame, hide_index=True, use_container_width=True)
        st.caption("실시간 응답은 검토·고정된 Snapshot으로 변환된 후에만 포트폴리오 분석 입력으로 사용할 수 있습니다.")
