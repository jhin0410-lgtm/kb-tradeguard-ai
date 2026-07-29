"""Multi-year OpenDART financial trend screening page."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_providers import (
    OpenDARTProvider,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderResponseError,
)
from src.intelligence import analyze_financial_trends

st.set_page_config(page_title="기업 재무추세", page_icon="📈", layout="wide")
st.title("최근 다년 기업 재무추세 스크리닝")
st.caption(
    "동일 기업·보고서 유형·연결범위의 OpenDART 공시를 연도별로 비교합니다. "
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
_ACCOUNT_LABELS = {
    "assets": "자산총계",
    "current_assets": "유동자산",
    "liabilities": "부채총계",
    "current_liabilities": "유동부채",
    "equity": "자본총계",
    "revenue": "매출액",
    "operating_profit": "영업이익",
    "net_income": "당기순이익",
    "interest_expense": "금융원가",
    "operating_cash_flow": "영업현금흐름",
}
_BAND_LABELS = {
    "high_review_priority": "높은 검토 우선순위",
    "review_required": "추가 검토 필요",
    "insufficient_data": "데이터 부족",
    "no_major_flag_detected": "단년도 중대 플래그 미탐지",
    "no_major_trend_flag_detected": "중대 추세 플래그 미탐지",
}
_SEVERITY_LABELS = {"high": "높음", "review": "검토", "stable": "안정"}


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

input_col, period_col, scope_col = st.columns(3)
with input_col:
    corp_code = st.text_input("DART 8자리 고유번호", value="00126380")
with period_col:
    latest_year = int(
        st.number_input("최근 사업연도", min_value=2017, max_value=2100, value=2025)
    )
    year_count = int(
        st.number_input("비교 연도 수", min_value=2, max_value=5, value=3)
    )
with scope_col:
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
years = list(range(latest_year - year_count + 1, latest_year + 1))
st.info(
    f"비교 범위: {years[0]}~{years[-1]}년 · {report_label} · {fs_label}. "
    "서로 다른 연결범위나 보고서 유형은 한 분석에서 혼합하지 않습니다."
)

if st.button("다년 재무추세 분석", type="primary"):
    try:
        snapshots = {
            year: _fetch_financials(
                corp_code,
                year,
                report_codes[report_label],
                fs_div,
            )
            for year in years
        }
        result = analyze_financial_trends(snapshots)

        top_left, top_middle, top_right, top_fourth = st.columns(4)
        top_left.metric(
            "다년 추세 밴드", _BAND_LABELS[result.trend_screening_band]
        )
        top_middle.metric(
            "최근연도 단년도 밴드", _BAND_LABELS[result.latest_screening_band]
        )
        top_right.metric("평균 데이터 충족률", f"{result.overall_coverage_ratio:.0%}")
        top_fourth.metric("비교 연도", f"{len(result.years)}개")

        st.subheader("연도별 데이터 상태")
        summary = result.year_summary.copy()
        summary["단년도 밴드"] = summary["screening_band"].map(_BAND_LABELS)
        summary["데이터 충족률"] = summary["data_coverage_ratio"]
        summary["공시 계정 수"] = summary["result_count"]
        st.dataframe(
            summary[
                [
                    "year",
                    "단년도 밴드",
                    "데이터 충족률",
                    "공시 계정 수",
                    "report_code",
                    "fs_div",
                    "retrieved_at",
                    "response_hash",
                ]
            ],
            column_config={
                "year": "사업연도",
                "데이터 충족률": st.column_config.ProgressColumn(
                    "데이터 충족률", min_value=0.0, max_value=1.0, format="percent"
                ),
                "response_hash": "응답 해시",
            },
            width="stretch",
            hide_index=True,
        )

        st.subheader("재무비율 추세")
        ratio_metrics = {
            key
            for key in (
                "current_ratio_pct",
                "debt_ratio_pct",
                "equity_ratio_pct",
                "operating_margin_pct",
                "net_margin_pct",
            )
        }
        ratios = result.annual_metrics[
            result.annual_metrics["metric"].isin(ratio_metrics)
            & result.annual_metrics["available"]
        ].copy()
        ratios["지표"] = ratios["metric"].map(_METRIC_LABELS)
        if ratios.empty:
            st.warning("비율 추세를 그릴 수 있는 공시 계정이 부족합니다.")
        else:
            st.plotly_chart(
                px.line(
                    ratios,
                    x="year",
                    y="value",
                    color="지표",
                    markers=True,
                    labels={"year": "사업연도", "value": "비율(%)"},
                ),
                width="stretch",
            )
            st.dataframe(
                ratios[["year", "지표", "value", "formula", "inputs"]].rename(
                    columns={
                        "year": "사업연도",
                        "value": "값",
                        "formula": "산식",
                        "inputs": "사용 계정",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

        st.subheader("핵심 공시금액 추세")
        available_account_keys = [
            key
            for key in _ACCOUNT_LABELS
            if not result.annual_accounts[
                (result.annual_accounts["account_key"] == key)
                & result.annual_accounts["value"].notna()
            ].empty
        ]
        if not available_account_keys:
            st.warning("금액 추세를 그릴 수 있는 공시 계정이 없습니다.")
        else:
            selected_account = st.selectbox(
                "차트 계정",
                available_account_keys,
                format_func=lambda key: _ACCOUNT_LABELS[key],
            )
            account_trend = result.annual_accounts[
                result.annual_accounts["account_key"] == selected_account
            ].copy()
            account_trend["계정"] = account_trend["account_key"].map(_ACCOUNT_LABELS)
            st.plotly_chart(
                px.line(
                    account_trend,
                    x="year",
                    y="value",
                    markers=True,
                    labels={"year": "사업연도", "value": "공시금액(원)"},
                ),
                width="stretch",
            )
            st.dataframe(
                account_trend[
                    [
                        "year",
                        "계정",
                        "value",
                        "matched_by",
                        "account_id",
                        "account_name",
                        "raw_amount",
                    ]
                ].rename(
                    columns={
                        "year": "사업연도",
                        "value": "추출 금액",
                        "matched_by": "매칭 기준",
                        "account_id": "공시 account_id",
                        "account_name": "공시 계정명",
                        "raw_amount": "원문 금액",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

        st.subheader("전년 대비 변화")
        changes = result.changes.copy()
        changes["항목"] = changes.apply(
            lambda row: (
                _METRIC_LABELS.get(row["series"], row["series"])
                if row["source"] == "metric"
                else _ACCOUNT_LABELS.get(row["series"], row["series"])
            ),
            axis=1,
        )
        focus_series = {
            "revenue",
            "operating_profit",
            "net_income",
            "operating_cash_flow",
            "current_ratio_pct",
            "debt_ratio_pct",
            "operating_margin_pct",
        }
        focus_changes = changes[changes["series"].isin(focus_series)].copy()
        st.dataframe(
            focus_changes[
                [
                    "year",
                    "previous_year",
                    "항목",
                    "value",
                    "previous_value",
                    "absolute_change",
                    "change_pct",
                    "direction",
                    "change_basis",
                    "unit",
                ]
            ].rename(
                columns={
                    "year": "사업연도",
                    "previous_year": "비교연도",
                    "value": "현재값",
                    "previous_value": "이전값",
                    "absolute_change": "절대변화",
                    "change_pct": "변화율(%)",
                    "direction": "방향",
                    "change_basis": "비교 기준",
                    "unit": "단위",
                }
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "전년 값이 0이거나 누락된 경우 변화율을 계산하지 않고 비교 불가 사유를 표시합니다."
        )

        st.subheader("다년 추세 검토 플래그")
        if result.flags.empty:
            st.success("가용 데이터에서 중대 다년 추세 플래그가 탐지되지 않았습니다.")
        else:
            flags = result.flags.copy()
            flags["항목"] = flags["series"].map(
                {**_METRIC_LABELS, **_ACCOUNT_LABELS, "data_availability": "데이터 가용성"}
            )
            flags["심각도"] = flags["severity"].map(_SEVERITY_LABELS)
            st.dataframe(
                flags[["항목", "latest_value", "심각도", "message"]].rename(
                    columns={
                        "latest_value": "최근값",
                        "message": "해석",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

        with st.expander("전체 계정 추출 근거", expanded=False):
            extracted = result.annual_accounts.copy()
            extracted["계정"] = extracted["account_key"].map(_ACCOUNT_LABELS)
            st.dataframe(extracted, width="stretch", hide_index=True)

        st.subheader("해석 제한")
        for limitation in result.limitations:
            st.write(f"- {limitation}")
    except Exception as exc:  # Streamlit boundary
        _render_error(exc)
