"""Competition view for three pinned real-public-data context cases."""
from __future__ import annotations

from typing import Any

import streamlit as st

from .official_case_studies import load_pinned_official_context_dataset

_INDICATORS = {
    "NY.GDP.MKTP.KD.ZG": ("GDP 성장률", "%"),
    "FP.CPI.TOTL.ZG": ("소비자물가 상승률", "%"),
    "FI.RES.TOTL.MO": ("수입 대비 외환보유액", "개월"),
    "BN.CAB.XOKA.GD.ZS": ("경상수지/GDP", "%"),
}

CASE_STUDY_CSS = """
<style>
.tg-case-boundary {border:1px solid #cdd9e8;border-left:6px solid #0d95aa;border-radius:16px;padding:.82rem .9rem;background:#f3fbfc;color:#52627a;font-size:.76rem;line-height:1.52;margin-bottom:.7rem;}
.tg-case-card {border:1px solid #dce4ef;border-radius:18px;padding:.92rem;background:#fff;min-height:380px;box-shadow:0 8px 22px rgba(15,36,68,.05);}
.tg-case-card small {font-size:.64rem;font-weight:900;letter-spacing:.08em;color:#748198;}
.tg-case-card h3 {margin:.35rem 0 .42rem;font-size:1rem;color:#172033;}
.tg-case-card p {margin:.18rem 0 .58rem;color:#647084;font-size:.75rem;line-height:1.48;}
.tg-case-metrics {display:grid;grid-template-columns:1fr 1fr;gap:.42rem;margin:.55rem 0;}
.tg-case-metric {border:1px solid #e1e8f1;border-radius:12px;padding:.55rem;background:#f8fafc;}
.tg-case-metric strong {display:block;font-size:.85rem;color:#172033;}
.tg-case-metric span {display:block;margin-top:.12rem;font-size:.62rem;color:#748198;line-height:1.3;}
.tg-case-trade {border-radius:13px;padding:.68rem;background:#07172d;color:#fff;margin-top:.6rem;}
.tg-case-trade strong {display:block;font-size:1.05rem;}
.tg-case-trade span {font-size:.65rem;opacity:.78;}
.tg-case-impact {border-left:4px solid #0d95aa;border-radius:10px;padding:.55rem .62rem;background:#eefafb;color:#52627a;font-size:.67rem;line-height:1.42;margin-top:.55rem;}
@media(max-width:760px) {.tg-case-card{min-height:auto}.tg-case-metrics{grid-template-columns:1fr 1fr;}}
</style>
"""


def _format_number(value: Any, unit: str) -> str:
    number = float(value)
    if unit == "%":
        return f"{number:.2f}%"
    if unit == "개월":
        return f"{number:.2f}개월"
    return f"{number:,.2f}"


def _format_usd(value: Any) -> str:
    number = float(value)
    if abs(number) >= 1_000_000_000:
        return f"US$ {number / 1_000_000_000:.2f}bn"
    if abs(number) >= 1_000_000:
        return f"US$ {number / 1_000_000:.1f}m"
    return f"US$ {number:,.0f}"


def build_official_case_study_summaries() -> list[dict[str, Any]]:
    dataset = load_pinned_official_context_dataset()
    summaries: list[dict[str, Any]] = []
    for case in dataset.cases:
        by_key = {source.asset_key: source for source in case.sources}
        macro_source = by_key["world_bank_country_macro"]
        trade_key = "un_comtrade_export" if case.trade_flow_code == "X" else "un_comtrade_import"
        trade_source = by_key[trade_key]
        macro_payload = macro_source.payload if isinstance(macro_source.payload, dict) else {}
        metrics = []
        for wrapper in macro_payload.get("results") or []:
            if not isinstance(wrapper, dict) or not isinstance(wrapper.get("results"), dict):
                continue
            observation = wrapper["results"]
            code = str(observation.get("indicator_code") or wrapper.get("indicator_code") or "")
            label, unit = _INDICATORS.get(code, (code, ""))
            metrics.append({
                "indicator_code": code,
                "label": label,
                "value": observation.get("value"),
                "unit": unit,
                "observation_year": observation.get("observation_year"),
                "response_hash": wrapper.get("response_hash"),
            })
        trade_payload = trade_source.payload if isinstance(trade_source.payload, dict) else {}
        trade_rows = trade_payload.get("results") or []
        trade_row = trade_rows[0] if trade_rows and isinstance(trade_rows[0], dict) else {}
        summaries.append({
            "case_id": case.case_id,
            "title": case.title,
            "decision_question": case.decision_question,
            "country_code": case.country_code,
            "hs_code": case.hs_code,
            "flow_label": "수출" if case.trade_flow_code == "X" else "수입",
            "comtrade_period": case.comtrade_period,
            "trade_value_usd": trade_row.get("primary_value_usd"),
            "metrics": metrics,
            "generated_at": case.generated_at.isoformat(),
            "macro_retrieved_at": macro_source.retrieved_at.isoformat() if macro_source.retrieved_at else None,
            "trade_retrieved_at": trade_source.retrieved_at.isoformat() if trade_source.retrieved_at else None,
            "macro_response_hash": macro_source.response_hash,
            "trade_response_hash": trade_source.response_hash,
            "authority_boundary": dataset.authority_boundary,
        })
    return summaries


def render_official_case_study_section(*, presentation_mode: bool) -> None:
    st.markdown(CASE_STUDY_CSS, unsafe_allow_html=True)
    st.markdown('<div id="cases" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">실제 공개데이터 사례 3개</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tg-case-boundary"><strong>사례 경계</strong> · 거래 질문과 기업은 합성이며, 아래 숫자만 2026년 7월 29일에 실제 World Bank·UN Comtrade 공개 API에서 수집해 고정한 Snapshot입니다. 관측연도는 지표별로 다르고 이후 수정될 수 있습니다.</div>',
        unsafe_allow_html=True,
    )
    summaries = build_official_case_study_summaries()
    columns = st.columns(3)
    for column, item in zip(columns, summaries):
        with column:
            metric_html = "".join(
                f'<div class="tg-case-metric"><strong>{_format_number(metric["value"], metric["unit"])}</strong><span>{metric["label"]} · {metric["observation_year"]}</span></div>'
                for metric in item["metrics"] if metric["value"] is not None
            )
            trade_value = _format_usd(item["trade_value_usd"]) if item["trade_value_usd"] is not None else "자료 없음"
            st.markdown(
                f'''
                <article class="tg-case-card">
                  <small>{item["country_code"]} · HS {item["hs_code"]} · {item["flow_label"]}</small>
                  <h3>{item["title"]}</h3>
                  <p>{item["decision_question"]}</p>
                  <div class="tg-case-metrics">{metric_html}</div>
                  <div class="tg-case-trade"><strong>{trade_value}</strong><span>한국 기준 {item["comtrade_period"]}년 HS {item["hs_code"]} {item["flow_label"]} 집계</span></div>
                  <div class="tg-case-impact"><strong>판단 영향</strong> · 국가·통화 집중도와 상담 질문을 보강하는 참고정보이며, 특정 바이어 신용·거래 승인·상품 적격성을 단독 확정하지 않습니다.</div>
                </article>
                ''',
                unsafe_allow_html=True,
            )
            if not presentation_mode:
                with st.expander("출처·hash 확인", expanded=False):
                    st.caption(f'World Bank 조회시각 · {item["macro_retrieved_at"]}')
                    st.code(item["macro_response_hash"], language=None)
                    st.caption(f'UN Comtrade 조회시각 · {item["trade_retrieved_at"]}')
                    st.code(item["trade_response_hash"], language=None)
                    st.warning("집계 통계이며 특정 기업의 실적·신용·거래 승인 근거가 아닙니다.")
