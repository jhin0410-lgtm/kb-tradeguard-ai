"""Human-review validation and explicit transaction approval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

import pandas as pd

from .document_extraction import REQUIRED_EXTRACTED_FIELDS
from .document_models import ExtractedTradeDocument, ReviewQueueItem
from .validators import validate_transactions

LOW_CONFIDENCE_THRESHOLD = 0.60
HIGH_CONFIDENCE_THRESHOLD = 0.85


@dataclass(frozen=True)
class CandidateValidation:
    errors: list[str]
    warnings: list[str]
    low_confidence_required_fields: list[str]

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class ApprovalResult:
    registered_transaction: dict[str, Any] | None
    approval_event: dict[str, Any] | None


def canonical_transaction_fingerprint(
    candidate: ExtractedTradeDocument,
) -> tuple[str, list[str]]:
    """Fingerprint transaction meaning independently of upload filename."""

    fields = [
        "transaction_type",
        "currency",
        "amount_fc",
        "expected_date",
        "counterparty_name",
    ]
    if candidate.document_reference:
        fields.insert(0, "document_reference")
    normalized = {}
    for field in fields:
        value = getattr(candidate, field)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        if isinstance(value, str):
            value = " ".join(value.strip().lower().split())
        normalized[field] = value
    digest = hashlib.sha256(
        json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return digest, fields


def transaction_fingerprint(
    candidate: ExtractedTradeDocument,
) -> tuple[str, list[str]]:
    """Compatibility alias for the canonical transaction fingerprint."""
    return canonical_transaction_fingerprint(candidate)


def upload_file_fingerprint(
    candidate: ExtractedTradeDocument,
) -> tuple[str, list[str]]:
    """Fingerprint one uploaded file using content hash, name, and size."""
    fields = ["upload_content_sha256", "source_filename", "upload_file_size"]
    normalized = {
        "upload_content_sha256": candidate.upload_content_sha256 or "",
        "source_filename": candidate.source_filename.strip().lower(),
        "upload_file_size": candidate.upload_file_size or 0,
    }
    digest = hashlib.sha256(
        json.dumps(normalized, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return digest, fields


def near_duplicate_key(
    candidate: ExtractedTradeDocument,
) -> tuple[str, list[str]]:
    """Coarse deterministic key used only to flag probable near duplicates."""
    fields = ["transaction_type", "currency", "amount_fc", "expected_date"]
    normalized = {}
    for field in fields:
        value = getattr(candidate, field)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        if isinstance(value, str):
            value = " ".join(value.strip().lower().split())
        normalized[field] = value
    digest = hashlib.sha256(
        json.dumps(normalized, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return digest, fields


def create_review_queue(
    candidates: list[ExtractedTradeDocument],
    supported_currencies: set[str],
    existing_fingerprints: dict[str, str] | None = None,
    existing_upload_fingerprints: dict[str, str] | None = None,
    existing_content_hashes: dict[str, str] | None = None,
    existing_near_duplicate_keys: dict[str, str] | None = None,
) -> list[ReviewQueueItem]:
    """Create pending/invalid/duplicate queue items without registration."""

    existing = dict(existing_fingerprints or {})
    existing_uploads = dict(existing_upload_fingerprints or {})
    existing_content = dict(existing_content_hashes or {})
    existing_near = dict(existing_near_duplicate_keys or {})
    queue = []
    seen_batch: dict[str, str] = {}
    seen_near: dict[str, str] = {}
    for index, candidate in enumerate(candidates, start=1):
        fingerprint, fields = canonical_transaction_fingerprint(candidate)
        file_fingerprint, file_fields = upload_file_fingerprint(candidate)
        near_key, near_fields = near_duplicate_key(candidate)
        validation = validate_extracted_candidate(candidate, supported_currencies)
        duplicate_of = None
        duplicate_category = None
        if file_fingerprint in existing_uploads:
            duplicate_of = existing_uploads[file_fingerprint]
            duplicate_category = "exact_same_file"
        elif (
            candidate.upload_content_sha256
            and candidate.upload_content_sha256 in existing_content
        ):
            duplicate_of = existing_content[candidate.upload_content_sha256]
            duplicate_category = "renamed_same_file"
        elif fingerprint in existing:
            duplicate_of = existing[fingerprint]
            duplicate_category = "same_transaction_different_file"
        elif fingerprint in seen_batch:
            duplicate_of = seen_batch[fingerprint]
            duplicate_category = "probable_near_duplicate"
        elif near_key in existing_near or near_key in seen_near:
            duplicate_of = existing_near.get(near_key) or seen_near[near_key]
            duplicate_category = "probable_near_duplicate"
        if validation.errors or candidate.validation_status == "invalid":
            status = "invalid"
        elif duplicate_of:
            status = "possible_duplicate"
        else:
            status = "pending"
        candidate_id = f"{candidate.source_filename}#{index}"
        queue.append(
            ReviewQueueItem(
                candidate_id=candidate_id,
                candidate=candidate,
                status=status,
                canonical_transaction_fingerprint=fingerprint,
                canonical_fingerprint_fields=fields,
                upload_file_fingerprint=file_fingerprint,
                upload_fingerprint_fields=file_fields,
                upload_content_sha256=candidate.upload_content_sha256 or "",
                near_duplicate_key=near_key,
                near_duplicate_fields=near_fields,
                duplicate_category=duplicate_category,
                duplicate_of=duplicate_of,
            )
        )
        seen_batch[fingerprint] = candidate_id
        seen_near[near_key] = candidate_id
    return queue


def validate_extracted_candidate(
    candidate: ExtractedTradeDocument,
    supported_currencies: set[str],
    existing_document_references: set[str] | None = None,
) -> CandidateValidation:
    errors = []
    warnings = list(candidate.warnings)
    for field in REQUIRED_EXTRACTED_FIELDS:
        if getattr(candidate, field) is None:
            errors.append(f"Missing required field: {field}")
    if candidate.currency and candidate.currency.upper() not in {
        value.upper() for value in supported_currencies
    }:
        errors.append(f"Unsupported currency: {candidate.currency}")
    if candidate.validation_status == "invalid" and not errors:
        errors.append("Candidate validation status is invalid")
    if (
        candidate.document_reference
        and existing_document_references
        and candidate.document_reference in existing_document_references
    ):
        errors.append(
            f"Duplicate document reference: {candidate.document_reference}"
        )
    low_fields = []
    for field in REQUIRED_EXTRACTED_FIELDS:
        provenance = candidate.provenance.get(field)
        confidence = (
            provenance.semantic_mapping_confidence
            if provenance is not None
            else candidate.semantic_mapping_confidence
        )
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            low_fields.append(field)
    return CandidateValidation(errors, warnings, low_fields)


def approve_extracted_transaction(
    candidate: ExtractedTradeDocument,
    edited_values: dict[str, Any],
    supported_currencies: set[str],
    existing_transaction_ids: set[str],
    existing_document_references: set[str],
    reviewed_fields: set[str],
    approved: bool,
) -> ApprovalResult:
    """Register only explicit approval after edits and low-confidence review."""

    if not approved:
        return ApprovalResult(None, None)
    updated = ExtractedTradeDocument.model_validate(
        {**candidate.model_dump(), **edited_values}
    )
    validation = validate_extracted_candidate(
        updated, supported_currencies, existing_document_references
    )
    if validation.errors:
        raise ValueError("; ".join(validation.errors))
    unreviewed = set(validation.low_confidence_required_fields) - set(reviewed_fields)
    if unreviewed:
        raise ValueError(
            "Low-confidence required fields must be reviewed: "
            + ", ".join(sorted(unreviewed))
        )
    transaction_id = updated.transaction_id
    if not transaction_id:
        raise ValueError("transaction_id is required for approval")
    if transaction_id in existing_transaction_ids:
        raise ValueError(f"Duplicate transaction ID: {transaction_id}")
    transaction = {
        "transaction_id": transaction_id,
        "transaction_type": updated.transaction_type,
        "currency": updated.currency.upper() if updated.currency else None,
        "amount_fc": updated.amount_fc,
        "probability": updated.probability if updated.probability is not None else 1.0,
        "status": updated.status or "expected",
        "expected_date": updated.expected_date,
        "invoice_date": updated.invoice_date,
        "document_reference": updated.document_reference,
        "document_type": updated.document_type,
        "counterparty_name": updated.counterparty_name,
        "counterparty_country": updated.counterparty_country,
        "item_description": updated.item_description,
        "payment_terms": updated.payment_terms,
        "incoterm": updated.incoterm,
        "source_filename": updated.source_filename,
        "source_type": "approved_document",
    }
    fingerprint, fingerprint_fields = canonical_transaction_fingerprint(updated)
    file_fingerprint, file_fingerprint_fields = upload_file_fingerprint(updated)
    near_key, near_fields = near_duplicate_key(updated)
    transaction["canonical_transaction_fingerprint"] = fingerprint
    transaction["canonical_fingerprint_fields"] = fingerprint_fields
    transaction["upload_file_fingerprint"] = file_fingerprint
    transaction["upload_fingerprint_fields"] = file_fingerprint_fields
    transaction["upload_content_sha256"] = updated.upload_content_sha256
    transaction["upload_file_size"] = updated.upload_file_size
    transaction["near_duplicate_key"] = near_key
    transaction["near_duplicate_fields"] = near_fields
    validate_transactions(pd.DataFrame([transaction]))
    changes = {
        key: {"extracted": getattr(candidate, key, None), "approved": value}
        for key, value in edited_values.items()
        if getattr(candidate, key, None) != value
    }
    timestamp = datetime.now(timezone.utc).isoformat()
    event = {
        "event_type": "approval",
        "approval_timestamp": timestamp,
        "transaction_id": transaction_id,
        "document_reference": updated.document_reference,
        "changed_fields": changes,
        "approved_values": transaction,
    }
    return ApprovalResult(transaction, event)


def batch_approve_extracted_transactions(
    requests: list[dict[str, Any]],
    supported_currencies: set[str],
    existing_transaction_ids: set[str],
    existing_document_references: set[str],
) -> list[ApprovalResult]:
    """Process every queue decision independently and record separate approvals."""

    results = []
    ids = set(existing_transaction_ids)
    references = set(existing_document_references)
    for request in requests:
        if request.get("decision") == "rejected":
            results.append(ApprovalResult(None, None))
            continue
        if request.get("decision") != "approved":
            continue
        result = approve_extracted_transaction(
            request["candidate"],
            request.get("edited_values", {}),
            supported_currencies,
            ids,
            references,
            set(request.get("reviewed_fields", [])),
            approved=True,
        )
        results.append(result)
        if result.registered_transaction:
            ids.add(result.registered_transaction["transaction_id"])
            reference = result.registered_transaction.get("document_reference")
            if reference:
                references.add(reference)
    return results
