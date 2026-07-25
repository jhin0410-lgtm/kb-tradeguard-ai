"""Manual live-provider verification using bundled synthetic demo data only."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.advisor_orchestrator import (
    AdvisorOrchestrator,
    ConfiguredStructuredAdvisor,
)
from src.advisor_tools import ReadOnlyAdvisorTools
from src.policy_retrieval import BundledPolicyRetriever

OUTPUT = ROOT / "evidence" / "provider_smoke_redacted.json"
DEMO_QUESTIONS = [
    "현재 USD 환노출이 얼마나 되나요?",
    "총액 상계가 50%인데 자연헤지가 왜 0%인가요?",
    "환율이 10% 하락하면 50% 헤지가 얼마나 방어하나요?",
    "EXP-001 입금이 30일 늦으면 어떻게 되나요?",
    "이 선물환 가격은 실제 KB 견적인가요?",
]
POLICY_CHECK = "은행 상담 전에 어떤 서류를 준비해야 하나요?"


def _build_tools() -> tuple[ReadOnlyAdvisorTools, pd.DataFrame]:
    transactions = pd.read_csv(ROOT / "data" / "sample_transactions.csv")
    fx_rates = pd.read_csv(ROOT / "data" / "sample_fx_rates.csv")
    company = json.loads(
        (ROOT / "data" / "sample_company.json").read_text(encoding="utf-8")
    )
    tools = ReadOnlyAdvisorTools(
        transactions,
        fx_rates,
        company,
        policy_retriever=BundledPolicyRetriever(ROOT / "data" / "policy_docs"),
    )
    return tools, transactions.copy(deep=True)


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("Live provider not configured; no transcript was written.")
        return 2
    provider = ConfiguredStructuredAdvisor()
    if not provider.is_available:
        print("Live provider SDK/configuration unavailable; no transcript was written.")
        return 2

    tools, original_transactions = _build_tools()
    forbidden = {
        "register_transaction",
        "edit_transaction",
        "approve_transaction",
        "delete_transaction",
    }
    if any(hasattr(tools, name) for name in forbidden):
        raise RuntimeError("Read-only tool boundary failed")

    orchestrator = AdvisorOrchestrator(tools, provider)
    evidence = []
    for question_id, question in enumerate([*DEMO_QUESTIONS, POLICY_CHECK], start=1):
        run = orchestrator.ask(question)
        if run.answer.provider_mode != provider.provider_mode:
            raise RuntimeError("Configured provider fell back; live verification failed")
        if not run.validation.validation_result:
            raise RuntimeError(
                f"Grounding validation failed for question {question_id}: "
                + "; ".join(run.validation.errors)
            )
        evidence.append(
            {
                "question_id": question_id,
                "official_demo_question": question_id <= len(DEMO_QUESTIONS),
                "provider_mode": run.answer.provider_mode,
                "intent": run.answer.intent.primary_intent,
                "tools": sorted(run.tool_results),
                "calculation_ids": [
                    item.calculation_id for item in run.answer.calculations_used
                ],
                "document_ids": [
                    item.document_id for item in run.answer.documents_used
                ],
                "answer": run.answer.direct_answer,
                "key_findings": run.answer.key_findings,
                "validation_result": run.validation.validation_result,
            }
        )

    pd.testing.assert_frame_equal(tools._transactions, original_transactions)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "evidence_type": "redacted_live_structured_provider_smoke_test",
                "synthetic_demo_data_only": True,
                "contains_credentials": False,
                "contains_uploaded_documents": False,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "model_environment_variable": "OPENAI_ADVISOR_MODEL",
                "runs": evidence,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Live structured-provider verification passed: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
