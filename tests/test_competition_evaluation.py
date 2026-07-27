from src.competition_evaluation import build_internal_trade_document_benchmark


def test_internal_benchmark_reports_rule_set_metrics_without_external_accuracy_claims():
    metrics = build_internal_trade_document_benchmark()

    assert metrics.case_count == 30
    assert metrics.positive_case_count > 0
    assert metrics.negative_control_count > 0
    assert metrics.exact_match_case_count == metrics.case_count
    assert metrics.false_positive_rule_count == 0
    assert metrics.false_negative_rule_count == 0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
    assert metrics.false_positive_case_ids == ()
    assert metrics.false_negative_case_ids == ()
    assert "synthetic" in metrics.evaluation_scope
    assert "do not measure" in metrics.authority_boundary
