"""Primary Streamlit entrypoint for the Global Trade Copilot workspace."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.copilot_integration import build_workspace_from_app_state
from src.copilot_streamlit import render_copilot_workspace

ROOT = Path(__file__).parent
SAMPLE_TRANSACTIONS = ROOT / "data" / "sample_transactions.csv"
SAMPLE_COMPANY = ROOT / "data" / "sample_company.json"
SAMPLE_FX_RATES = ROOT / "data" / "sample_fx_rates.csv"
DEFAULT_OBJECTIVE = "환노출, 결제시점, 유동성 위험을 상담 전에 통합 점검해 주세요."


@st.cache_data
def load_company() -> dict:
    return json.loads(SAMPLE_COMPANY.read_text(encoding="utf-8"))


@st.cache_data
def load_transactions() -> pd.DataFrame:
    frame = pd.read_csv(SAMPLE_TRANSACTIONS)
    frame["source_type"] = "bundled"
    return frame


@st.cache_data
def load_fx_rates() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_FX_RATES)


def initialize_session() -> None:
    defaults = {
        "copilot_objective": DEFAULT_OBJECTIVE,
        "copilot_transactions": load_transactions().to_dict("records"),
        "copilot_cash_allocations": [],
        "copilot_audit_events": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main() -> None:
    st.set_page_config(page_title="KB TradeGuard Copilot", page_icon="🛡️", layout="wide")
    initialize_session()

    st.title("KB TradeGuard AI")
    st.caption("Evidence-grounded Global Trade Copilot · deterministic financial authority")

    with st.sidebar:
        st.markdown("### 상담 목적")
        objective = st.text_area("분석 요청", key="copilot_objective", height=140)
        st.markdown("### 데이터 모드")
        st.info("현재 진입점은 검토 가능한 bundled demo 상태를 Workspace로 변환합니다.")
        st.caption("기존 상세 대시보드는 app.py에서 계속 사용할 수 있습니다.")

    company = load_company()
    transactions = pd.DataFrame(st.session_state.copilot_transactions)
    fx_rates = load_fx_rates()

    workspace = build_workspace_from_app_state(
        user_objective=objective,
        company=company,
        approved_transactions=transactions,
        fx_rates=fx_rates,
        cash_allocations=st.session_state.copilot_cash_allocations,
        audit_events=st.session_state.copilot_audit_events,
    )
    render_copilot_workspace(workspace)

    with st.expander("보조 분석 입력 확인"):
        st.markdown("**승인 거래**")
        st.dataframe(transactions, width="stretch", hide_index=True)
        st.markdown("**환율 참고 입력**")
        st.dataframe(fx_rates, width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
