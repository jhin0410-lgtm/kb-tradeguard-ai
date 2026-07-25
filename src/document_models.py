"""Structured trade-document and provenance data models."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FieldProvenance(BaseModel):
    """Source evidence for one extracted field; never model reasoning."""

    source_file: str
    page_or_sheet: str | None = None
    source_excerpt: str | None = None
    extraction_method: str
    parsing_confidence: float = Field(default=0.0, ge=0, le=1)
    semantic_mapping_confidence: float = Field(default=0.0, ge=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_confidence(cls, value):
        if isinstance(value, dict) and "confidence" in value:
            migrated = dict(value)
            confidence = migrated.pop("confidence")
            migrated.setdefault("parsing_confidence", confidence)
            migrated.setdefault("semantic_mapping_confidence", confidence)
            return migrated
        return value

    @property
    def confidence(self) -> float:
        """Compatibility alias; UI must display the two explicit fields."""

        return self.semantic_mapping_confidence


class ExtractedTradeDocument(BaseModel):
    """Reviewable extraction result. Missing information remains null."""

    model_config = ConfigDict(str_strip_whitespace=True)

    transaction_id: str | None = None
    document_type: str | None = None
    transaction_type: Literal["export", "import"] | None = None
    currency: str | None = None
    amount_fc: float | None = Field(default=None, gt=0)
    expected_date: date | None = None
    invoice_date: date | None = None
    counterparty_name: str | None = None
    counterparty_country: str | None = None
    item_description: str | None = None
    payment_terms: str | None = None
    incoterm: str | None = None
    document_reference: str | None = None
    source_filename: str
    upload_content_sha256: str | None = None
    upload_file_size: int | None = Field(default=None, ge=0)
    source_page: str | None = None
    parsing_confidence: float = Field(default=0.0, ge=0, le=1)
    semantic_mapping_confidence: float = Field(default=0.0, ge=0, le=1)
    validation_status: Literal["valid", "review_required", "invalid"] = "review_required"
    extraction_method: str
    probability: float | None = Field(default=None, ge=0, le=1)
    status: Literal["confirmed", "expected"] | None = None
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, FieldProvenance] = Field(default_factory=dict)
    document_text: str | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_confidence(cls, value):
        if isinstance(value, dict) and "extraction_confidence" in value:
            migrated = dict(value)
            confidence = migrated.pop("extraction_confidence")
            migrated.setdefault("parsing_confidence", confidence)
            migrated.setdefault("semantic_mapping_confidence", confidence)
            return migrated
        return value

    @property
    def extraction_confidence(self) -> float:
        """Compatibility alias for prior callers; not used as a UI label."""

        return self.semantic_mapping_confidence


class ReviewQueueItem(BaseModel):
    candidate_id: str
    candidate: ExtractedTradeDocument
    status: Literal[
        "pending", "approved", "rejected", "invalid", "possible_duplicate"
    ]
    canonical_transaction_fingerprint: str
    canonical_fingerprint_fields: list[str]
    upload_file_fingerprint: str
    upload_fingerprint_fields: list[str]
    upload_content_sha256: str
    near_duplicate_key: str
    near_duplicate_fields: list[str]
    duplicate_category: Literal[
        "exact_same_file",
        "renamed_same_file",
        "same_transaction_different_file",
        "probable_near_duplicate",
    ] | None = None
    duplicate_of: str | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_fingerprint(cls, value):
        if isinstance(value, dict) and "transaction_fingerprint" in value:
            migrated = dict(value)
            migrated.setdefault(
                "canonical_transaction_fingerprint",
                migrated.pop("transaction_fingerprint"),
            )
            migrated.setdefault(
                "canonical_fingerprint_fields",
                migrated.pop("fingerprint_fields", []),
            )
            candidate = migrated.get("candidate", {})
            migrated.setdefault("upload_file_fingerprint", "")
            migrated.setdefault("upload_fingerprint_fields", [])
            migrated.setdefault(
                "upload_content_sha256",
                candidate.get("upload_content_sha256", "")
                if isinstance(candidate, dict)
                else candidate.upload_content_sha256 or "",
            )
            migrated.setdefault("near_duplicate_key", "")
            migrated.setdefault("near_duplicate_fields", [])
            return migrated
        return value

    @property
    def transaction_fingerprint(self) -> str:
        """Legacy read-only alias for prior session payloads."""
        return self.canonical_transaction_fingerprint

    @property
    def fingerprint_fields(self) -> list[str]:
        """Legacy read-only alias for prior session payloads."""
        return self.canonical_fingerprint_fields


class UploadedDocument(BaseModel):
    """In-memory uploaded document; content is not persisted automatically."""

    filename: str
    content: bytes
    media_type: str | None = None
