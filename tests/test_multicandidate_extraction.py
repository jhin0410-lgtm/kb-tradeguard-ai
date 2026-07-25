import io

import pandas as pd

from src.document_extraction import DeterministicSpreadsheetExtractor
from src.document_models import UploadedDocument
from src.document_validation import (
    batch_approve_extracted_transactions,
    create_review_queue,
)


def test_multiple_csv_rows_create_separate_candidates_and_provenance():
    content = (
        "transaction_id,transaction_type,currency,amount_fc,expected_date\n"
        "A-1,export,USD,100,2026-10-01\n"
        "A-2,import,EUR,200,2026-11-01\n"
    ).encode()
    candidates = DeterministicSpreadsheetExtractor().extract(
        UploadedDocument(filename="multi.csv", content=content)
    )
    assert len(candidates) == 2
    assert candidates[0].transaction_id == "A-1"
    assert candidates[1].transaction_id == "A-2"
    assert candidates[0].source_page == "CSV row 2"
    assert candidates[1].source_page == "CSV row 3"


def test_every_xlsx_sheet_is_inspected_and_header_rows_detected():
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(
            [["note", None, None], ["transaction_id", "direction", "ccy"], ["S1", "export", "USD"]],
        ).to_excel(writer, sheet_name="Exports", index=False, header=False)
        pd.DataFrame(
            [
                {
                    "transaction_id": "S2",
                    "transaction_type": "import",
                    "currency": "EUR",
                    "amount_fc": 300,
                    "expected_date": "2026-12-01",
                }
            ]
        ).to_excel(writer, sheet_name="Imports", index=False)
    candidates = DeterministicSpreadsheetExtractor().extract(
        UploadedDocument(filename="sheets.xlsx", content=buffer.getvalue())
    )
    # The first sheet candidate is invalid because the illustrative header lacks
    # amount/date, but it is still preserved rather than silently dropped.
    assert len(candidates) == 2
    assert {candidate.source_page.split(",")[0] for candidate in candidates} == {
        "Sheet: Exports",
        "Sheet: Imports",
    }


def test_parsing_and_semantic_confidence_are_separate():
    content = (
        "trade_type,ccy,invoice_amount,due_date\n"
        "export,USD,100,2026-12-15\n"
    ).encode()
    candidate = DeterministicSpreadsheetExtractor().extract(
        UploadedDocument(filename="alias.csv", content=content)
    )[0]
    assert candidate.parsing_confidence == 1.0
    assert candidate.semantic_mapping_confidence == 0.75
    assert candidate.parsing_confidence != candidate.semantic_mapping_confidence
    assert (
        candidate.provenance["amount_fc"].parsing_confidence == 1.0
    )
    assert (
        candidate.provenance["amount_fc"].semantic_mapping_confidence == 0.75
    )


def test_invalid_value_remains_invalid_despite_exact_parsing():
    content = (
        "transaction_type,currency,amount_fc,expected_date\n"
        "export,USD,,2026-12-15\n"
    ).encode()
    candidate = DeterministicSpreadsheetExtractor().extract(
        UploadedDocument(filename="invalid.csv", content=content)
    )[0]
    assert candidate.parsing_confidence == 1.0
    assert candidate.validation_status == "invalid"


def test_duplicate_fingerprint_and_queue_do_not_register():
    content = (
        "transaction_id,transaction_type,currency,amount_fc,expected_date,document_reference\n"
        "D-1,export,USD,100,2026-12-15,R-1\n"
        "D-2,export,USD,100,2026-12-15,R-1\n"
    ).encode()
    candidates = DeterministicSpreadsheetExtractor().extract(
        UploadedDocument(filename="dup.csv", content=content)
    )
    queue = create_review_queue(candidates, {"USD", "EUR"})
    assert queue[0].status == "pending"
    assert queue[1].status == "possible_duplicate"
    assert (
        queue[0].canonical_transaction_fingerprint
        == queue[1].canonical_transaction_fingerprint
    )
    assert "source_filename" not in queue[0].canonical_fingerprint_fields


def test_batch_approval_records_each_approval_and_rejection_registers_none():
    content = (
        "transaction_id,transaction_type,currency,amount_fc,expected_date\n"
        "B-1,export,USD,100,2026-10-01\n"
        "B-2,import,EUR,200,2026-11-01\n"
    ).encode()
    candidates = DeterministicSpreadsheetExtractor().extract(
        UploadedDocument(filename="batch.csv", content=content)
    )
    results = batch_approve_extracted_transactions(
        [
            {
                "candidate": candidates[0],
                "edited_values": {"validation_status": "review_required"},
                "reviewed_fields": [],
                "decision": "approved",
            },
            {
                "candidate": candidates[1],
                "decision": "rejected",
            },
        ],
        {"USD", "EUR"},
        set(),
        set(),
    )
    assert results[0].registered_transaction["transaction_id"] == "B-1"
    assert results[0].approval_event["event_type"] == "approval"
    assert results[1].registered_transaction is None
