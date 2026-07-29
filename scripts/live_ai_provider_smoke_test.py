"""Optional real-provider smoke test for the grounded Live AI boundary.

Usage in PowerShell:
    $env:OPENAI_API_KEY="..."
    $env:OPENAI_MODEL="gpt-5-mini"
    py -3.13 scripts/live_ai_provider_smoke_test.py

The script uses only the synthetic O/A demo scenario and never prints the API key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.demo_scenarios import load_demo_scenario  # noqa: E402
from src.intelligence.live_ai_contract import build_live_ai_grounding_packet  # noqa: E402
from src.intelligence.live_ai_provider import (  # noqa: E402
    LiveAiProviderError,
    openai_live_ai_is_configured,
    run_grounded_openai_live_ai,
)
from src.intelligence.single_transaction_package import (  # noqa: E402
    run_single_transaction_package,
)


def main() -> int:
    if not openai_live_ai_is_configured():
        print(
            json.dumps(
                {
                    "status": "configuration_required",
                    "missing": "OPENAI_API_KEY",
                    "note": "No network call was attempted.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    package = load_demo_scenario("oa_high_risk")
    run = run_single_transaction_package(package)
    packet = build_live_ai_grounding_packet(
        run.updated_case,
        run.assessment_result,
        request_id=f"LIVE-SMOKE-{uuid4().hex[:10]}",
        mode="prepare_consultation",
        user_question="은행과 K-SURE 상담 전에 무엇을 어떤 순서로 준비해야 하나요?",
    )
    try:
        execution = run_grounded_openai_live_ai(packet)
    except LiveAiProviderError as exc:
        print(
            json.dumps(
                {"status": "provider_error", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    output = {
        "status": "ok" if execution.validation.accepted else "rejected",
        "provider": execution.response.provider_name,
        "model": execution.response.model_name,
        "provider_request_id": execution.provider_request_id,
        "case_hash": packet.case_hash,
        "allowed_reference_count": len(packet.allowed_reference_ids),
        "cited_reference_ids": execution.response.cited_reference_ids,
        "validation": execution.validation.model_dump(mode="json"),
        "answer_markdown": (
            execution.response.answer_markdown
            if execution.validation.accepted
            else "[not displayed because validation failed]"
        ),
        "limitations": execution.response.limitations,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if execution.validation.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
