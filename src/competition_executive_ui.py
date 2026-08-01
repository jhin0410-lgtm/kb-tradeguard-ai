"""Executive decision-cockpit presentation layer for the public competition app.

This module is presentation-only. It reads governed deterministic records and
portfolio outputs, and does not create risk findings, product eligibility, pricing,
approval decisions, or executable hedge instructions.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from .assessment_app_v2 import RiskFirstSummary, build_risk_first_summary
from .competition_case_study_view import build_official_case_study_summaries
from .competition_fx_strategy_view import render_fx_consultation_comparison
from .competition_product_view import ProductConsultationCard, build_product_consultation_cards
from .intelligence.portfolio_assessment import PortfolioAssessment, analyze_trade_portfolio
from .portfolio_demo import build_demo_company_workspace


STAGE_LABELS = {
    "decision": "1 · 판정",
    "scenarios": "2 · 시나리오",
    "support": "3 · 금융지원",
    "evidence": "4 · 근거",
}

EXECUTIVE_CSS = """
<style>
:root{--kb-yellow:#ffbc00;--tg-blue:#1b63e9;--tg-cyan:#0d95aa;--tg-border:#dce4ef;--tg-muted:#647084}
.tg-exec-hero{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(230px,.3fr);gap:.9rem;padding:1.14rem 1.28rem;border-radius:22px;color:#fff;background:radial-gradient(circle at 88% 8%,rgba(255,188,0,.32),transparent 30%),linear-gradient(126deg,#07172d,#123f78 60%,#0b7285);box-shadow:0 18px 42px rgba(7,23,45,.18)}
.tg-exec-hero small{font-size:.67rem;letter-spacing:.12em;font-weight:900;opacity:.78}.tg-exec-hero h1{margin:.38rem 0;font-size:1.68rem;line-height:1.17;letter-spacing:-.03em}.tg-exec-hero p{margin:0;max-width:800px;font-size:.84rem;line-height:1.5;opacity:.94}.tg-exec-hero-side{display:grid;gap:.42rem;align-content:center}.tg-exec-hero-chip{border:1px solid rgba(255,255,255,.24);border-radius:12px;padding:.56rem .64rem;background:rgba(255,255,255,.09)}.tg-exec-hero-chip strong{display:block;font-size:.74rem}.tg-exec-hero-chip span{display:block;margin-top:.08rem;font-size:.62rem;line-height:1.32;opacity:.82}
.tg-exec-mini{display:flex;align-items:center;justify-content:space-between;gap:.8rem;padding:.75rem .9rem;border:1px solid var(--tg-border);border-left:6px solid var(--kb-yellow);border-radius:16px;background:linear-gradient(120deg,#fff,#f7fbff);box-shadow:0 8px 20px rgba(15,36,68,.04);margin-bottom:.62rem}.tg-exec-mini small{font-size:.62rem;font-weight:900;letter-spacing:.08em;color:#748198}.tg-exec-mini strong{display:block;margin-top:.12rem;font-size:.92rem;color:#172033}.tg-exec-mini span{font-size:.69rem;color:#647084;text-align:right}
.tg-stage-shell{border:1px solid var(--tg-border);border-radius:18px;padding:.58rem .72rem;background:#fff;margin:.58rem 0 .72rem;color:#647084;font-size:.72rem}.tg-cockpit{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(300px,.85fr);gap:.72rem;margin:.65rem 0 .75rem}.tg-decision-card{border:1px solid var(--tg-border);border-left:9px solid var(--tg-blue);border-radius:20px;padding:1rem 1.05rem;background:#fff}.tg-decision-card[data-tone="critical"]{border-left-color:#b52431;background:#fff5f6}.tg-decision-card[data-tone="warning"]{border-left-color:#b76800;background:#fff9ef}.tg-decision-card[data-tone="clear"]{border-left-color:#147455;background:#f2faf7}.tg-decision-card small{font-size:.64rem;font-weight:900;letter-spacing:.08em;color:#758199}.tg-decision-card h2{margin:.3rem 0 .34rem;font-size:1.28rem;color:#172033}.tg-decision-card p{margin:.18rem 0;color:#58667a;font-size:.78rem;line-height:1.48}.tg-cockpit-metrics{display:grid;grid-template-columns:1fr 1fr;gap:.5rem}.tg-cockpit-metric{border:1px solid var(--tg-border);border-radius:15px;padding:.72rem .76rem;background:#fff}.tg-cockpit-metric small{display:block;font-size:.61rem;color:#748198;font-weight:900}.tg-cockpit-metric strong{display:block;margin-top:.18rem;font-size:1.05rem;color:#172033}.tg-cockpit-metric span{display:block;margin-top:.14rem;font-size:.63rem;color:#748198;line-height:1.35}.tg-priority-strip{border:1px solid #ebd08a;border-radius:16px;padding:.78rem .86rem;background:#fff9e8;margin:.62rem 0}.tg-priority-strip strong{font-size:.78rem;color:#533800}.tg-priority-strip span{display:block;margin-top:.22rem;font-size:.72rem;line-height:1.48;color:#74551a}.tg-chart-note{border:1px dashed #9aabc2;border-radius:13px;padding:.64rem .72rem;background:#f8fafc;color:#647084;font-size:.7rem;line-height:1.45}
.tg-product-priority{border:1px solid var(--tg-border);border-top:5px solid var(--tg-cyan);border-radius:18px;padding:.85rem;background:#fff;min-height:220px;box-shadow:0 8px 22px rgba(15,36,68,.05)}.tg-product-priority[data-rank="1"]{border-top-color:var(--kb-yellow)}.tg-product-priority small{font-size:.62rem;font-weight:900;letter-spacing:.07em;color:#748198}.tg-product-priority h3{margin:.34rem 0;font-size:.94rem;color:#172033;line-height:1.35}.tg-product-priority p{margin:.22rem 0;color:#647084;font-size:.73rem;line-height:1.43}.tg-handoff{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(250px,.65fr);gap:.75rem;border:1px solid #e2c05e;border-radius:19px;padding:.9rem;background:linear-gradient(135deg,#fffaf0,#fff)}.tg-handoff h3{margin:.12rem 0 .35rem;font-size:1rem;color:#172033}.tg-handoff p{margin:.22rem 0;color:#647084;font-size:.75rem;line-height:1.48}.tg-handoff-path{display:grid;gap:.36rem}.tg-handoff-step{border:1px solid #ead79c;border-radius:12px;padding:.58rem;background:#fff;font-size:.7rem;color:#5d4a19}
.tg-impact-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.55rem}.tg-impact-card{border:1px solid var(--tg-border);border-radius:16px;padding:.78rem;background:#fff}.tg-impact-card small{font-size:.61rem;font-weight:900;color:#748198}.tg-impact-card h4{margin:.28rem 0;font-size:.86rem;color:#172033}.tg-impact-card p{margin:.18rem 0;color:#647084;font-size:.7rem;line-height:1.44}.tg-api-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:.5rem}.tg-api-card{border:1px solid var(--tg-border);border-radius:14px;padding:.68rem;background:#fff}.tg-api-card strong{display:block;font-size:.74rem;color:#172033}.tg-api-card span{display:block;margin-top:.12rem;font-size:.64rem;color:#647084;line-height:1.4}.tg-api-state{display:inline-block!important;margin-top:.32rem!important;padding:.22rem .42rem;border-radius:999px;background:#eef4f8;font-size:.6rem!important;font-weight:900;color:#31506b}.tg-api-state[data-state="configured"],.tg-api-state[data-state="public"]{background:#edf8f3;color:#147455}.tg-api-state[data-state="missing"]{background:#fff5e8;color:#9a5a00}
.tg-mobile-stage-nav{position:fixed;left:50%;bottom:max(10px,env(safe-area-inset-bottom));transform:translateX(-50%);z-index:9999;display:flex;gap:.2rem;padding:.3rem;border:1px solid rgba(135,151,175,.55);border-radius:999px;background:rgba(8,19,36,.94);box-shadow:0 10px 30px rgba(0,0,0,.24)}.tg-mobile-stage-nav a{color:#eef4ff;text-decoration:none;font-size:.68rem;font-weight:900;padding:.56rem .7rem;border-radius:999px;white-space:nowrap}.tg-mobile-stage-nav a[data-active="true"]{background:var(--kb-yellow);color:#2b2100}
@media(max-width:760px){.tg-exec-hero{grid-template-columns:1fr;padding:.72rem .78rem;border-radius:16px;gap:.48rem}.tg-exec-hero small{font-size:.58rem}.tg-exec-hero h1{font-size:1.19rem;line-height:1.2;margin:.27rem 0}.tg-exec-hero p{font-size:.7rem;line-height:1.4}.tg-exec-hero-side{grid-template-columns:repeat(3,1fr);gap:.28rem}.tg-exec-hero-chip{padding:.38rem .3rem;text-align:center}.tg-exec-hero-chip strong{font-size:.64rem}.tg-exec-hero-chip span{display:none}.tg-exec-mini{padding:.58rem .65rem}.tg-exec-mini strong{font-size:.8rem}.tg-exec-mini span{display:none}.tg-cockpit{grid-template-columns:1fr}.tg-cockpit-metrics{grid-template-columns:1fr 1fr}.tg-cockpit-metric{padding:.62rem}.tg-cockpit-metric strong{font-size:.92rem}.tg-product-priority{min-height:auto}.tg-handoff{grid-template-columns:1fr}.tg-impact-grid{grid-template-columns:1fr}.tg-mobile-stage-nav{width:calc(100% - .8rem);justify-content:space-around}.tg-mobile-stage-nav a{padding:.54rem .48rem;font-size:.63rem}}
</style>
"""


@dataclass(frozen=True)
class ExecutiveModel:
    transaction_label: str
    disposition: str
    disposition_headline: str
    disposition_explanation: str
    top_risk_title: str
    missing_information_count: int
    reviewed_data_count: int
    unavailable_data_count: int
    product_cards: tuple[ProductConsultationCard, ...]
    summary: RiskFirstSummary


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _format_krw(value: Decimal | None, *, signed: bool = False) -> str:
    if value is None:
        return "확인 필요"
    prefix = "+" if signed and value > 0 else ""
    absolute = abs(value)
    if absolute >= Decimal("100000000"):
        return f"{prefix}{value / Decimal('100000000'):.1f}억원"
    if absolute >= Decimal("10000"):
        return f"{prefix}{value / Decimal('10000'):.0f}만원"
    return f"{prefix}{value:,.0f}원"


def _first_value(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _transaction_label(run) -> str:
    transactions = list(getattr(run.updated_case, "approved_transactions", []) or [])
    transaction = transactions[0] if transactions and isinstance(transactions[0], dict) else {}
    direction = str(_first_value(transaction, "transaction_type", "direction") or "거래").strip().lower()
    direction_label = {"export": "수출", "import": "수입"}.get(direction, direction or "거래")
    country = str(
        _first_value(
            transaction,
            "country_code",
            "buyer_country",
            "seller_country",
            "counterparty_country",
            "trade_country",
            "destination_country",
            "origin_country",
        )
        or "거래국 확인"
    ).upper()
    currency = str(_first_value(transaction, "currency", "settlement_currency") or "").upper()
    amount = _as_decimal(
        _first_value(transaction, "amount", "amount_fc", "transaction_amount", "invoice_amount")
    )
    amount_text = f"{amount:,.0f}" if amount is not None else "금액 확인"
    amount_label = f"{currency} {amount_text}".strip()
    return " · ".join(item for item in (country, direction_label, amount_label) if item)


def resolve_active_portfolio() -> tuple[Any, PortfolioAssessment]:
    workspace = build_demo_company_workspace()
    selected_label = st.session_state.get("competition_portfolio_company")
    if selected_label:
        for company_id, case in workspace.companies.items():
            label = case.identity.company_name or company_id
            if label == selected_label:
                workspace = workspace.switch_company(company_id)
                break
    case = workspace.active_case
    return case, analyze_trade_portfolio(case)


def build_executive_model(run) -> ExecutiveModel:
    summary = build_risk_first_summary(run)
    assets = list(getattr(run.updated_case, "official_data_assets", {}).values())
    reviewed = sum(1 for item in assets if item.status in {"available", "partial"})
    unavailable = sum(1 for item in assets if item.status not in {"available", "partial"})
    return ExecutiveModel(
        transaction_label=_transaction_label(run),
        disposition=summary.disposition,
        disposition_headline=summary.disposition_headline,
        disposition_explanation=summary.disposition_explanation,
        top_risk_title=summary.top_risks[0].title if summary.top_risks else "중대한 순위 위험 없음",
        missing_information_count=len(summary.missing_information),
        reviewed_data_count=reviewed,
        unavailable_data_count=unavailable,
        product_cards=tuple(build_product_consultation_cards(run, limit=3)),
        summary=summary,
    )


def render_executive_hero() -> None:
    st.markdown("""
    <section class="tg-exec-hero"><div><small>KB TRADEGUARD AI · 거래 의사결정 COCKPIT</small><h1>거래 확정 전, 위험·현금 공백·금융 행동을 한 화면에서 확인합니다</h1><p>여러 수출입 거래와 공식데이터를 연결해 무엇이 위험한지, 어떤 시나리오가 손익과 유동성에 영향을 주는지, 어느 상담을 먼저 준비해야 하는지 근거 ID와 함께 제시합니다.</p></div><div class="tg-exec-hero-side"><div class="tg-exec-hero-chip"><strong>판정</strong><span>진행 전 보완조건과 상위 위험</span></div><div class="tg-exec-hero-chip"><strong>시나리오</strong><span>FX·현금흐름·자연헤지 변화</span></div><div class="tg-exec-hero-chip"><strong>금융지원</strong><span>우선 상담 3개와 준비자료</span></div></div></section><div class="tg-boundary">공개 합성 거래를 사용하는 상담 준비용 프로토타입입니다. 은행 승인, 체결환율, 금리·한도, 상품 적격성, 보험 인수, 법률·제재 판단을 확정하지 않습니다.</div>
    """, unsafe_allow_html=True)


def render_compact_stage_header(stage: str) -> None:
    label = STAGE_LABELS.get(stage, STAGE_LABELS["decision"])
    descriptions = {
        "decision": "거래 판정과 최우선 행동",
        "scenarios": "FX·현금흐름·자연헤지 변화",
        "support": "우선 상담 후보와 준비자료",
        "evidence": "공식데이터·AI 경계·감사 근거",
    }
    st.markdown(
        f'<section class="tg-exec-mini"><div><small>KB TRADEGUARD AI · GUIDED REVIEW</small><strong>{escape(label)}</strong></div><span>{escape(descriptions.get(stage, descriptions["decision"]))}</span></section>',
        unsafe_allow_html=True,
    )


def _query_value(name: str, default: str) -> str:
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        value = value[0] if value else default
    return str(value)


def render_stage_selector() -> str:
    allowed = list(STAGE_LABELS)
    current = _query_value("stage", "decision")
    if current not in allowed:
        current = "decision"
    labels = [STAGE_LABELS[item] for item in allowed]
    selected = st.radio("검토 단계", labels, index=allowed.index(current), horizontal=True, label_visibility="collapsed", key="competition_guided_stage")
    selected_code = allowed[labels.index(selected)]
    if selected_code != current:
        st.query_params["stage"] = selected_code
        st.rerun()
    st.markdown('<div class="tg-stage-shell">판정 → 시나리오 → 금융지원 → 근거 순서로 검토합니다. 각 단계는 같은 결정론적 case와 계산 ID를 공유합니다.</div>', unsafe_allow_html=True)
    return selected_code


def render_mobile_stage_nav(active_stage: str, scenario_id: str) -> None:
    study_value = _query_value("study", "").strip().lower()
    study_enabled = study_value in {"1", "true", "yes", "on"}
    links = []
    for code, label in STAGE_LABELS.items():
        short = label.split("·", 1)[1].strip()
        study_query = "&study=true" if study_enabled else ""
        links.append(
            f'<a href="?scenario={escape(scenario_id)}&stage={code}{study_query}" '
            f'data-active="{str(code == active_stage).lower()}">{escape(short)}</a>'
        )
    st.markdown(
        '<nav class="tg-mobile-stage-nav" aria-label="TradeGuard guided stages">'
        + "".join(links)
        + "</nav>",
        unsafe_allow_html=True,
    )


def render_decision_cockpit(run) -> ExecutiveModel:
    from .assessment_app_presentation import disposition_presentation

    model = build_executive_model(run)
    presentation = disposition_presentation(model.disposition)
    st.markdown('<div id="decision" class="tg-section-anchor"></div><div class="tg-section-title">01 · 거래 의사결정 Cockpit</div>', unsafe_allow_html=True)
    risk_count = len(model.summary.top_risks)
    action_count = len(model.summary.next_actions)
    candidate_count = len(model.product_cards)
    st.markdown(f"""
    <div class="tg-cockpit"><section class="tg-decision-card" data-tone="{escape(presentation.tone)}"><small>{escape(model.transaction_label)} · {escape(presentation.eyebrow)}</small><h2>{escape(model.disposition_headline)}</h2><p>{escape(model.disposition_explanation)}</p><p><strong>가장 먼저 볼 위험</strong> · {escape(model.top_risk_title)}</p><p><strong>추가 확인</strong> · {model.missing_information_count}개 정보</p></section><div class="tg-cockpit-metrics"><div class="tg-cockpit-metric"><small>상위 위험</small><strong>{risk_count}건</strong><span>현재 단일 거래 Decision Brief 기준</span></div><div class="tg-cockpit-metric"><small>추가 확인</small><strong>{model.missing_information_count}건</strong><span>거래 확정 전 보완할 정보</span></div><div class="tg-cockpit-metric"><small>우선 행동</small><strong>{action_count}건</strong><span>의존관계를 반영한 실행 순서</span></div><div class="tg-cockpit-metric"><small>상담 후보</small><strong>{candidate_count}건</strong><span>가입·승인이 아닌 상담 준비 후보</span></div></div></div>
    """, unsafe_allow_html=True)
    action_text = " → ".join(f"{item.sequence}. {item.title}" for item in model.summary.next_actions[:3]) or "현재 생성된 실행 행동 없음"
    st.markdown(f'<div class="tg-priority-strip"><strong>지금 할 일</strong><span>{escape(action_text)}</span></div>', unsafe_allow_html=True)
    return model


def build_fx_stress_figure(assessment: PortfolioAssessment) -> go.Figure:
    points = [item for item in assessment.stress_points if item.estimated_fx_value_change_krw is not None]
    x = [f"{float(item.shock_percent):+g}%" for item in points]
    y = [float(item.estimated_fx_value_change_krw) for item in points]
    colors = ["#b52431" if value < 0 else "#147455" for value in y]
    fig = go.Figure(go.Bar(x=x, y=y, marker_color=colors, text=[f"{value/1e6:+.1f}m" for value in y], textposition="outside"))
    fig.update_layout(title="환율 충격별 추정 가치변화", height=330, margin=dict(l=12, r=12, t=52, b=20), yaxis_title="KRW", xaxis_title="동시 환율 충격", showlegend=False)
    fig.add_hline(y=0, line_color="#8390a4", line_width=1)
    return fig


def build_liquidity_figure(assessment: PortfolioAssessment) -> go.Figure:
    buckets = [item for item in assessment.liquidity_buckets if item.ending_cash_krw is not None]
    x = [item.period for item in buckets]
    y = [float(item.ending_cash_krw) for item in buckets]
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines+markers", line=dict(width=3, color="#1b63e9"), marker=dict(size=8, color=["#b52431" if value < 0 else "#1b63e9" for value in y]), fill="tozeroy", fillcolor="rgba(27,99,233,.10)"))
    fig.add_hline(y=0, line_dash="dash", line_color="#b52431")
    fig.update_layout(title="월별 예상 기말현금", height=330, margin=dict(l=12, r=12, t=52, b=20), yaxis_title="KRW", xaxis_title="결제월", showlegend=False)
    return fig


def build_exposure_waterfall(assessment: PortfolioAssessment) -> go.Figure:
    candidates = [item for item in assessment.currency_exposures if item.net_exposure_fc is not None]
    if not candidates:
        return go.Figure().update_layout(title="통화 노출 자료 없음", height=330)
    exposure = max(
        candidates,
        key=lambda item: (
            abs(item.net_exposure_krw)
            if item.net_exposure_krw is not None
            else Decimal("-1")
        ),
    )
    export_value = float(exposure.export_receivables_fc)
    import_value = -float(exposure.import_payables_fc)
    cash_value = float(exposure.foreign_cash_fc)
    fig = go.Figure(go.Waterfall(measure=["absolute", "relative", "relative", "total"], x=["수출채권", "수입채무", "외화현금", "순노출"], y=[export_value, import_value, cash_value, 0], text=[f"{export_value:,.0f}", f"{import_value:,.0f}", f"{cash_value:,.0f}", f"{float(exposure.net_exposure_fc):,.0f}"], textposition="outside", connector={"line": {"color": "#8b98aa"}}, increasing={"marker": {"color": "#147455"}}, decreasing={"marker": {"color": "#b52431"}}, totals={"marker": {"color": "#1b63e9"}}))
    fig.update_layout(title=f"{exposure.currency} 노출 구성", height=330, margin=dict(l=12, r=12, t=52, b=20), yaxis_title=exposure.currency, showlegend=False)
    return fig


def render_scenario_story(assessment: PortfolioAssessment) -> None:
    st.markdown('<div id="scenarios" class="tg-section-anchor"></div><div class="tg-section-title">02 · 손익·유동성·자연헤지 시나리오</div>', unsafe_allow_html=True)
    left, middle, right = st.columns(3)
    with left:
        st.plotly_chart(build_fx_stress_figure(assessment), use_container_width=True, config={"displayModeBar": False})
    with middle:
        st.plotly_chart(build_liquidity_figure(assessment), use_container_width=True, config={"displayModeBar": False})
    with right:
        st.plotly_chart(build_exposure_waterfall(assessment), use_container_width=True, config={"displayModeBar": False})
    st.markdown('<div class="tg-chart-note"><strong>해석 경계</strong> · 환율 민감도는 모든 대상 통화가 같은 비율로 움직인다는 공개 스트레스입니다. 외화현금은 자산으로 별도 표시하며, 자연헤지는 동일통화 수출채권과 수입채무의 상계 가능 규모일 뿐 법적 상계권이나 만기 일치를 확정하지 않습니다.</div>', unsafe_allow_html=True)


def build_handoff_payload(run, model: ExecutiveModel) -> dict[str, Any]:
    brief = run.assessment_result.brief
    identity = getattr(run.updated_case, "identity", None)
    case_id = str(getattr(identity, "case_id", ""))
    brief_reference_ids = list(
        dict.fromkeys(
            [
                *brief.country_fact_ids,
                *brief.compliance_screening_ids,
                *brief.calculation_ids,
                *brief.product_candidate_ids,
                *brief.consultation_requirement_ids,
            ]
        )
    )
    return {
        "schema_version": "kb-tradeguard-consultation-handoff/1.0",
        "case_id": case_id,
        "transaction_label": model.transaction_label,
        "disposition": model.disposition,
        "disposition_headline": model.disposition_headline,
        "top_risks": [{"rank": item.rank, "title": item.title, "severity": item.severity, "reference_ids": list(item.reference_ids)} for item in model.summary.top_risks[:3]],
        "missing_information": list(model.summary.missing_information),
        "priority_actions": [{"sequence": item.sequence, "title": item.title, "responsible_party": item.responsible_party, "dependency_action_ids": list(item.dependency_action_ids)} for item in model.summary.next_actions[:3]],
        "consultation_candidates": [{"candidate_id": item.candidate_id, "provider": item.provider, "product_name": item.product_name, "status": item.status, "matched_needs": list(item.matched_needs), "unresolved_conditions": list(item.unresolved_conditions), "next_action": item.next_action} for item in model.product_cards],
        "brief_reference_ids": brief_reference_ids,
        "authority_boundary": "Consultation preparation only. No approval, eligibility, pricing, limit, insurance acceptance, guarantee issuance, legal advice, or executable hedge instruction.",
    }


def render_financial_support(run, model: ExecutiveModel, *, presentation_mode: bool) -> None:
    st.markdown('<div id="support" class="tg-section-anchor"></div><div class="tg-section-title">03 · 우선 금융지원과 KB 상담 Handoff</div>', unsafe_allow_html=True)
    st.caption("전체 registry를 나열하지 않고 현재 Decision Brief에 선택된 상위 상담 후보 3개만 먼저 표시합니다.")
    if not model.product_cards:
        st.info("현재 Decision Brief에 선택된 상담 후보가 없습니다.")
    else:
        columns = st.columns(len(model.product_cards))
        for rank, (column, card) in enumerate(zip(columns, model.product_cards), start=1):
            reason = " · ".join(card.matched_needs) or "거래 목적"
            unresolved = " / ".join(card.unresolved_conditions) or "공식 조건 재확인"
            with column:
                st.markdown(f'<article class="tg-product-priority" data-rank="{rank}"><small>우선 상담 {rank} · {escape(card.provider)}</small><h3>{escape(card.product_name)}</h3><p><strong>선정 이유</strong> · {escape(reason)}</p><p><strong>미확인 조건</strong> · {escape(unresolved)}</p><p><strong>다음 행동</strong> · {escape(card.next_action)}</p></article>', unsafe_allow_html=True)
    render_fx_consultation_comparison(run, presentation_mode=presentation_mode)
    handoff = build_handoff_payload(run, model)
    st.markdown('<section class="tg-handoff"><div><small>INDEPENDENT PROTOTYPE · 상담 준비 패키지</small><h3>고객의 거래 검토 결과를 KB 기업금융·외환 상담으로 넘길 때 필요한 정보를 한 묶음으로 정리합니다</h3><p>위험, 누락정보, 행동순서, 상담 후보와 근거 ID를 함께 전달해 고객이 같은 설명을 반복하지 않도록 돕습니다. 실제 KB 내부 시스템 연계나 상담 예약이 구현됐다는 의미는 아닙니다.</p></div><div class="tg-handoff-path"><div class="tg-handoff-step"><strong>고객</strong> · 거래조건과 문서 확인</div><div class="tg-handoff-step"><strong>TradeGuard</strong> · 위험·시나리오·준비자료 구조화</div><div class="tg-handoff-step"><strong>상담 담당자</strong> · 적격성·가격·한도와 실제 실행 검토</div></div></section>', unsafe_allow_html=True)
    if not presentation_mode:
        st.download_button("상담 준비 패키지 JSON 저장", data=(json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"), file_name="kb-tradeguard-consultation-handoff.json", mime="application/json", use_container_width=True)
        with st.expander("전체 금융상품 후보와 공식 조건", expanded=False):
            import assessment_app as detailed
            detailed._render_product_tab(run)


def _impact_text(case_id: str, title: str) -> tuple[str, str]:
    token = f"{case_id} {title}".lower()
    if "vn" in token or "베트남" in token:
        return "국가·통화 집중도 확인", "거시·교역 맥락을 추가하지만 바이어 신용이나 보험 인수 가능성을 단독 판단하지 않습니다."
    if "us" in token or "미국" in token:
        return "시장·품목 규모 맥락", "시장성과 교역 규모를 설명하지만 특정 기업 매출이나 수출 성공 가능성을 보장하지 않습니다."
    return "수입원가·공급 의존 맥락", "수입 규모와 거시환경을 원가 스트레스 참고로 사용하며 공급자 신뢰도나 결제 승인을 확정하지 않습니다."


def render_data_decision_impact() -> None:
    st.markdown('<div id="evidence" class="tg-section-anchor"></div><div class="tg-section-title">04 · 공식데이터가 판단에 미치는 영향</div>', unsafe_allow_html=True)
    cards = []
    for item in build_official_case_study_summaries():
        label, impact = _impact_text(item["case_id"], item["title"])
        cards.append(f'<article class="tg-impact-card"><small>{escape(item["country_code"])} · HS {escape(item["hs_code"])}</small><h4>{escape(label)}</h4><p>{escape(impact)}</p><p><strong>데이터 기준</strong> · World Bank 관측연도별 최신 비결측치 / UN Comtrade {escape(item["comtrade_period"])} 집계</p></article>')
    st.markdown('<div class="tg-impact-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def provider_configuration_status() -> list[dict[str, str]]:
    providers = [
        ("World Bank", "public", "공개 endpoint · 국가 거시지표"),
        ("UN Comtrade", "public", "공개 Preview endpoint · 국가·품목 통계"),
        ("KEXIM", "configured" if os.getenv("KEXIM_API_KEY") else "missing", "KEXIM_API_KEY"),
        ("관세청", "configured" if (os.getenv("KCS_TRADE_API_KEY") or os.getenv("DATA_GO_KR_SERVICE_KEY")) else "missing", "KCS_TRADE_API_KEY 또는 DATA_GO_KR_SERVICE_KEY"),
        ("BOK ECOS", "configured" if os.getenv("BOK_ECOS_API_KEY") else "missing", "BOK_ECOS_API_KEY"),
        ("OpenDART", "configured" if os.getenv("OPENDART_API_KEY") else "missing", "OPENDART_API_KEY"),
        ("국세청", "configured" if (os.getenv("NTS_BUSINESS_API_KEY") or os.getenv("DATA_GO_KR_SERVICE_KEY")) else "missing", "NTS_BUSINESS_API_KEY 또는 DATA_GO_KR_SERVICE_KEY"),
    ]
    return [{"provider": name, "state": state, "detail": detail} for name, state, detail in providers]


def render_api_status_matrix() -> None:
    labels = {"public": "공개 조회 가능", "configured": "Secret 설정됨", "missing": "Secret 미설정"}
    cards = []
    for item in provider_configuration_status():
        cards.append(f'<div class="tg-api-card"><strong>{escape(item["provider"])}</strong><span>{escape(item["detail"])}</span><span class="tg-api-state" data-state="{escape(item["state"])}">{escape(labels[item["state"]])}</span></div>')
    st.markdown("#### 공식 API 연결 상태")
    st.markdown('<div class="tg-api-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)
    st.caption("Secret 미설정 provider는 live 성공으로 표시하지 않습니다. 공개 endpoint와 설정된 provider만 smoke 대상이며, 실시간 응답은 검토 Snapshot 경계 전에는 거래판정에 자동 반영되지 않습니다.")
