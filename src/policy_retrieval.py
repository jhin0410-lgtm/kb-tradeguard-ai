"""Deterministic BM25-style retrieval over approved bundled policy summaries."""

from __future__ import annotations

import json
import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .citation_models import DocumentCitation

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+|[가-힣]{2,}")
SECTION_PATTERN = re.compile(r"^\[section:\s*([^\]]+)\]\s*$", re.MULTILINE)


@dataclass(frozen=True)
class PolicyExcerpt:
    document_id: str
    title: str
    excerpt_id: str
    excerpt: str
    score: float
    citation: DocumentCitation
    information_boundary: str = (
        "General information only; customer-specific eligibility and current "
        "product availability require verification with the issuing organization."
    )


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _sections(text: str) -> list[tuple[str, str]]:
    matches = list(SECTION_PATTERN.finditer(text))
    if not matches:
        return [("full-text", text.strip())]
    sections = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[start:end].strip()))
    return sections


class BundledPolicyRetriever:
    """Search only manifest entries explicitly marked approved_reference."""

    def __init__(self, policy_dir: str | Path):
        self.policy_dir = Path(policy_dir)
        manifest = json.loads(
            (self.policy_dir / "manifest.json").read_text(encoding="utf-8")
        )
        self.documents = [
            document
            for document in manifest["documents"]
            if document.get("status") == "approved_reference"
        ]
        self.passages = []
        for document in self.documents:
            local_path = self.policy_dir / document["text_file"]
            content = local_path.read_bytes()
            checksum = hashlib.sha256(content).hexdigest()
            if checksum != document["local_file_checksum"]:
                raise ValueError(
                    f"Policy summary checksum mismatch: {document['document_id']}"
                )
            text = content.decode("utf-8")
            for excerpt_id, excerpt in _sections(text):
                searchable = " ".join(
                    [
                        document["title"],
                        document["official_issuer"],
                        " ".join(document.get("categories", [])),
                        excerpt,
                    ]
                )
                self.passages.append(
                    {
                        "document": document,
                        "excerpt_id": excerpt_id,
                        "excerpt": excerpt,
                        "tokens": _tokenize(searchable),
                    }
                )

    def search(
        self,
        query: str,
        limit: int = 3,
        as_of_date: date | None = None,
    ) -> list[PolicyExcerpt]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        count = len(self.passages)
        average_length = (
            sum(len(passage["tokens"]) for passage in self.passages) / count
            if count
            else 1
        )
        document_frequency = Counter()
        for token in set(query_tokens):
            document_frequency[token] = sum(
                token in set(passage["tokens"]) for passage in self.passages
            )
        scored = []
        for passage in self.passages:
            frequencies = Counter(passage["tokens"])
            score = 0.0
            for token in query_tokens:
                frequency = frequencies[token]
                if not frequency:
                    continue
                inverse_frequency = math.log(
                    1 + (count - document_frequency[token] + 0.5)
                    / (document_frequency[token] + 0.5)
                )
                denominator = frequency + 1.5 * (
                    1 - 0.75
                    + 0.75 * len(passage["tokens"]) / max(average_length, 1)
                )
                score += inverse_frequency * frequency * 2.5 / denominator
            if score > 0:
                scored.append((score, passage))
        scored.sort(
            key=lambda item: (
                -item[0],
                item[1]["document"]["document_id"],
                item[1]["excerpt_id"],
            )
        )
        current = as_of_date or date.today()
        results = []
        for score, passage in scored[:limit]:
            document = passage["document"]
            warnings = []
            if not document.get("official_effective_date"):
                warnings.append("Official effective date is not stated")
            if not document.get("effective_date_verified"):
                warnings.append("Effective date has not been independently verified")
            retrieval = date.fromisoformat(document["source_retrieval_date"])
            if (current - retrieval).days > 365:
                warnings.append("Bundled retrieval is more than 365 days old")
            stale_warning = "; ".join(warnings) or None
            citation = DocumentCitation(
                document_id=document["document_id"],
                title=document["title"],
                excerpt_id=passage["excerpt_id"],
                issuing_organization=document["official_issuer"],
                publication_date=document.get("official_publication_date"),
                retrieval_date=document["source_retrieval_date"],
                source_url=document["official_source_url"],
                stale_warning=stale_warning,
                content_origin=document["content_origin"],
                official_issuer=document["official_issuer"],
                official_source_url=document["official_source_url"],
                summary_last_reviewed=document["summary_last_reviewed"],
                effective_date_verified=document["effective_date_verified"],
            )
            results.append(
                PolicyExcerpt(
                    document_id=document["document_id"],
                    title=document["title"],
                    excerpt_id=passage["excerpt_id"],
                    excerpt=passage["excerpt"],
                    score=score,
                    citation=citation,
                )
            )
        return results
