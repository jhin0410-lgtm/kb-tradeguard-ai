"""Trade-document extractor interfaces and optional structured AI provider."""

from __future__ import annotations

import io
import hashlib
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd

from .document_models import (
    ExtractedTradeDocument,
    FieldProvenance,
    UploadedDocument,
)

HEADING_ALIASES = {
    "transaction_id": {"transaction_id", "transaction id", "거래번호"},
    "document_type": {"document_type", "document type", "문서유형"},
    "transaction_type": {
        "transaction_type",
        "transaction type",
        "direction",
        "trade_type",
        "수출입구분",
    },
    "currency": {"currency", "ccy", "통화"},
    "amount_fc": {
        "amount_fc",
        "amount",
        "foreign amount",
        "invoice_amount",
        "금액",
    },
    "expected_date": {
        "expected_date",
        "expected date",
        "settlement_date",
        "due_date",
        "결제예정일",
    },
    "invoice_date": {"invoice_date", "invoice date", "발행일"},
    "counterparty_name": {
        "counterparty_name",
        "counterparty",
        "buyer",
        "seller",
        "거래상대방",
    },
    "counterparty_country": {
        "counterparty_country",
        "country",
        "상대국가",
    },
    "item_description": {
        "item_description",
        "description",
        "item",
        "품목",
    },
    "payment_terms": {"payment_terms", "payment terms", "결제조건"},
    "incoterm": {"incoterm", "incoterms", "인코텀즈"},
    "document_reference": {
        "document_reference",
        "document reference",
        "invoice_no",
        "invoice number",
        "문서번호",
    },
    "probability": {"probability", "확률"},
    "status": {"status", "거래상태"},
}
REQUIRED_EXTRACTED_FIELDS = (
    "transaction_type",
    "currency",
    "amount_fc",
    "expected_date",
)


class TradeDocumentExtractor(ABC):
    @abstractmethod
    def extract(self, document: UploadedDocument) -> list[ExtractedTradeDocument]:
        """Extract reviewable candidates without registering transactions."""


def _upload_identity(document: UploadedDocument) -> dict[str, Any]:
    return {
        "upload_content_sha256": hashlib.sha256(document.content).hexdigest(),
        "upload_file_size": len(document.content),
    }


def _normalized_heading(value: Any) -> str:
    return str(value).strip().lower()


def _canonical_heading_map(columns: list[Any]) -> tuple[dict[str, Any], list[str]]:
    mapping: dict[str, Any] = {}
    warnings = []
    normalized = {_normalized_heading(column): column for column in columns}
    for field, aliases in HEADING_ALIASES.items():
        hits = [normalized[alias] for alias in aliases if alias in normalized]
        if len(hits) > 1:
            warnings.append(f"Ambiguous headings for {field}: {hits}")
        if hits:
            mapping[field] = hits[0]
    return mapping, warnings


def _normalize_value(field: str, value: Any) -> Any:
    if pd.isna(value):
        return None
    if field == "transaction_type":
        normalized = str(value).strip().lower()
        aliases = {"수출": "export", "export": "export", "수입": "import", "import": "import"}
        return aliases.get(normalized, normalized)
    if field == "currency":
        return str(value).strip().upper()
    if field in {"expected_date", "invoice_date"}:
        parsed = pd.to_datetime(value, errors="coerce")
        return None if pd.isna(parsed) else parsed.date()
    if field in {"amount_fc", "probability"}:
        return float(value)
    if field == "status":
        return str(value).strip().lower()
    return str(value).strip()


class DeterministicSpreadsheetExtractor(TradeDocumentExtractor):
    """Map known CSV/XLSX headings and preserve row/sheet provenance."""

    def _read_frames(
        self, document: UploadedDocument
    ) -> list[tuple[str, pd.DataFrame, int]]:
        suffix = Path(document.filename).suffix.lower()
        if suffix == ".csv":
            raw = pd.read_csv(io.BytesIO(document.content), header=None)
            return [("CSV", raw, self._find_header_row(raw))]
        elif suffix == ".xlsx":
            workbook = pd.ExcelFile(io.BytesIO(document.content))
            frames = []
            for sheet in workbook.sheet_names:
                raw = pd.read_excel(workbook, sheet_name=sheet, header=None)
                if not raw.dropna(how="all").empty:
                    frames.append((sheet, raw, self._find_header_row(raw)))
            return frames
        else:
            raise ValueError("DeterministicSpreadsheetExtractor supports CSV and XLSX")

    @staticmethod
    def _find_header_row(raw: pd.DataFrame) -> int:
        alias_set = set().union(*HEADING_ALIASES.values())
        scored = []
        for index, row in raw.iterrows():
            matches = sum(
                _normalized_heading(value) in alias_set
                for value in row
                if not pd.isna(value)
            )
            scored.append((matches, -int(index), int(index)))
        best_matches, _, best_index = max(scored, default=(0, 0, 0))
        if best_matches < 2:
            raise ValueError("Could not identify a likely spreadsheet header row")
        return best_index

    def extract(self, document: UploadedDocument) -> list[ExtractedTradeDocument]:
        frames = self._read_frames(document)
        if not frames:
            raise ValueError("Spreadsheet contains no transaction rows")
        candidates = []
        suffix = Path(document.filename).suffix.lower()
        method = (
            "deterministic_csv_heading_map"
            if suffix == ".csv"
            else "deterministic_xlsx_heading_map"
        )
        for sheet, raw, header_index in frames:
            headings = list(raw.iloc[header_index])
            frame = raw.iloc[header_index + 1 :].copy()
            frame.columns = headings
            frame = frame.dropna(how="all")
            if frame.empty:
                continue
            candidates.extend(
                self._extract_rows(
                    document.filename,
                    sheet,
                    frame,
                    header_index,
                    method,
                )
            )
        identity = _upload_identity(document)
        return [
            candidate.model_copy(update=identity) for candidate in candidates
        ]

    def _extract_rows(
        self,
        filename: str,
        sheet: str,
        frame: pd.DataFrame,
        header_index: int,
        method: str,
    ) -> list[ExtractedTradeDocument]:
        heading_map, warnings = _canonical_heading_map(list(frame.columns))
        normalized_columns = {
            _normalized_heading(column): column for column in frame.columns
        }
        candidates = []
        for row_position, (_, row) in enumerate(frame.iterrows(), start=1):
            row_warnings = list(warnings)
            values: dict[str, Any] = {}
            provenance = {}
            page_or_sheet = (
                f"CSV row {header_index + row_position + 1}"
                if sheet == "CSV"
                else f"Sheet: {sheet}, row {header_index + row_position + 1}"
            )
            for field, aliases in HEADING_ALIASES.items():
                hit_columns = [
                    normalized_columns[alias]
                    for alias in aliases
                    if alias in normalized_columns
                ]
                hit_values = {
                    str(row[column]).strip()
                    for column in hit_columns
                    if not pd.isna(row[column])
                }
                if len(hit_values) > 1:
                    row_warnings.append(
                        f"Conflicting values for {field}: {sorted(hit_values)}"
                    )
            for field, column in heading_map.items():
                value = _normalize_value(field, row[column])
                values[field] = value
                normalized_column = _normalized_heading(column)
                canonical = normalized_column == field
                provenance[field] = FieldProvenance(
                    source_file=filename,
                    page_or_sheet=page_or_sheet,
                    source_excerpt=f"{column}: {row[column]}",
                    extraction_method=method,
                    parsing_confidence=1.0,
                    semantic_mapping_confidence=0.90 if canonical else 0.75,
                )
            missing = [
                field
                for field in REQUIRED_EXTRACTED_FIELDS
                if values.get(field) is None
            ]
            row_warnings.extend(
                f"Missing required field: {field}" for field in missing
            )
            semantic_values = [
                evidence.semantic_mapping_confidence
                for evidence in provenance.values()
            ]
            semantic = (
                sum(semantic_values) / len(semantic_values)
                if semantic_values
                else 0.0
            )
            status = (
                "invalid"
                if missing
                else "review_required"
                if row_warnings
                else "valid"
            )
            candidates.append(
                ExtractedTradeDocument(
                    **values,
                    source_filename=filename,
                    source_page=page_or_sheet,
                    parsing_confidence=1.0,
                    semantic_mapping_confidence=semantic,
                    validation_status=status,
                    extraction_method=method,
                    warnings=row_warnings,
                    provenance=provenance,
                )
            )
        return candidates


class PdfTextExtractor(TradeDocumentExtractor):
    """Extract text and page evidence from text-based PDFs; never performs OCR."""

    def extract(self, document: UploadedDocument) -> list[ExtractedTradeDocument]:
        if Path(document.filename).suffix.lower() != ".pdf":
            raise ValueError("PdfTextExtractor supports PDF files")
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required for PDF text extraction") from exc
        reader = PdfReader(io.BytesIO(document.content))
        pages = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append(f"[Page {page_number}]\n{text}")
        combined = "\n\n".join(pages)
        warnings = [
            f"Missing required field: {field}" for field in REQUIRED_EXTRACTED_FIELDS
        ]
        if not combined.strip():
            warnings.append("No extractable PDF text found; OCR is not supported")
        return [ExtractedTradeDocument(
            document_type="PDF",
            source_filename=document.filename,
            **_upload_identity(document),
            source_page="; ".join(
                f"Page {number}" for number in range(1, len(reader.pages) + 1)
            ),
            parsing_confidence=1.0 if combined.strip() else 0.0,
            semantic_mapping_confidence=0.0,
            validation_status="invalid",
            extraction_method="pdf_text_extraction_no_ocr",
            warnings=warnings,
            document_text=combined,
            provenance={
                "document_text": FieldProvenance(
                    source_file=document.filename,
                    page_or_sheet="All extractable pages",
                    source_excerpt=combined[:500] or None,
                    extraction_method="pdf_text_extraction_no_ocr",
                    parsing_confidence=1.0 if combined.strip() else 0.0,
                    semantic_mapping_confidence=0.0,
                )
            },
        )]


class PlainTextExtractor(TradeDocumentExtractor):
    """Display TXT content for human review without inventing structured values."""

    def extract(self, document: UploadedDocument) -> list[ExtractedTradeDocument]:
        text = document.content.decode("utf-8", errors="replace")
        return [ExtractedTradeDocument(
            document_type="TXT",
            source_filename=document.filename,
            **_upload_identity(document),
            source_page="Text file",
            parsing_confidence=1.0,
            semantic_mapping_confidence=0.0,
            validation_status="invalid",
            extraction_method="plain_text_display_no_structured_inference",
            warnings=[
                f"Missing required field: {field}"
                for field in REQUIRED_EXTRACTED_FIELDS
            ],
            document_text=text,
            provenance={
                "document_text": FieldProvenance(
                    source_file=document.filename,
                    page_or_sheet="Text file",
                    source_excerpt=text[:500] or None,
                    extraction_method="plain_text_display_no_structured_inference",
                    parsing_confidence=1.0,
                    semantic_mapping_confidence=0.0,
                )
            },
        )]


class OptionalStructuredLLMExtractor(TradeDocumentExtractor):
    """Optional JSON-schema extractor isolated from all financial calculations."""

    def __init__(self, client=None, model: str | None = None):
        self.model = model or os.getenv("OPENAI_DOCUMENT_MODEL", "gpt-4.1-mini")
        self.client = client
        if self.client is None and os.getenv("OPENAI_API_KEY"):
            try:
                from openai import OpenAI

                self.client = OpenAI()
            except ImportError:
                self.client = None

    @property
    def is_available(self) -> bool:
        return self.client is not None and bool(os.getenv("OPENAI_API_KEY"))

    def extract(self, document: UploadedDocument) -> list[ExtractedTradeDocument]:
        if not self.is_available:
            raise RuntimeError(
                "Optional structured LLM extraction is not configured; "
                "deterministic extraction remains available"
            )
        text_result = (
            PdfTextExtractor().extract(document)
            if Path(document.filename).suffix.lower() == ".pdf"
            else PlainTextExtractor().extract(document)
        )[0]
        schema = {
            "type": "array",
            "items": ExtractedTradeDocument.model_json_schema(),
        }
        prompt = (
            "Extract only explicitly supported trade-document facts. Never infer or "
            "invent missing amounts, dates, currencies, counterparties, or directions. "
            "Use null for missing values, preserve short source excerpts, and add "
            "warnings for conflicts. Do not perform financial calculations.\n\n"
            + (text_result.document_text or "")
        )
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "trade_document_extraction",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        payload = json.loads(response.output_text)
        candidates = []
        for item in payload:
            item["source_filename"] = document.filename
            item["extraction_method"] = "optional_structured_llm_json_schema"
            item.update(_upload_identity(document))
            candidates.append(ExtractedTradeDocument.model_validate(item))
        return candidates


def select_deterministic_extractor(filename: str) -> TradeDocumentExtractor:
    suffix = Path(filename).suffix.lower()
    if suffix in {".csv", ".xlsx"}:
        return DeterministicSpreadsheetExtractor()
    if suffix == ".pdf":
        return PdfTextExtractor()
    if suffix == ".txt":
        return PlainTextExtractor()
    raise ValueError("Supported document types are PDF, XLSX, CSV, and TXT")
