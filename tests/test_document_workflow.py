import io

import pandas as pd
import pytest
from pypdf import PdfWriter

from src.document_extraction import (
    DeterministicSpreadsheetExtractor,
    PdfTextExtractor,
)
from src.document_models import (
    ExtractedTradeDocument,
    FieldProvenance,
    UploadedDocument,
)
from src.document_validation import (
    approve_extracted_transaction,
    validate_extracted_candidate,
)


def test_csv_heading_aliases_and_nulls_are_not_invented():
    content = (
        "trade_type,ccy,invoice_amount,due_date,invoice_no\n"
        "export,USD,12345,2026-12-15,INV-1\n"
    ).encode()
    result = DeterministicSpreadsheetExtractor().extract(
        UploadedDocument(filename="trade.csv", content=content)
    )[0]
    assert result.transaction_type == "export"
    assert result.currency == "USD"
    assert result.amount_fc == 12_345
    assert str(result.expected_date) == "2026-12-15"
    assert result.counterparty_name is None
    assert result.provenance["amount_fc"].source_excerpt == "invoice_amount: 12345"


def test_conflicting_alias_values_generate_warning():
    content = (
        "trade_type,ccy,amount,invoice_amount,due_date\n"
        "export,USD,100,200,2026-12-15\n"
    ).encode()
    result = DeterministicSpreadsheetExtractor().extract(
        UploadedDocument(filename="conflict.csv", content=content)
    )[0]
    assert any(
        "Conflicting values for amount_fc" in warning
        for warning in result.warnings
    )


def test_xlsx_preserves_sheet_provenance():
    buffer = io.BytesIO()
    frame = pd.DataFrame(
        [
            {
                "direction": "import",
                "currency": "EUR",
                "amount": 5000,
                "settlement_date": "2026-10-01",
            }
        ]
    )
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Invoice", index=False)
    result = DeterministicSpreadsheetExtractor().extract(
        UploadedDocument(filename="trade.xlsx", content=buffer.getvalue())
    )[0]
    assert result.source_page == "Sheet: Invoice, row 2"
    assert result.provenance["currency"].page_or_sheet == "Sheet: Invoice, row 2"


def test_pdf_text_extraction_preserves_page_reference_without_ocr():
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buffer)
    result = PdfTextExtractor().extract(
        UploadedDocument(filename="invoice.pdf", content=buffer.getvalue())
    )[0]
    assert "Page 1" in result.source_page
    assert result.extraction_method == "pdf_text_extraction_no_ocr"
    assert any("Missing required field" in warning for warning in result.warnings)


def _candidate(confidence=1.0):
    provenance = {
        field: FieldProvenance(
            source_file="trade.csv",
            page_or_sheet="CSV row 2",
            source_excerpt=field,
            extraction_method="test",
            confidence=confidence,
        )
        for field in ("transaction_type", "currency", "amount_fc", "expected_date")
    }
    return ExtractedTradeDocument(
        transaction_id="DOC-001",
        transaction_type="export",
        currency="USD",
        amount_fc=1000,
        expected_date="2026-12-01",
        document_reference="REF-1",
        source_filename="trade.csv",
        extraction_confidence=confidence,
        extraction_method="test",
        provenance=provenance,
    )


def test_missing_unsupported_and_duplicate_reference_block_approval():
    missing = ExtractedTradeDocument(
        source_filename="x.txt", extraction_method="test"
    )
    validation = validate_extracted_candidate(missing, {"USD", "EUR"})
    assert len(validation.errors) == 4

    unsupported = _candidate().model_copy(update={"currency": "JPY"})
    validation = validate_extracted_candidate(unsupported, {"USD", "EUR"})
    assert "Unsupported currency: JPY" in validation.errors

    duplicate = validate_extracted_candidate(
        _candidate(), {"USD", "EUR"}, {"REF-1"}
    )
    assert "Duplicate document reference: REF-1" in duplicate.errors


def test_extraction_does_not_register_and_rejection_changes_nothing():
    result = approve_extracted_transaction(
        _candidate(),
        {},
        {"USD", "EUR"},
        set(),
        set(),
        {"transaction_type", "currency", "amount_fc", "expected_date"},
        approved=False,
    )
    assert result.registered_transaction is None
    assert result.approval_event is None


def test_low_confidence_requires_review_and_edits_are_registered():
    candidate = _candidate(confidence=0.5)
    with pytest.raises(ValueError, match="must be reviewed"):
        approve_extracted_transaction(
            candidate,
            {"amount_fc": 1200},
            {"USD", "EUR"},
            set(),
            set(),
            set(),
            approved=True,
        )
    approved = approve_extracted_transaction(
        candidate,
        {"amount_fc": 1200},
        {"USD", "EUR"},
        set(),
        set(),
        {"transaction_type", "currency", "amount_fc", "expected_date"},
        approved=True,
    )
    assert approved.registered_transaction["amount_fc"] == 1200
    assert approved.approval_event["changed_fields"]["amount_fc"] == {
        "extracted": 1000.0,
        "approved": 1200,
    }


def test_duplicate_transaction_id_blocks_approval():
    with pytest.raises(ValueError, match="Duplicate transaction ID"):
        approve_extracted_transaction(
            _candidate(),
            {},
            {"USD", "EUR"},
            {"DOC-001"},
            set(),
            {"transaction_type", "currency", "amount_fc", "expected_date"},
            approved=True,
        )
