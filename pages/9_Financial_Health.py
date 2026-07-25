"""Transparent OpenDART financial-health screening page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data_providers import (
    OpenDARTProvider,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderResponseError,
)
from src.intelligence import analyze_financial_health

st.set_page_config(page_title="기업 재무건전성", page_icon="🏢", layout="wide")
st.title("기업 재무건전성 사전 스크리닝")
st.caption(
    "OpenDART 공시 재무제표에서 핵심 계정을 추출해 유동성·레버리지·수익성·이자상환여력을 계산합니다. "
    "공식 신용등급, 부도확률, 대출 승인 또는 상품 적합성 판단이 아닙니다."
)

_METRIC_LABELS = {
    "current_ratio_pct": "유동비율",
    "debt_ratio_pct": "부채비율",
    "equity_ratio_pct": "자기자본비율",
    "operating_margin_pct": "영업이익률",
    "net_margin_pct": "순이익률",
    "interest_coverage_ratio": "이자보상배율",
    "operating_cash_flow_krw": "영업현금흐름",
}
_BAND_LABELS = {
    "high_review_priority": "높은 검토 우선순위",
    "review_required": "추가 검토 필요",
    "insufficient_data": "데이터 부족",
    "no_major_flag_detected": "중대 플래그 미탐지",
}
_SEVERITY_LABELS = {
    "high": "높음",
    "review": "검토",
    "stable": "안정",
}


def _render_error(exc: Exception) -> None:
    if isinstance(exc, ProviderConfigurationError):
        st.error(f"환경변수 설정 오류: {exc}")
    elif isinstance(exc, ProviderRequestError):
        st.warning(f"외부 API가 현재 요청을 처리하지 못했습니다: {exc}")
    elif isinstance(exc, ProviderResponseError):
        st.error(f"공급자 응답 오류: {exc}")
    else:
        st.error(f"처리 오류: {exc}")


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_financials(
    corp_code: str,
    business_year: int,
    report_code: str,
    fs_div: str,
) -> dict:
    return OpenDARTProvider().get_financial_statements(
        corp_code,
        business_year,
        report_code=report_code,
        fs_div=fs_div,
    )


provider = OpenDARTProvider()
st.metric("OpenDART API", "설정됨" if provider.is_configured else "미설정")

input_col, option_col = st.columns(2)
with input_col:
    corp_code = st.text_input("DART 8자리 고유번호", value="00126380")
    business_year = int(
        st.number_input("사업연도", min_value=2015, max_value=2100, value=2025)
    )
with option_col:
    report_label = st.selectbox(
        "보고서",
        ["사업보고서", "1분기보고서", "반기보고서", "3분기보고서"],
    )
    fs_label = st.radio("재무제표 구분", ["연결", "별도"], horizontal=True)

report_codes = {
    "사업보고서": "11011",
    "1분기보고서": "11013",
    "반기보고서": "11012",
    "3분기보고서": "11014",
}
fs_div = "CFS" if fs_label == "연결" else "OFS"

if st.button("재무건전성 분석", type="primary"):
    try:
        snapshot = _fetch_financials(
            corp_code,
            business_year,
            report_codes[report_label],
            fs_div,
        )
        if not snapshot["results"]:
            st.warning("해당 조건으로 조회된 재무제표가 없습니다.")
            st.stop()

        result = analyze_financial_health(snapshot["results"])
        top_left, top_middle, top_right = st.columns(3)
        top_left.metric("내부 스크리닝 밴드", _BAND_LABELS[result.screening_band])
        top_middle.metric("지표 데이터 충족률", f"{result.data_coverage_ratio:.0%}")
        top_right.metric("추출 공시 계정", f"{result.extracted_accounts['value'].notna().sum()}개")

        st.subheader("핵심 재무지표")
        metrics = result.metrics.copy()
        metrics["지표"] = metrics["metric"].map(_METRIC_LABELS)
        metrics["값"] = metrics["value"]
        metrics["단위"] = metrics["unit"]
        metrics["산식"] = metrics["formula"]
        metrics["사용 계정"] = metrics["inputs"]
        st.dataframe(
            metrics[["지표", "값", "단위", "산식", "사용 계정", "available"]],
            column_config={"available": st.column_config.CheckboxColumn("계산 가능")},
            width="stretch",
            hide_index=True,
        )

        st.subheader("검토 플래그")
        if result.flags.empty:
            st.info("계산 가능한 지표에서 플래그가 생성되지 않았습니다.")
        else:
            flags = result.flags.copy()
            flags["지표"] = flags["metric"].map(_METRIC_LABELS)
            flags["심각도"] = flags["severity"].map(_SEVERITY_LABELS)
            flags["값"] = flags["value"]
            flags["해석"] = flags["message"]
            st.dataframe(
                flags[["지표", "값", "심각도", "해석"]],
                width="stretch",
                hide_index=True,
            )

        with st.expander("계정 추출 근거", expanded=False):
            extracted = result.extracted_accounts.copy()
            extracted = extracted.rename(
                columns={
                    "account_key": "내부 계정키",
                    "value": "추출 금액",
                    "matched_by": "매칭 기준",
                    "account_id": "공시 account_id",
                    "account_name": "공시 계정명",
                    "statement_name": "재무제표명",
                    "raw_amount": "원문 금액",
                    "row_order": "원문 행순서",
                }
            )
            st.dataframe(extracted, width="stretch", hide_index=True)

        with st.expander("원본 공시 계정", expanded=False):
            raw = pd.DataFrame(snapshot["results"])
            preferred = [
                column
                for column in (
                    "sj_nm",
                    "account_id",
                    "account_nm",
                    "thstrm_nm",
                    "thstrm_amount",
                    "frmtrm_nm",
                    "frmtrm_amount",
                    "currency",
                )
                if column in raw.columns
            ]
            st.dataframe(raw[preferred] if preferred else raw, width="stretch", hide_index=True)

        st.subheader("해석 제한")
        for limitation in result.limitations:
            st.write(f"- {limitation}")
        st.caption(
            f"OpenDART 조회시각 {snapshot['retrieved_at']} · 응답 해시 "
            f"{snapshot['response_hash'][:16]}… · {business_year}년 {report_label} {fs_label}"
        )
    except Exception as exc:  # Streamlit boundary
        _render_error(exc)
