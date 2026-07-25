"""Integrated FX-source, exposure, cash-flow, and hedge analysis page."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.cashflow import CASH_FLOW_VIEWS, calculate_monthly_cashflow
from src.data_providers import (
    KEXIMFXProvider,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderResponseError,
)
from src.exposure import calculate_exposure
from src.fx_source_selection import FXInputSelection, select_fx_inputs
from src.portfolio_hedging import calculate_transaction_level_portfolio_hedge
from src.validators import validate_fx_rates, validate_transactions

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_TRANSACTIONS = ROOT / "data" / "sample_transactions.csv"
SAMPLE_COMPANY = ROOT / "data" / "sample_company.json"
SAMPLE_FX_RATES = ROOT / "data" / "sample_fx_rates.csv"

_SOURCE_LABELS = {
    "번들 샘플 가정": "bundled",
    "수동 입력": "manual",
    "한국수출입은행 공식 참고환율": "kexim",
}
_SOURCE_DISPLAY = {
    "bundled": "번들 샘플 가정",
    "manual": "수동 입력",
    "kexim_reference_spot": "한국수출입은행 공식 참고 현물환율",
    "bundled_fallback": "번들 샘플 명시적 fallback",
}

st.set_page_config(page_title="공식환율 통합 엔진", page_icon="💱", layout="wide")
st.title("공식 참고환율 × 환노출·현금흐름·헤지 엔진")
st.caption(
    "현물환율 데이터 소스를 명시적으로 선택해 기존 결정론적 계산엔진에 연결합니다. "
    "수출입은행 값은 공개 참고환율이며 실제 KB 고객 체결환율이나 선물환 견적이 아닙니다."
)


@st.cache_data
ndef_load_marker = None


@st.cache_data
def _load_transactions() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_TRANSACTIONS)


@st.cache_data
def _load_company() -> dict:
    return json.loads(SAMPLE_COMPANY.read_text(encoding="utf-8"))


@st.cache_data
def _load_base_rates() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_FX_RATES)


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_kexim(as_of_date: str) -> dict:
    return KEXIMFXProvider().fetch_latest_rates(as_of_date, lookback_days=10)


def _render_provider_error(exc: Exception) -> None:
    if isinstance(exc, ProviderConfigurationError):
        st.error(f"환경변수 설정 오류: {exc}")
    elif isinstance(exc, ProviderRequestError):
        st.warning(f"외부 API가 현재 요청을 처리하지 못했습니다: {exc}")
    elif isinstance(exc, ProviderResponseError):
        st.error(f"공급자 응답 오류: {exc}")
    else:
        st.error(f"처리 오류: {exc}")


def _selection_summary(selection: FXInputSelection) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "요청 소스": _SOURCE_DISPLAY.get(
                    selection.requested_source, selection.requested_source
                ),
                "적용 소스": _SOURCE_DISPLAY.get(
                    selection.applied_source, selection.applied_source
                ),
                "요청 기준일": selection.requested_as_of_date,
                "공표 관측일": selection.observation_date,
                "조회시각": selection.retrieved_at,
                "응답 해시": selection.response_hash,
                "경과일": selection.stale_days,
                "오래된 데이터": selection.is_stale,
                "fallback 사용": selection.used_fallback,
                "fallback 사유": selection.fallback_reason,
            }
        ]
    )


transactions = _load_transactions()
company = _load_company()
base_rates = _load_base_rates()
required_currencies = sorted(
    set(transactions["currency"].astype(str).str.upper())
    | {str(currency).upper() for currency in company["foreign_cash"]}
)

left, middle, right = st.columns(3)
with left:
    source_label = st.selectbox("현물환율 데이터 소스", list(_SOURCE_LABELS))
    source = _SOURCE_LABELS[source_label]
with middle:
    analysis_date = st.date_input("환율·헤지 기준일", value=date.today())
with right:
    stale_after_days = int(
        st.number_input("신선도 경고 기준(일)", min_value=0, max_value=30, value=3)
    )

allow_fallback = st.checkbox(
    "공식 API 실패 시 번들 샘플로 명시적 fallback",
    value=True,
    disabled=source != "kexim",
)

st.info(
    "필수 통화: "
    + ", ".join(required_currencies)
    + ". 공식 현물환율을 선택해도 KRW·외화 금리는 번들 데모 가정을 유지하며 별도로 표시합니다."
)

manual_rates = None
if source == "manual":
    st.subheader("수동 환율·금리 입력")
    manual_rates = st.data_editor(
        base_rates,
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        key="integrated_manual_fx_rates",
    )

cash_flow_view = st.selectbox("현금흐름 관점", list(CASH_FLOW_VIEWS), index=1)
hedge_ratio_pct = int(st.slider("거래통화 공통 헤지비율", 0, 100, 50))

if st.button("통합 분석 실행", type="primary"):
    snapshot = None
    provider_failure: Exception | None = None
    if source == "kexim":
        try:
            snapshot = _fetch_kexim(analysis_date.isoformat())
        except (
            ProviderConfigurationError,
            ProviderRequestError,
            ProviderResponseError,
        ) as exc:
            provider_failure = exc
            if not allow_fallback:
                _render_provider_error(exc)
                st.stop()

    try:
        selection = select_fx_inputs(
            base_rates,
            required_currencies,
            source=source,
            as_of_date=analysis_date,
            manual_rates=manual_rates,
            kexim_snapshot=snapshot,
            stale_after_days=stale_after_days,
            allow_bundled_fallback=bool(allow_fallback),
            fallback_reason=str(provider_failure) if provider_failure else None,
        )
        fx_rates = validate_fx_rates(selection.rates)
        portfolio = validate_transactions(transactions, fx_rates)
    except Exception as exc:
        _render_provider_error(exc)
        st.stop()

    if selection.used_fallback:
        st.warning(
            "공식 참고환율이 적용되지 않았습니다. 계산 전체에 번들 샘플을 사용했습니다. "
            f"사유: {selection.fallback_reason}"
        )
    elif selection.is_stale:
        st.warning(
            f"공식 환율 관측일이 기준일보다 {selection.stale_days}일 이전입니다. "
            "휴일 여부와 최신 공표 여부를 검토하세요."
        )
    else:
        st.success(
            f"환율 입력 적용 완료: {_SOURCE_DISPLAY.get(selection.applied_source, selection.applied_source)}"
        )

    st.subheader("데이터 출처와 계산 입력")
    st.dataframe(_selection_summary(selection), width="stretch", hide_index=True)
    visible_columns = [
        "currency",
        "spot_rate_krw",
        "krw_interest_rate",
        "foreign_interest_rate",
        "spot_source",
        "interest_rate_source",
        "spot_observation_date",
        "spot_stale_days",
        "spot_is_stale",
        "spot_response_hash",
    ]
    st.dataframe(
        fx_rates[[column for column in visible_columns if column in fx_rates.columns]],
        width="stretch",
        hide_index=True,
    )
    for limitation in selection.limitations:
        st.caption("• " + limitation)

    selected_exposure = calculate_exposure(
        portfolio, company["foreign_cash"], fx_rates
    )
    bundled_selection = select_fx_inputs(
        base_rates,
        required_currencies,
        source="bundled",
        as_of_date=analysis_date,
    )
    bundled_exposure = calculate_exposure(
        portfolio, company["foreign_cash"], bundled_selection.rates
    )

    st.subheader("통화별 환노출")
    st.dataframe(selected_exposure.by_currency, width="stretch", hide_index=True)

    comparison = selected_exposure.by_currency[
        [
            "currency",
            "spot_rate_krw",
            "expected_transaction_exposure_krw",
            "expected_total_economic_position_krw",
        ]
    ].merge(
        bundled_exposure.by_currency[
            [
                "currency",
                "spot_rate_krw",
                "expected_transaction_exposure_krw",
                "expected_total_economic_position_krw",
            ]
        ],
        on="currency",
        suffixes=("_selected", "_bundled"),
        validate="one_to_one",
    )
    comparison["spot_delta_krw"] = (
        comparison["spot_rate_krw_selected"]
        - comparison["spot_rate_krw_bundled"]
    )
    comparison["expected_economic_position_delta_krw"] = (
        comparison["expected_total_economic_position_krw_selected"]
        - comparison["expected_total_economic_position_krw_bundled"]
    )
    st.markdown("**선택 환율과 번들 가정 비교**")
    st.dataframe(comparison, width="stretch", hide_index=True)

    selected_rate_map = dict(
        zip(fx_rates["currency"], fx_rates["spot_rate_krw"], strict=True)
    )
    bundled_rate_map = dict(
        zip(
            bundled_selection.rates["currency"],
            bundled_selection.rates["spot_rate_krw"],
            strict=True,
        )
    )
    selected_cashflow = calculate_monthly_cashflow(
        portfolio,
        selected_rate_map,
        company["monthly_fixed_cost_krw"],
        company["current_cash_krw"],
        cash_flow_view=cash_flow_view,
    )
    bundled_cashflow = calculate_monthly_cashflow(
        portfolio,
        bundled_rate_map,
        company["monthly_fixed_cost_krw"],
        company["current_cash_krw"],
        cash_flow_view=cash_flow_view,
    )
    cashflow_compare = selected_cashflow.merge(
        bundled_cashflow[["year_month", "ending_cash_krw"]],
        on="year_month",
        how="left",
        suffixes=("_selected", "_bundled"),
        validate="one_to_one",
    )
    cashflow_compare["ending_cash_delta_krw"] = (
        cashflow_compare["ending_cash_krw_selected"]
        - cashflow_compare["ending_cash_krw_bundled"]
    )

    st.subheader("월별 현금흐름·유동성")
    st.dataframe(cashflow_compare, width="stretch", hide_index=True)
    cashflow_chart = cashflow_compare.melt(
        id_vars="year_month",
        value_vars=["ending_cash_krw_selected", "ending_cash_krw_bundled"],
        var_name="series",
        value_name="ending_cash_krw",
    )
    st.plotly_chart(
        px.line(
            cashflow_chart,
            x="year_month",
            y="ending_cash_krw",
            color="series",
            markers=True,
            labels={"year_month": "월", "ending_cash_krw": "기말 현금(원)"},
        ),
        width="stretch",
    )

    transaction_currencies = sorted(portfolio["currency"].unique())
    hedge_ratios = {
        currency: hedge_ratio_pct / 100.0 for currency in transaction_currencies
    }
    try:
        hedge = calculate_transaction_level_portfolio_hedge(
            portfolio,
            fx_rates,
            analysis_date,
            hedge_ratios=hedge_ratios,
            exposure_measure="expected",
        )
    except Exception as exc:
        st.error(f"헤지 분석 오류: {exc}")
    else:
        st.subheader("이론 선물환·헤지 시나리오")
        st.warning(
            "선물환 값은 선택 현물환율과 별도 금리 가정에 따른 ACT/365 이론값입니다. "
            "실제 KB 선물환 견적이나 체결 가능 가격이 아닙니다."
        )
        st.dataframe(
            hedge.transaction_results,
            width="stretch",
            hide_index=True,
        )
        st.dataframe(
            hedge.portfolio_scenario_totals,
            width="stretch",
            hide_index=True,
        )

    audit_payload = {
        "analysis_type": "official_reference_fx_integrated_engine",
        "contains_credentials": False,
        "requested_source": selection.requested_source,
        "applied_source": selection.applied_source,
        "required_currencies": list(selection.required_currencies),
        "requested_as_of_date": selection.requested_as_of_date,
        "observation_date": selection.observation_date,
        "retrieved_at": selection.retrieved_at,
        "response_hash": selection.response_hash,
        "stale_days": selection.stale_days,
        "is_stale": selection.is_stale,
        "used_fallback": selection.used_fallback,
        "fallback_reason": selection.fallback_reason,
        "fx_inputs": fx_rates.to_dict("records"),
        "cash_flow_view": cash_flow_view,
        "hedge_ratio": hedge_ratio_pct / 100.0,
        "limitations": list(selection.limitations),
    }
    st.download_button(
        "환율 입력·출처 감사 JSON 내려받기",
        json.dumps(audit_payload, ensure_ascii=False, indent=2, default=str),
        "kb_tradeguard_fx_source_audit.json",
        "application/json",
    )
