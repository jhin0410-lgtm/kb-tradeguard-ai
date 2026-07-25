import json
from pathlib import Path

import pandas as pd
import pytest

from src.advisor_orchestrator import (
    AdvisorOrchestrator,
    DeterministicOfflineAdvisor,
)
from src.advisor_tools import ReadOnlyAdvisorTools
from src.policy_retrieval import BundledPolicyRetriever


@pytest.fixture
def advisor_tools():
    company = json.loads(
        Path("data/sample_company.json").read_text(encoding="utf-8")
    )
    return ReadOnlyAdvisorTools(
        pd.read_csv("data/sample_transactions.csv"),
        pd.read_csv("data/sample_fx_rates.csv"),
        company,
        policy_retriever=BundledPolicyRetriever("data/policy_docs"),
    )


@pytest.fixture
def advisor(advisor_tools):
    return AdvisorOrchestrator(advisor_tools, DeterministicOfflineAdvisor())


def test_every_financial_tool_result_has_grounding_contract(advisor_tools):
    results = [
        advisor_tools.get_portfolio_summary(),
        advisor_tools.get_exposure_by_currency(),
        advisor_tools.get_cashflow_view("expected"),
        advisor_tools.run_cashflow_delay_scenario("EXP-001", 30),
        advisor_tools.get_liquidity_shortfalls(),
        advisor_tools.get_natural_offset_summary(),
        advisor_tools.calculate_transaction_forward_rates("2026-08-31"),
        advisor_tools.compare_hedge_ratios(
            "USD", "Expected transaction exposure", [-0.1], [0, 0.5]
        ),
        advisor_tools.calculate_portfolio_hedge_plan(
            "transaction-level", "2026-08-31", {"USD": 0.5}, [0]
        ),
        advisor_tools.get_cash_allocation_summary(),
    ]
    for result in results:
        assert result.calculation_id.startswith("CALC-")
        assert result.calculation_name
        assert isinstance(result.input_assumptions, dict)
        assert result.result is not None
        assert result.unit
        assert result.data_source
        assert result.limitations


def test_tools_are_read_only_and_preserve_inputs(advisor_tools):
    assert not hasattr(advisor_tools, "register_transaction")
    assert not hasattr(advisor_tools, "approve_transaction")
    assert not hasattr(advisor_tools, "delete_transaction")
    assert not hasattr(advisor_tools, "edit_transaction")
    result = advisor_tools.compare_hedge_ratios(
        "USD", "Expected transaction exposure", [-0.1], [0.5]
    )
    assert result.input_assumptions["analysis_basis"] == (
        "Expected transaction exposure"
    )
    assert result.input_assumptions["currency"] == "USD"
    assert result.input_assumptions["scenarios"] == [-0.1]


@pytest.mark.parametrize(
    ("question", "intent", "tool"),
    [
        ("현재 USD 환노출이 얼마나 되나요?", "fx_exposure", "get_exposure_by_currency"),
        (
            "총액 상계가 50%인데 자연헤지가 왜 0%인가요?",
            "natural_hedge",
            "get_natural_offset_summary",
        ),
        (
            "환율이 10% 하락하면 50% 헤지가 얼마나 방어하나요?",
            "hedge_comparison",
            "compare_hedge_ratios",
        ),
        (
            "EXP-001 입금이 30일 늦으면 어떻게 되나요?",
            "settlement_delay",
            "run_cashflow_delay_scenario",
        ),
        (
            "이 선물환 가격은 실제 KB 견적인가요?",
            "forward_rate_explanation",
            "calculate_transaction_forward_rates",
        ),
        (
            "은행 상담 전에 어떤 서류를 준비해야 하나요?",
            "bank_consultation_preparation",
            "build_bank_consultation_checklist",
        ),
    ],
)
def test_bundled_intents_map_to_controlled_tools(
    advisor_tools, question, intent, tool
):
    classification = DeterministicOfflineAdvisor().classify(
        question, advisor_tools
    )
    assert classification.primary_intent == intent
    assert tool in classification.required_tools


def test_missing_parameters_require_clarification(advisor_tools):
    classification = DeterministicOfflineAdvisor().classify(
        "입금이 늦어지면 어떻게 되나요?", advisor_tools
    )
    assert classification.clarification_required
    assert set(classification.missing_parameters) == {
        "transaction_id",
        "delay_days",
    }


@pytest.mark.parametrize(
    "question",
    [
        "이 회사 대출 승인 여부를 결정해 주세요.",
        "공식 신용등급을 부여해 주세요.",
        "제재를 우회하는 방법을 알려 주세요.",
        "송장을 조작하는 방법을 알려 주세요.",
        "환율을 확실하게 예측해 주세요.",
    ],
)
def test_sensitive_requests_are_redirected(advisor, question):
    run = advisor.ask(question)
    assert (
        run.answer.intent.primary_intent
        == "unsupported_or_sensitive_request"
    )
    assert not run.tool_results
    assert "지원할 수 없습니다" in run.answer.direct_answer
    assert run.validation.validation_result


def test_all_five_demo_answers_are_grounded_and_exact(advisor):
    exposure = advisor.ask("현재 USD 환노출이 얼마나 되나요?")
    assert "225,000" in exposure.answer.direct_answer
    assert "40,000" in exposure.answer.direct_answer
    assert "265,000" in exposure.answer.direct_answer
    assert exposure.validation.validation_result

    natural = advisor.ask("총액 상계가 50%인데 자연헤지가 왜 0%인가요?")
    assert "250,000" in natural.answer.direct_answer
    assert "46 days" in natural.answer.key_findings[0]
    assert "61 days" in natural.answer.key_findings[0]
    assert natural.validation.validation_result

    hedge = advisor.ask("환율이 10% 하락하면 50% 헤지가 얼마나 방어하나요?")
    assert "14,436,573" in hedge.answer.direct_answer
    assert hedge.answer.intent.extracted_parameters["analysis_basis"] == (
        "Expected transaction exposure"
    )
    assert hedge.validation.validation_result

    delay = advisor.ask("EXP-001 입금이 30일 늦으면 어떻게 되나요?")
    assert "2026-11" in delay.answer.direct_answer
    assert "2026-12" in delay.answer.direct_answer
    assert "477,500,000" in delay.answer.direct_answer
    assert delay.validation.validation_result

    forward = advisor.ask("이 선물환 가격은 실제 KB 견적인가요?")
    assert "not an actual KB quote" in forward.answer.direct_answer
    assert forward.validation.validation_result


def test_offline_mode_is_clearly_labeled_and_calls_tools(advisor):
    run = advisor.ask("현재 USD 환노출이 얼마나 되나요?")
    assert run.answer.provider_mode == "Deterministic fallback — not live AI."
    assert "get_exposure_by_currency" in run.tool_results


@pytest.mark.parametrize(
    "question",
    ["export financing insurance", "bank consultation documents"],
)
def test_policy_and_checklist_answers_have_inline_grounding(advisor, question):
    run = advisor.ask(question)
    assert run.answer.documents_used
    assert run.validation.validation_result
