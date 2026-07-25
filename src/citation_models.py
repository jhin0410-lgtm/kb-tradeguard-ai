"""Structured citations for deterministic calculations and policy guidance."""

from __future__ import annotations

from pydantic import BaseModel


class CalculationCitation(BaseModel):
    calculation_id: str
    calculation_name: str

    def format(self) -> str:
        return f"[{self.calculation_id}, {self.calculation_name}]"


class DocumentCitation(BaseModel):
    document_id: str
    title: str
    excerpt_id: str
    issuing_organization: str
    publication_date: str | None = None
    retrieval_date: str
    source_url: str
    stale_warning: str | None = None
    content_origin: str = "project_authored_summary"
    official_issuer: str | None = None
    official_source_url: str | None = None
    summary_last_reviewed: str | None = None
    effective_date_verified: bool = False

    def format(self) -> str:
        return f"[{self.document_id}, {self.title}, {self.excerpt_id}]"
