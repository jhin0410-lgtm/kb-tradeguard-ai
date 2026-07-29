"""Transparent evaluation metrics for the competition evidence package.

The benchmark uses project-authored, synthetic, human-reviewed field fixtures. It is
useful for regression and rule-coverage evidence, but it is not an external accuracy
study, a legal-document benchmark, or proof of production performance.
"""

from __future__ import annotations

from dataclasses import dataclass

from .intelligence.trade_document_gold import list_trade_document_gold_cases
from .intelligence.trade_document_rules import evaluate_trade_document


@dataclass(frozen=True)
class InternalBenchmarkMetrics:
    evaluation_scope: str
    case_count: int
    positive_case_count: int
    negative_control_count: int
    exact_match_case_count: int
    true_positive_rule_count: int
    false_positive_rule_count: int
    false_negative_rule_count: int
    precision: float | None
    recall: float | None
    f1: float | None
    false_positive_case_ids: tuple[str, ...]
    false_negative_case_ids: tuple[str, ...]
    authority_boundary: str

    @property
    def exact_match_rate(self) -> float:
        if self.case_count == 0:
            return 0.0
        return self.exact_match_case_count / self.case_count


def _rule_id_from_finding(finding_id: str, document_id: str) -> str:
    prefix = "CLAUSE-"
    suffix = f"-{document_id}"
    if not finding_id.startswith(prefix) or not finding_id.endswith(suffix):
        raise ValueError(f"Unexpected governed finding identifier: {finding_id}")
    return finding_id[len(prefix) : -len(suffix)]


def build_internal_trade_document_benchmark() -> InternalBenchmarkMetrics:
    """Evaluate exact Rule-ID sets across the reviewed synthetic fixture set."""

    cases = list_trade_document_gold_cases()
    true_positive = 0
    false_positive = 0
    false_negative = 0
    exact_matches = 0
    false_positive_cases: list[str] = []
    false_negative_cases: list[str] = []

    for case in cases:
        findings = evaluate_trade_document(case.document, case.payment_structure)
        predicted = {
            _rule_id_from_finding(item.clause_finding_id, case.document.document_id)
            for item in findings
        }
        expected = set(case.expected_rule_ids)
        true_positive += len(predicted & expected)
        false_positive += len(predicted - expected)
        false_negative += len(expected - predicted)
        if predicted == expected:
            exact_matches += 1
        if predicted - expected:
            false_positive_cases.append(case.case_id)
        if expected - predicted:
            false_negative_cases.append(case.case_id)

    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = (
        true_positive / precision_denominator if precision_denominator else None
    )
    recall = true_positive / recall_denominator if recall_denominator else None
    f1 = None
    if precision is not None and recall is not None and precision + recall:
        f1 = 2 * precision * recall / (precision + recall)

    return InternalBenchmarkMetrics(
        evaluation_scope="project-authored synthetic reviewed-field regression benchmark",
        case_count=len(cases),
        positive_case_count=sum(bool(case.expected_rule_ids) for case in cases),
        negative_control_count=sum(not case.expected_rule_ids for case in cases),
        exact_match_case_count=exact_matches,
        true_positive_rule_count=true_positive,
        false_positive_rule_count=false_positive,
        false_negative_rule_count=false_negative,
        precision=precision,
        recall=recall,
        f1=f1,
        false_positive_case_ids=tuple(false_positive_cases),
        false_negative_case_ids=tuple(false_negative_cases),
        authority_boundary=(
            "Internal synthetic regression evidence only. These metrics do not measure "
            "raw-document extraction quality, external legal-review accuracy, credit "
            "performance, approval outcomes, or production suitability."
        ),
    )
