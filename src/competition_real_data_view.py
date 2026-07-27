"""Read-only official-data panel for the competition deployment.

Transaction documents and company records in the public showcase remain synthetic.
This panel proves the external-data path separately and never injects a live response
into the governed Decision Brief without a reviewed snapshot boundary.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from .data_providers import (
    KoreaCustomsTradeProvider,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderResponseError,
    WorldBankCountryProvider,
)

_INDICATOR_LABELS = {
    "NY.GDP.MKTP.KD.ZG": "GDP 성장률",
    "FP.CPI.TOTL.ZG": "소비자물가 상승률",
    "FI.RES.TOTL.MO": "수입 대비 외환보유액",
    "BN.CAB.XOKA.GD.ZS": "경상수지/GDP",
}
_INDICATOR_UNITS = {
    "NY.GDP.MKTP.KD.ZG": "%",
    "FP.CPI.TOTL.ZG": "%",
    "FI.RES.TOTL.MO": "개월",
    "BN.CAB.XOKA.GD.ZS": "%",
}

REAL_DATA_CSS = """
<style>
.tg-data-boundary {border:1px solid #cdd9e8;border-left:6px solid #1b63e9;border-radius:16px;padding:.82rem .9rem;background:#f5f8fc;color:#52627a;font-size:.76rem;line-height:1.52;margin-bottom:.7rem;}
.tg-data-source-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.55rem;margin:.55rem 0;}
.tg-data-source {border:1px solid #dce4ef;border-radius:14px;padding:.72rem;background:#fff;}
.tg-data-source strong {display:block;font-size:.77rem;color:#172033;margin-bottom:.16rem;}
.tg-data-source span {display:block;font-size:.67rem;line-height:1.4;color:#647084;}
@media(max-width:760px) {.tg-data-source-grid {grid-template-columns:1fr;}}
</style>
"""


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_world_bank(country_code: str) -> list[dict]:
    return WorldBankCountryProvider().get_reference_macro_indicators(country_code)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_customs(
    country_code: str,
    start_yymm: str,
    end_yymm: str,
    hs_code: str,
) -> dict:
    return KoreaCustomsTradeProvider().get_country_product_trade(
        start_yymm=start_yymm,
        end_yymm=end_yymm,
        country_code=country_code,
        hs_code=hs_code or None,
    )


def _scenario_country_code() -> str:
    package = st.session_state.get("competition_package")
    if package is None:
        return "VN"
    value = getattr(package.request, "country_code", None)
    return str(value or "VN").strip().upper()


def _previous_months() -> tuple[str, str]:
    today = date.today()
    end_year = today.year if today.month > 1 else today.year - 1
    end_month = today.month - 1 if today.month > 1 else 12
    end_index = end_year * 12 + end_month - 1
    start_index = max(end_index - 5, 0)
    start_year, start_zero_month = divmod(start_index, 12)
    return f"{start_year:04d}{start_zero_month + 1:02d}", f"{end_year:04d}{end_month:02d}"


def _render_provider_error(exc: Exception) -> None:
    if isinstance(exc, ProviderConfigurationError):
        st.warning(f"공식 API 키 설정 필요: {exc}")
    elif isinstance(exc, ProviderRequestError):
        st.warning(f"공식 데이터 요청 실패: {exc}")
    elif isinstance(exc, ProviderResponseError):
        st.error(f"공식 데이터 응답 검증 실패: {exc}")
    else:
        st.error(f"공식 데이터 처리 실패: {exc}")


def render_official_data_section(*, presentation_mode: bool) -> None:
    """Render live World Bank data and an optional Korea Customs query."""

    st.markdown(REAL_DATA_CSS, unsafe_allow_html=True)
    st.markdown('<div id="data" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tg-section-title">06 · 실제 공식 데이터 연결</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="tg-data-boundary"><strong>데이터 경계</strong> · 거래문서와 기업정보는 공개 시연용 합성 데이터입니다. 아래 국가 거시지표와 수출입 통계는 공식 API를 읽기 전용으로 조회하며, 검토되지 않은 실시간 응답을 자동으로 거래 승인·위험등급·상품 적격성 판단에 반영하지 않습니다.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="tg-data-source-grid">
          <div class="tg-data-source"><strong>World Bank</strong><span>GDP·물가·외환보유액·경상수지의 최신 비결측 공식 관측치</span></div>
          <div class="tg-data-source"><strong>관세청</strong><span>국가·HS Code별 수출액·수입액·중량·무역수지 집계</span></div>
          <div class="tg-data-source"><strong>국세청과 구분</strong><span>국세청 API는 국내 사업자 상태 확인용이며 수출입 통계를 제공하지 않음</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if presentation_mode:
        return

    country_code = _scenario_country_code()
    macro_col, customs_col = st.columns(2)
    with macro_col:
        st.markdown(f"#### {country_code} 공식 거시지표")
        st.caption("API Key가 필요 없는 World Bank Indicators API를 호출합니다.")
        if st.button("실제 거시지표 조회", key=f"world_bank_{country_code}"):
            try:
                snapshots = _fetch_world_bank(country_code)
                rows = []
                for snapshot in snapshots:
                    result = snapshot.get("results")
                    if not result:
                        continue
                    code = str(result.get("indicator_code") or snapshot.get("indicator_code"))
                    rows.append(
                        {
                            "지표": _INDICATOR_LABELS.get(code, result.get("indicator_name") or code),
                            "관측연도": result.get("observation_year"),
                            "값": result.get("value"),
                            "단위": _INDICATOR_UNITS.get(code, result.get("unit") or ""),
                            "국가": result.get("country_name") or country_code,
                        }
                    )
                if rows:
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                    st.caption("각 행은 최신 비결측 공식 관측치이며 관측연도는 지표별로 다를 수 있습니다.")
                else:
                    st.warning("요청 기간에서 비결측 거시지표를 찾지 못했습니다.")
            except Exception as exc:  # Streamlit provider boundary
                _render_provider_error(exc)

    with customs_col:
        provider = KoreaCustomsTradeProvider()
        st.markdown("#### 관세청 국가·품목 무역통계")
        if not provider.is_configured:
            st.info(
                "관세청 API 어댑터는 구현되어 있습니다. Streamlit Secret에 "
                "`KCS_TRADE_API_KEY` 또는 `DATA_GO_KR_SERVICE_KEY`를 설정하면 실제 조회가 활성화됩니다."
            )
            return
        default_start, default_end = _previous_months()
        start_yymm = st.text_input("시작월(YYYYMM)", value=default_start, key="kcs_start")
        end_yymm = st.text_input("종료월(YYYYMM)", value=default_end, key="kcs_end")
        hs_code = st.text_input("HS Code(선택)", value="", key="kcs_hs")
        if st.button("실제 수출입 통계 조회", key="kcs_fetch"):
            try:
                snapshot = _fetch_customs(country_code, start_yymm, end_yymm, hs_code)
                frame = pd.DataFrame(snapshot["results"])
                if frame.empty:
                    st.warning("해당 국가·기간·품목 조건에서 조회된 집계가 없습니다.")
                else:
                    visible = [
                        "period",
                        "country_name_ko",
                        "hs_code",
                        "product_name_ko",
                        "export_value_usd",
                        "import_value_usd",
                        "trade_balance_usd",
                    ]
                    st.dataframe(
                        frame[[column for column in visible if column in frame.columns]],
                        hide_index=True,
                        use_container_width=True,
                    )
                    st.caption(
                        f"조회시각 {snapshot['retrieved_at']} · 응답 해시 {snapshot['response_hash'][:16]}…"
                    )
                st.warning("관세청 수치는 국가·품목 집계이며 특정 기업의 수출입 실적이 아닙니다.")
            except Exception as exc:  # Streamlit provider boundary
                _render_provider_error(exc)
