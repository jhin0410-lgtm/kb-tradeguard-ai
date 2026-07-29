from __future__ import annotations

import pandas as pd

from src.copilot_integration import build_workspace_from_app_state
from src.copilot_streamlit import workspace_summary_rows, workspace_trace_rows


COMPANY = {
    "company_name": "테스트무역",
    "foreign_cash": {"USD": 10000},
    "current_cash_krw": 100000000,
    "monthly_fixed_cost_krw": 20000000,
    "as_of_date": "2026-08-31",
}
TRANSACTIONS = pd.DataFrame(
    [
        {
            "transaction_id": "EXP-001",
            "transaction_type": "export",
            "currency": "USD",
            "amount_fc": 50000,
            "expected_date": "2026-09-30",
            "source_filename": "invoice.csv",
            "source_type": "bundled",
        }
    ]
)
FX = pd.DataFrame([{"currency": "USD", "spot_rate_krw": 1350}])


def _workspace():
    return build_workspace_from_app_state(
        user_objective="환노출과 수금지연을 점검",
        company=COMPANY,
        approved_transactions=TRANSACTIONS,
        fx_rates=FX,
    )


def test_summary_rows_cover_every_workspace_section():
    workspace = _workspace()
    rows = workspace_summary_rows(workspace)
    assert len(rows) == len(workspace.sections)
    assert {row["section"] for row in rows} == {item.title for item in workspace.sections}


def test_summary_rows_translate_status_for_human_review():
    rows = workspace_summary_rows(_workspace())
    assert all(row["status"] in {"준비됨", "검토 필요", "차단됨", "자료 없음"} for row in rows)


def test_trace_rows_are_contiguous_and_preserve_authority():
    workspace = _workspace()
    rows = workspace_trace_rows(workspace)
    assert [row["순서"] for row in rows] == list(range(1, len(rows) + 1))
    assert {row["권한"] for row in rows} <= {
        "case_state",
        "deterministic_engine",
        "governed_reasoning",
    }


def test_trace_rows_disclose_missing_inputs_and_output_ids():
    rows = workspace_trace_rows(_workspace())
    assert all("누락 입력" in row and "출력 ID" in row for row in rows)


def test_renderer_helpers_do_not_mutate_workspace():
    workspace = _workspace()
    before = workspace.model_dump(mode="json")
    workspace_summary_rows(workspace)
    workspace_trace_rows(workspace)
    assert workspace.model_dump(mode="json") == before
