"""Print an auditable summary of trade-document gold and mutation coverage."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intelligence.trade_document_gold import (  # noqa: E402
    iter_semantic_preserving_gold_mutations,
    list_trade_document_gold_cases,
    load_trade_document_gold_dataset,
)
from src.intelligence.trade_document_rules import (  # noqa: E402
    evaluate_trade_document,
    load_trade_document_rule_registry,
)


def _rule_ids(findings, document_id: str) -> set[str]:
    prefix = "CLAUSE-"
    suffix = f"-{document_id}"
    return {
        item.clause_finding_id[len(prefix) : -len(suffix)]
        for item in findings
    }


def main() -> int:
    dataset = load_trade_document_gold_dataset()
    cases = list_trade_document_gold_cases()
    mutations = list(iter_semantic_preserving_gold_mutations(cases))
    registry = load_trade_document_rule_registry()

    failures = []
    for case in cases:
        actual = _rule_ids(
            evaluate_trade_document(case.document, case.payment_structure),
            case.document.document_id,
        )
        if actual != set(case.expected_rule_ids):
            failures.append(
                {
                    "case_id": case.case_id,
                    "expected": sorted(case.expected_rule_ids),
                    "actual": sorted(actual),
                }
            )

    for mutation in mutations:
        actual = _rule_ids(
            evaluate_trade_document(mutation.document, mutation.payment_structure),
            mutation.document.document_id,
        )
        if actual != set(mutation.expected_rule_ids):
            failures.append(
                {
                    "mutation_id": mutation.mutation_id,
                    "expected": sorted(mutation.expected_rule_ids),
                    "actual": sorted(actual),
                }
            )

    covered = {
        rule_id for case in cases for rule_id in case.expected_rule_ids
    }
    governed = {item.rule_id for item in registry.rules}
    output = {
        "status": "ok" if not failures and covered == governed else "failed",
        "dataset_version": dataset["dataset_version"],
        "source_mode": dataset["source_mode"],
        "gold_case_count": len(cases),
        "mutation_case_count": len(mutations),
        "governed_rule_count": len(governed),
        "covered_rule_count": len(covered),
        "uncovered_rule_ids": sorted(governed - covered),
        "unexpected_rule_ids": sorted(covered - governed),
        "document_type_counts": dict(
            Counter(item.document.document_type for item in cases)
        ),
        "mutation_kind_counts": dict(
            Counter(item.mutation_kind for item in mutations)
        ),
        "failures": failures,
        "authority_boundary": dataset["authority_boundary"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
