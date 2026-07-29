from datetime import date

import pytest

from src.intelligence.document_extraction_evaluation import (
    ExtractionEvaluationCase,
    ExtractionEvaluationDataset,
    ExtractionFieldEvaluation,
    evaluate_document_extraction_dataset,
)


def _dataset(data_origin="private_authorized"):
    return ExtractionEvaluationDataset(
        dataset_name="reviewed-holdout",
        dataset_version="1.0",
        created_date=date(2026, 7, 28),
        extraction_system_name="test-extractor",
        extraction_system_version="0.1",
        adjudication_notes="Two-pass review with final adjudication.",
        cases=[
            ExtractionEvaluationCase(
                case_id="CONTRACT-001",
                document_type="contract",
                language="ko-en",
                data_origin=data_origin,
                source_locator="private://contract-001",
                source_license_or_authorization="authorized review copy",
                reviewer_count=2,
                fields=[
                    ExtractionFieldEvaluation(
                        field_name="currency",
                        expected_value="USD",
                        predicted_value="usd",
                        prediction_status="extracted",
                    ),
                    ExtractionFieldEvaluation(
                        field_name="amount",
                        expected_value="1,000.00",
                        predicted_value=1000,
                        prediction_status="extracted",
                        comparison_mode="number",
                    ),
                    ExtractionFieldEvaluation(
                        field_name="governing_law",
                        expected_value="Republic of Korea",
                        prediction_status="abstained",
                    ),
                    ExtractionFieldEvaluation(
                        field_name="optional_clause",
                        expected_value=None,
                        prediction_status="missing",
                    ),
                ],
            ),
            ExtractionEvaluationCase(
                case_id="INVOICE-001",
                document_type="commercial_invoice",
                language="en",
                data_origin=data_origin,
                source_locator="private://invoice-001",
                source_license_or_authorization="authorized review copy",
                reviewer_count=1,
                fields=[
                    ExtractionFieldEvaluation(
                        field_name="invoice_date",
                        expected_value="2026-07-01",
                        predicted_value="2026/07/01",
                        prediction_status="extracted",
                        comparison_mode="date",
                    ),
                    ExtractionFieldEvaluation(
                        field_name="buyer_name",
                        expected_value="Example Buyer Ltd.",
                        predicted_value="Wrong Buyer Ltd.",
                        prediction_status="extracted",
                    ),
                    ExtractionFieldEvaluation(
                        field_name="purchase_order_number",
                        expected_value=None,
                        predicted_value="PO-UNKNOWN",
                        prediction_status="extracted",
                    ),
                ],
            ),
        ],
    )


def test_evaluation_reports_errors_and_transparent_metrics():
    report = evaluate_document_extraction_dataset(_dataset())

    assert report.evaluation_scope == "external_holdout"
    assert report.overall.case_count == 2
    assert report.overall.field_count == 7
    assert report.overall.expected_present_count == 5
    assert report.overall.exact_field_match_count == 4
    assert report.overall.true_positive_count == 3
    assert report.overall.false_positive_count == 2
    assert report.overall.false_negative_count == 2
    assert report.overall.abstention_count == 1
    assert report.overall.document_exact_match_count == 0
    assert {item.error_type for item in report.errors} == {
        "false_negative",
        "false_positive",
        "value_mismatch",
    }
    assert {item.slice_name for item in report.by_document_type} == {
        "document_type:commercial_invoice",
        "document_type:contract",
    }
    assert "does not measure legal" in report.authority_boundary


def test_synthetic_case_cannot_be_reported_as_external_holdout():
    report = evaluate_document_extraction_dataset(_dataset(data_origin="synthetic"))

    assert report.evaluation_scope == "mixed_or_synthetic"


def test_field_status_contract_rejects_inconsistent_values():
    with pytest.raises(ValueError, match="requires predicted_value"):
        ExtractionFieldEvaluation(
            field_name="currency",
            expected_value="USD",
            prediction_status="extracted",
        )
    with pytest.raises(ValueError, match="cannot carry predicted_value"):
        ExtractionFieldEvaluation(
            field_name="currency",
            expected_value="USD",
            predicted_value="USD",
            prediction_status="abstained",
        )


def test_case_rejects_duplicate_field_names():
    field = ExtractionFieldEvaluation(
        field_name="currency",
        expected_value="USD",
        predicted_value="USD",
        prediction_status="extracted",
    )
    with pytest.raises(ValueError, match="field_name values must be unique"):
        ExtractionEvaluationCase(
            case_id="DUPLICATE",
            document_type="contract",
            language="en",
            data_origin="synthetic",
            source_locator="synthetic://duplicate",
            source_license_or_authorization="project fixture",
            reviewer_count=1,
            fields=[field, field],
        )
