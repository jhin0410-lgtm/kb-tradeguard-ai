from pathlib import Path

import pytest

from src.intelligence.decision_brief_report import (
    render_single_transaction_assessment_markdown,
)
from src.intelligence.single_transaction_package import (
    load_single_transaction_package,
    run_single_transaction_package,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "single_transaction_assessment_package_minimal.json"


def _run():
    package = load_single_transaction_package(EXAMPLE)
    return run_single_transaction_package(package)


def test_markdown_report_is_deterministic_and_contains_audit_links():
    run = _run()

    first = render_single_transaction_assessment_markdown(
        run.updated_case, run.assessment_result
    )
    second = render_single_transaction_assessment_markdown(
        run.updated_case, run.assessment_result
    )

    assert first == second
    assert run.output_case_hash in first
    assert run.assessment_result.pipeline_id in first
    assert run.assessment_result.transaction_id in first
    assert run.assessment_result.brief.source.source_id in first
    assert "## 4. Finding 전문가 검토" in first
    assert "## 8. 파이프라인 실행기록" in first
    assert "계약서·L/C 사전검사" in first
    assert "건너뜀" in first
    assert "[REF:" in first


def test_markdown_report_preserves_missing_information_and_authority_boundary():
    run = _run()
    report = render_single_transaction_assessment_markdown(
        run.updated_case, run.assessment_result
    )

    assert "추가 정보 필요" in report
    for item in run.assessment_result.brief.missing_information:
        assert item in report
    assert "거래 승인·거절" in report
    assert "은행 신용승인" in report
    assert "K-SURE" in report


def test_markdown_report_rejects_case_result_hash_mismatch():
    run = _run()
    different_case = run.updated_case.model_copy(
        update={
            "monthly_cost_assumptions": {
                **run.updated_case.monthly_cost_assumptions,
                "synthetic_change": 1,
            }
        }
    )

    with pytest.raises(ValueError, match="case hash does not match"):
        render_single_transaction_assessment_markdown(
            different_case,
            run.assessment_result,
        )
