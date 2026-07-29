"""Official public-data dashboard for TradeGuard v2."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.data_providers import (
    BOKECOSProvider,
    KEXIMFXProvider,
    NTSBusinessStatusProvider,
    OpenDARTProvider,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderResponseError,
)
from src.official_data_views import (
    build_dart_company_frame,
    build_ecos_key_statistics_frame,
    build_kexim_rate_frame,
)

st.set_page_config(page_title="TradeGuard 공식 데이터", page_icon="🌐", layout="wide")
st.title("공식 데이터 연결 대시보드")
st.caption(
    "한국은행·한국수출입은행·OpenDART·국세청의 공개 데이터를 읽기 전용으로 조회합니다. "
    "참고환율은 실제 KB 체결가격이 아니며, 사업자 상태는 신용평가가 아닙니다."
)


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
def _fetch_ecos() -> dict:
    return BOKECOSProvider().get_key_statistics(1, 20)


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_kexim(as_of_date: str) -> dict:
    return KEXIMFXProvider().fetch_latest_rates(as_of_date, lookback_days=10)


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_dart_company(corp_code: str) -> dict:
    return OpenDARTProvider().get_company(corp_code)


@st.cache_data(ttl=900, show_spinner=False)
def _fetch_dart_financials(
    corp_code: str, business_year: int, report_code: str, fs_div: str
) -> dict:
    return OpenDARTProvider().get_financial_statements(
        corp_code,
        business_year,
        report_code=report_code,
        fs_div=fs_div,
    )


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_nts_status(business_number: str) -> dict:
    return NTSBusinessStatusProvider().check_status([business_number])


configured = {
    "한국은행 ECOS": BOKECOSProvider().is_configured,
    "수출입은행 환율": KEXIMFXProvider().is_configured,
    "OpenDART": OpenDARTProvider().is_configured,
    "국세청 사업자 상태": NTSBusinessStatusProvider().is_configured,
}
columns = st.columns(len(configured))
for column, (name, is_configured) in zip(columns, configured.items(), strict=True):
    column.metric(name, "설정됨" if is_configured else "미설정")

st.divider()
market_tab, dart_tab, nts_tab = st.tabs(
    ["시장·거시 데이터", "기업공시·재무제표", "국내 사업자 상태"]
)

with market_tab:
    left, right = st.columns(2)

    with left:
        st.subheader("한국은행 ECOS 주요지표")
        st.write("버튼을 누를 때만 공식 API를 호출하며 결과는 15분간 캐시됩니다.")
        if st.button("ECOS 주요지표 조회", key="fetch_ecos"):
            try:
                snapshot = _fetch_ecos()
                frame = build_ecos_key_statistics_frame(snapshot)
                st.success(f"{len(frame)}개 지표를 조회했습니다.")
                st.dataframe(
                    frame[
                        [
                            "class_name",
                            "stat_name",
                            "data_value",
                            "cycle",
                            "unit_name",
                        ]
                    ],
                    width="stretch",
                    hide_index=True,
                )
                st.caption(
                    f"조회시각 {snapshot['retrieved_at']} · 응답 해시 "
                    f"{snapshot['response_hash'][:16]}…"
                )
            except Exception as exc:  # Streamlit boundary
                _render_error(exc)

    with right:
        st.subheader("한국수출입은행 공식 참고환율")
        as_of_date = st.date_input("기준일", value=date.today(), key="kexim_date")
        if st.button("최근 공개 환율 조회", key="fetch_kexim"):
            try:
                snapshot = _fetch_kexim(as_of_date.isoformat())
                frame = build_kexim_rate_frame(snapshot)
                st.success(
                    f"공표일 {snapshot['observation_date']} 기준 {len(frame)}개 통화를 조회했습니다."
                )
                visible = frame[
                    [
                        "currency",
                        "currency_name",
                        "raw_currency_unit",
                        "quotation_unit",
                        "deal_base_rate_raw",
                        "spot_rate_krw_per_unit",
                        "telegraphic_transfer_buy_per_unit",
                        "telegraphic_transfer_sell_per_unit",
                    ]
                ]
                st.dataframe(visible, width="stretch", hide_index=True)
                st.info(
                    "JPY(100)처럼 100단위로 고시되는 통화는 원 고시값을 보존하고, "
                    "계산용 열에서 1통화 단위당 원화값으로 별도 정규화합니다."
                )
                st.warning(
                    "이 표는 공공 참고환율입니다. 실제 KB 고객 체결환율·선물환 견적이 아닙니다."
                )
                st.caption(
                    f"조회시각 {snapshot['retrieved_at']} · 응답 해시 "
                    f"{snapshot['response_hash'][:16]}…"
                )
            except Exception as exc:  # Streamlit boundary
                _render_error(exc)

with dart_tab:
    st.subheader("OpenDART 기업개황과 재무제표")
    corp_code = st.text_input("DART 8자리 고유번호", value="00126380")
    profile_col, financial_col = st.columns(2)

    with profile_col:
        if st.button("기업개황 조회", key="fetch_dart_profile"):
            try:
                snapshot = _fetch_dart_company(corp_code)
                frame = build_dart_company_frame(snapshot)
                profile = frame.iloc[0]
                st.success(f"{profile.get('corp_name') or corp_code} 기업개황 조회 완료")
                display_fields = {
                    "회사명": profile.get("corp_name"),
                    "영문명": profile.get("corp_name_eng"),
                    "종목코드": profile.get("stock_code"),
                    "대표자": profile.get("ceo_nm"),
                    "업종코드": profile.get("induty_code"),
                    "설립일": profile.get("est_dt"),
                    "결산월": profile.get("acc_mt"),
                    "주소": profile.get("adres"),
                }
                st.dataframe(
                    pd.DataFrame(
                        [{"항목": key, "값": value} for key, value in display_fields.items()]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                st.caption(
                    f"조회시각 {snapshot['retrieved_at']} · 응답 해시 "
                    f"{snapshot['response_hash'][:16]}…"
                )
            except Exception as exc:  # Streamlit boundary
                _render_error(exc)

    with financial_col:
        business_year = int(
            st.number_input("사업연도", min_value=2015, max_value=2100, value=2025)
        )
        report_label = st.selectbox(
            "보고서",
            ["사업보고서", "1분기보고서", "반기보고서", "3분기보고서"],
        )
        report_codes = {
            "사업보고서": "11011",
            "1분기보고서": "11013",
            "반기보고서": "11012",
            "3분기보고서": "11014",
        }
        fs_label = st.radio("재무제표 구분", ["연결", "별도"], horizontal=True)
        fs_div = "CFS" if fs_label == "연결" else "OFS"
        if st.button("재무제표 조회", key="fetch_dart_financials"):
            try:
                snapshot = _fetch_dart_financials(
                    corp_code,
                    business_year,
                    report_codes[report_label],
                    fs_div,
                )
                rows = snapshot["results"]
                if not rows:
                    st.warning("해당 조건으로 조회된 재무제표가 없습니다.")
                else:
                    frame = pd.DataFrame(rows)
                    preferred = [
                        column
                        for column in (
                            "sj_nm",
                            "account_nm",
                            "thstrm_nm",
                            "thstrm_amount",
                            "frmtrm_nm",
                            "frmtrm_amount",
                            "ord",
                            "currency",
                        )
                        if column in frame.columns
                    ]
                    st.success(f"{len(frame)}개 공시 계정을 조회했습니다.")
                    st.dataframe(
                        frame[preferred] if preferred else frame,
                        width="stretch",
                        hide_index=True,
                    )
                    st.caption(
                        f"조회시각 {snapshot['retrieved_at']} · 응답 해시 "
                        f"{snapshot['response_hash'][:16]}…"
                    )
                st.warning(
                    "공시 재무제표 기반 사전 분석용이며 공식 신용등급·대출 가능 여부를 의미하지 않습니다."
                )
            except Exception as exc:  # Streamlit boundary
                _render_error(exc)

with nts_tab:
    st.subheader("국세청 사업자등록 상태조회")
    st.write(
        "국내 사업자 존재·영업상태 확인용입니다. 계속사업자 여부는 신용도나 거래 안전성을 보증하지 않습니다."
    )
    business_number = st.text_input(
        "사업자등록번호", type="password", placeholder="10자리 숫자"
    )
    if st.button("사업자 상태조회", key="fetch_nts"):
        try:
            snapshot = _fetch_nts_status(business_number)
            results = snapshot["results"]
            if not results:
                st.warning("조회 결과가 없습니다.")
            else:
                row = dict(results[0])
                row.pop("business_number", None)
                st.dataframe(
                    pd.DataFrame([row]), width="stretch", hide_index=True
                )
                st.caption(
                    f"조회시각 {snapshot['retrieved_at']} · 응답 해시 "
                    f"{snapshot['response_hash'][:16]}…"
                )
            st.warning(snapshot["limitations"])
        except Exception as exc:  # Streamlit boundary
            _render_error(exc)
