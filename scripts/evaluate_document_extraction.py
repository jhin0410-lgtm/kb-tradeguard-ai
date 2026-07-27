"""Evaluate a reviewed document-extraction holdout file and write a JSON report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.intelligence.document_extraction_evaluation import (
    evaluate_document_extraction_dataset,
    load_document_extraction_dataset,
    write_document_extraction_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate reviewed field-level document extraction predictions."
    )
    parser.add_argument("dataset", type=Path, help="UTF-8 evaluation dataset JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/document_extraction_evaluation_report.json"),
        help="Report JSON path",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    dataset = load_document_extraction_dataset(args.dataset)
    report = evaluate_document_extraction_dataset(dataset)
    output = write_document_extraction_report(report, args.output)
    summary = {
        "output": str(output),
        "evaluation_scope": report.evaluation_scope,
        "case_count": report.overall.case_count,
        "field_count": report.overall.field_count,
        "field_exact_match_rate": report.overall.field_exact_match_rate,
        "document_exact_match_rate": report.overall.document_exact_match_rate,
        "precision": report.overall.precision,
        "recall": report.overall.recall,
        "f1": report.overall.f1,
        "abstention_rate": report.overall.abstention_rate,
        "error_count": len(report.errors),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
