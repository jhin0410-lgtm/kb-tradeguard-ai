"""Deterministic helpers for the public competition demo surface.

These helpers summarize existing governed fixtures and build a QR image for a configured
public URL. They do not call external services or change assessment results.
"""

from __future__ import annotations

from io import BytesIO
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import qrcode
from pydantic import BaseModel, ConfigDict

from .demo_scenarios import list_demo_scenarios
from .intelligence.trade_document_gold import (
    iter_semantic_preserving_gold_mutations,
    list_trade_document_gold_cases,
)
from .intelligence.trade_document_rules import load_trade_document_rule_registry


class CompetitionValidationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    governed_rule_count: int
    gold_case_count: int
    mutation_case_count: int
    demo_scenario_count: int
    authority_boundary: str


def build_competition_validation_status() -> CompetitionValidationStatus:
    """Return compact regression-coverage counts for the public demo footer."""

    gold_cases = list_trade_document_gold_cases()
    mutations = list(iter_semantic_preserving_gold_mutations(gold_cases))
    registry = load_trade_document_rule_registry()
    return CompetitionValidationStatus(
        governed_rule_count=len(registry.rules),
        gold_case_count=len(gold_cases),
        mutation_case_count=len(mutations),
        demo_scenario_count=len(list_demo_scenarios()),
        authority_boundary=(
            "합성 Fixture에 대한 결정론적 회귀검증 현황입니다. 실제 거래의 법률적 "
            "정확성, 금융기관 승인, 보험 인수 또는 상품 적격성을 의미하지 않습니다."
        ),
    )


def normalize_public_demo_url(value: str, *, presentation: bool = False) -> str:
    """Validate an HTTP(S) demo URL and add governed public-demo query parameters."""

    candidate = value.strip()
    if not candidate:
        raise ValueError("Public demo URL is empty")
    parts = urlsplit(candidate)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("Public demo URL must be an absolute HTTP(S) URL")
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["demo"] = "1"
    if presentation:
        query["presentation"] = "1"
    else:
        query.pop("presentation", None)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), ""))


def build_public_demo_qr_png(url: str) -> bytes:
    """Build a local PNG QR code without network calls."""

    normalized = normalize_public_demo_url(url)
    image = qrcode.make(normalized)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
