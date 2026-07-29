"""Field-level holdout evaluation for document extraction outputs.

This module evaluates reviewed gold annotations against a model or parser prediction
file. It does not perform OCR or extraction itself and it never turns a synthetic rule
fixture into a claim about real-document accuracy.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ComparisonMode = Literal["exact", "normalized_text", "number", "date"]
PredictionStatus = Literal["extracted", "abstained", "missing"]
DataOrigin = Literal["public_licensed", "private_authorized", "synthetic"]


class ExtractionFieldEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    field_name: str
    expected_value: Any | None = None
    predicted_value: Any | None = None
    prediction_status: PredictionStatus
    comparison_mode: ComparisonMode = "normalized_text"

    @model_validator(mode="after")
    def status_and_value_are_consistent(self):
        if self.prediction_status == "extracted" and self.predicted_value is None:
            raise ValueError("extracted prediction requires predicted_value")
        if self.prediction_status != "extracted" and self.predicted_value is not None:
            raise ValueError("abstained or missing prediction cannot carry predicted_value")
        return self


class ExtractionEvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: str
    document_type: Literal[
        "contract",
        "commercial_invoice",
        "purchase_order",
        "letter_of_credit",
        "packing_list",
        "bill_of_lading",
        "other",
    ]
    language: str
    split: Literal["holdout"] = "holdout"
    data_origin: DataOrigin
    source_locator: str
    source_license_or_authorization: str
    reviewer_count: int = Field(ge=1)
    fields: list[ExtractionFieldEvaluation]

    @model_validator(mode="after")
    def field_names_are_unique(self):
        names = [item.field_name for item in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("field_name values must be unique within a case")
        if not self.fields:
            raise ValueError("evaluation case must contain at least one field")
        return self


class ExtractionEvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dataset_name: str
    dataset_version: str
    created_date: date
    schema_version: Literal["document-extraction-evaluation/1.0"] = (
        "document-extraction-evaluation/1.0"
    )
    extraction_system_name: str
    extraction_system_version: str
    adjudication_notes: str
    cases: list[ExtractionEvaluationCase]

    @model_validator(mode="after")
    def case_ids_are_unique(self):
        identifiers = [item.case_id for item in self.cases]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("case_id values must be unique")
        if not self.cases:
            raise ValueError("evaluation dataset must contain at least one holdout case")
        return self


class ExtractionErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    document_type: str
    language: str
    field_name: str
    error_type: Literal["false_positive", "false_negative", "value_mismatch"]
    expected_value: Any | None = None
    predicted_value: Any | None = None
    prediction_status: PredictionStatus


class ExtractionMetricSlice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slice_name: str
    case_count: int
    field_count: int
    expected_present_count: int
    exact_field_match_count: int
    true_positive_count: int
    false_positive_count: int
    false_negative_count: int
    abstention_count: int
    document_exact_match_count: int
    precision: float | None
    recall: float | None
    f1: float | None
    field_exact_match_rate: float
    document_exact_match_rate: float
    abstention_rate: float


class ExtractionEvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_version: Literal["document-extraction-report/1.0"] = (
        "document-extraction-report/1.0"
    )
    generated_at: datetime
    dataset_name: str
    dataset_version: str
    extraction_system_name: str
    extraction_system_version: str
    evaluation_scope: Literal["external_holdout", "mixed_or_synthetic"]
    overall: ExtractionMetricSlice
    by_document_type: list[ExtractionMetricSlice]
    by_language: list[ExtractionMetricSlice]
    errors: list[ExtractionErrorDetail]
    authority_boundary: str


_SPACE_PATTERN = re.compile(r"\s+")


def _normalize(value: Any, mode: ComparisonMode) -> Any:
    if value is None:
        return None
    if mode == "exact":
        return value
    if mode == "normalized_text":
        return _SPACE_PATTERN.sub(" ", str(value).strip()).casefold()
    if mode == "number":
        try:
            return Decimal(str(value).replace(",", "").strip()).normalize()
        except (InvalidOperation, AttributeError) as exc:
            raise ValueError(f"Unable to normalize numeric evaluation value: {value}") from exc
    if mode == "date":
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        text = str(value).strip()
        for format_text in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(text, format_text).date().isoformat()
            except ValueError:
                continue
        raise ValueError(f"Unable to normalize date evaluation value: {value}")
    raise ValueError(f"Unsupported comparison mode: {mode}")


def _field_outcome(field: ExtractionFieldEvaluation) -> tuple[bool, int, int, int, str | None]:
    expected_present = field.expected_value is not None
    extracted = field.prediction_status == "extracted"
    if not expected_present and not extracted:
        return True, 0, 0, 0, None
    if expected_present and extracted:
        if _normalize(field.expected_value, field.comparison_mode) == _normalize(
            field.predicted_value, field.comparison_mode
        ):
            return True, 1, 0, 0, None
        return False, 0, 1, 1, "value_mismatch"
    if expected_present:
        return False, 0, 0, 1, "false_negative"
    return False, 0, 1, 0, "false_positive"


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _metric_slice(
    slice_name: str,
    cases: list[ExtractionEvaluationCase],
) -> tuple[ExtractionMetricSlice, list[ExtractionErrorDetail]]:
    field_count = 0
    expected_present_count = 0
    exact_field_match_count = 0
    true_positive_count = 0
    false_positive_count = 0
    false_negative_count = 0
    abstention_count = 0
    exact_documents = 0
    errors: list[ExtractionErrorDetail] = []

    for case in cases:
        case_exact = True
        for field in case.fields:
            field_count += 1
            expected_present_count += int(field.expected_value is not None)
            abstention_count += int(field.prediction_status == "abstained")
            exact, true_positive, false_positive, false_negative, error_type = _field_outcome(
                field
            )
            exact_field_match_count += int(exact)
            true_positive_count += true_positive
            false_positive_count += false_positive
            false_negative_count += false_negative
            case_exact = case_exact and exact
            if error_type is not None:
                errors.append(
                    ExtractionErrorDetail(
                        case_id=case.case_id,
                        document_type=case.document_type,
                        language=case.language,
                        field_name=field.field_name,
                        error_type=error_type,
                        expected_value=field.expected_value,
                        predicted_value=field.predicted_value,
                        prediction_status=field.prediction_status,
                    )
                )
        exact_documents += int(case_exact)

    precision = _safe_ratio(
        true_positive_count,
        true_positive_count + false_positive_count,
    )
    recall = _safe_ratio(
        true_positive_count,
        true_positive_count + false_negative_count,
    )
    f1 = None
    if precision is not None and recall is not None and precision + recall:
        f1 = 2 * precision * recall / (precision + recall)

    return (
        ExtractionMetricSlice(
            slice_name=slice_name,
            case_count=len(cases),
            field_count=field_count,
            expected_present_count=expected_present_count,
            exact_field_match_count=exact_field_match_count,
            true_positive_count=true_positive_count,
            false_positive_count=false_positive_count,
            false_negative_count=false_negative_count,
            abstention_count=abstention_count,
            document_exact_match_count=exact_documents,
            precision=precision,
            recall=recall,
            f1=f1,
            field_exact_match_rate=(exact_field_match_count / field_count if field_count else 0.0),
            document_exact_match_rate=(exact_documents / len(cases) if cases else 0.0),
            abstention_rate=(abstention_count / field_count if field_count else 0.0),
        ),
        errors,
    )


def evaluate_document_extraction_dataset(
    dataset: ExtractionEvaluationDataset,
) -> ExtractionEvaluationReport:
    """Evaluate overall, document-type, and language slices without hiding errors."""

    overall, errors = _metric_slice("overall", dataset.cases)
    by_document: dict[str, list[ExtractionEvaluationCase]] = defaultdict(list)
    by_language: dict[str, list[ExtractionEvaluationCase]] = defaultdict(list)
    for case in dataset.cases:
        by_document[case.document_type].append(case)
        by_language[case.language].append(case)

    document_slices = [
        _metric_slice(f"document_type:{name}", cases)[0]
        for name, cases in sorted(by_document.items())
    ]
    language_slices = [
        _metric_slice(f"language:{name}", cases)[0]
        for name, cases in sorted(by_language.items())
    ]
    scope = (
        "external_holdout"
        if all(case.data_origin != "synthetic" for case in dataset.cases)
        else "mixed_or_synthetic"
    )
    return ExtractionEvaluationReport(
        generated_at=datetime.now().astimezone(),
        dataset_name=dataset.dataset_name,
        dataset_version=dataset.dataset_version,
        extraction_system_name=dataset.extraction_system_name,
        extraction_system_version=dataset.extraction_system_version,
        evaluation_scope=scope,
        overall=overall,
        by_document_type=document_slices,
        by_language=language_slices,
        errors=errors,
        authority_boundary=(
            "Field-level holdout extraction evaluation only. It does not measure legal "
            "interpretation, transaction approval, credit outcomes, sanctions clearance, "
            "product eligibility, or production suitability. Synthetic cases must not be "
            "reported as external-document accuracy."
        ),
    )


def load_document_extraction_dataset(path: str | Path) -> ExtractionEvaluationDataset:
    dataset_path = Path(path)
    try:
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load extraction evaluation dataset: {dataset_path}") from exc
    return ExtractionEvaluationDataset.model_validate(payload)


def write_document_extraction_report(
    report: ExtractionEvaluationReport,
    path: str | Path,
) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return report_path
