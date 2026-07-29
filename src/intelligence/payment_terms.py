"""Deterministic normalization of reviewed trade-payment wording.

The normalizer converts already-reviewed payment wording into a narrow canonical
representation. It does not interpret an entire contract autonomously, determine bank
undertakings, or replace legal and trade-finance review.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..trade_finance_domain import PaymentStructure, SourceReference

PaymentInstrument = Literal[
    "advance_payment",
    "open_account",
    "documentary_collection_dp",
    "documentary_collection_da",
    "letter_of_credit",
    "standby_letter_of_credit",
    "other",
]
AvailabilityType = Literal[
    "sight",
    "deferred_payment",
    "acceptance",
    "negotiation",
    "usance",
    "unknown",
]
TenorStartEvent = Literal[
    "shipment_date",
    "bill_of_lading_date",
    "invoice_date",
    "document_presentation",
    "sight",
    "acceptance",
    "fixed_maturity_date",
    "other",
    "unknown",
]


class NormalizedPaymentTerms(BaseModel):
    """Canonical payment terms extracted from one reviewed wording fragment."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    instrument: PaymentInstrument
    availability_type: AvailabilityType
    tenor_days: int | None = Field(default=None, ge=0)
    tenor_start_event: TenorStartEvent = "unknown"
    draft_required: bool | None = None
    draft_tenor_text: str | None = None
    acceptance_party: str | None = None
    normalized_trigger: str | None = None
    reviewed_text: str
    matched_patterns: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    authority_boundary: str = (
        "Deterministic normalization of reviewed wording only; not a bank, legal, "
        "document-compliance, or payment-availability decision."
    )

    @model_validator(mode="after")
    def timing_contract_is_consistent(self):
        deferred = self.availability_type in {
            "usance",
            "deferred_payment",
            "acceptance",
        }
        if self.availability_type == "sight" and self.tenor_days not in {None, 0}:
            raise ValueError("Sight terms cannot carry a positive tenor_days value")
        if deferred and self.tenor_days is None and "tenor_days" not in " ".join(
            self.unresolved_fields
        ):
            raise ValueError("Deferred or acceptance terms must preserve missing tenor_days")
        if self.draft_required is False and self.draft_tenor_text:
            raise ValueError("draft_tenor_text cannot be set when draft_required is false")
        return self

    def to_payment_structure(
        self,
        *,
        payment_structure_id: str,
        transaction_id: str,
        source: SourceReference,
        deferred_payment_percent: int | None = None,
    ) -> PaymentStructure:
        """Build the existing governed payment structure without inventing extra facts."""

        return PaymentStructure(
            payment_structure_id=payment_structure_id,
            transaction_id=transaction_id,
            method=self.instrument,
            tenor_days=self.tenor_days,
            deferred_payment_percent=deferred_payment_percent,
            payment_trigger=self.normalized_trigger,
            source=source,
            record_status="partial" if self.unresolved_fields else "verified",
            limitations=[self.authority_boundary, *self.unresolved_fields],
        )

    def reviewed_fields(self) -> dict[str, object]:
        """Return L/C rule inputs that can be merged into reviewed document fields."""

        return {
            "availability_type": self.availability_type,
            "tenor_days": self.tenor_days,
            "tenor_start_event": self.tenor_start_event,
            "draft_required": self.draft_required,
            "draft_tenor_text": self.draft_tenor_text,
            "acceptance_party": self.acceptance_party,
            "payment_terms_reviewed_text": self.reviewed_text,
        }


_INSTRUMENT_PATTERNS: list[tuple[PaymentInstrument, tuple[str, ...]]] = [
    (
        "standby_letter_of_credit",
        (r"\bstandby\s+(?:letter\s+of\s+credit|l/?c)\b", r"\bsblc\b"),
    ),
    (
        "documentary_collection_dp",
        (
            r"\bd\s*/\s*p\b",
            r"documents?\s+against\s+payment",
            r"cash\s+against\s+documents?",
        ),
    ),
    (
        "documentary_collection_da",
        (r"\bd\s*/\s*a\b", r"documents?\s+against\s+acceptance"),
    ),
    (
        "letter_of_credit",
        (r"\bl\s*/\s*c\b", r"letter\s+of\s+credit", r"documentary\s+credit"),
    ),
    ("open_account", (r"\bo\s*/\s*a\b", r"open\s+account")),
    (
        "advance_payment",
        (r"advance\s+payment", r"payment\s+in\s+advance", r"cash\s+in\s+advance"),
    ),
]

_START_EVENT_PATTERNS: list[tuple[TenorStartEvent, tuple[str, ...]]] = [
    (
        "bill_of_lading_date",
        (r"b\s*/\s*l(?:\s+date)?", r"bill\s+of\s+lading(?:\s+date)?"),
    ),
    ("shipment_date", (r"shipment(?:\s+date)?", r"date\s+of\s+shipment")),
    ("invoice_date", (r"invoice(?:\s+date)?",)),
    (
        "document_presentation",
        (r"presentation(?:\s+date)?", r"documents?\s+presented"),
    ),
    ("acceptance", (r"acceptance(?:\s+date)?",)),
    ("sight", (r"after\s+sight", r"from\s+sight")),
]

_DEFERRED_AVAILABILITY = {"usance", "deferred_payment", "acceptance"}
_SIMPLE_TENOR_CONTEXT_PATTERNS = (
    r"(?:\busance\b|deferred\s+payment|available\s+by\s+acceptance|"
    r"\btenor\b|\bmaturity\b|\bpayable\b|\bdraft\b)"
    r"[^.;,\n]{0,80}?(?P<days>\d{1,4})\s*(?:calendar\s+)?days?",
    r"(?P<days>\d{1,4})\s*(?:calendar\s+)?days?"
    r"[^.;,\n]{0,40}?(?:\busance\b|deferred\s+payment|\btenor\b|"
    r"\bmaturity\b|\bpayable\b|\bdraft\b)",
)


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().replace("–", "-").replace("—", "-").split())


def _first_match(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return pattern
    return None


def _instrument(text: str) -> tuple[PaymentInstrument, list[str]]:
    for instrument, patterns in _INSTRUMENT_PATTERNS:
        matched = _first_match(text, patterns)
        if matched:
            return instrument, [f"instrument:{matched}"]
    return "other", []


def _availability(
    text: str, instrument: PaymentInstrument
) -> tuple[AvailabilityType, list[str]]:
    if instrument == "documentary_collection_da":
        return "acceptance", ["availability:derived_from_documentary_collection_da"]

    # Explicit documentary-credit availability wording takes precedence over a generic
    # day-count phrase. This prevents "available by acceptance at 90 days after B/L"
    # from being downgraded to generic usance and losing acceptance-specific controls.
    patterns: list[tuple[AvailabilityType, tuple[str, ...]]] = [
        ("deferred_payment", (r"deferred\s+payment",)),
        ("negotiation", (r"available\s+by\s+negotiation", r"negotiation")),
        ("acceptance", (r"available\s+by\s+acceptance", r"\bacceptance\b")),
        ("sight", (r"at\s+sight", r"sight\s+payment", r"available\s+by\s+payment")),
        (
            "usance",
            (r"\busance\b", r"\d+\s*(?:calendar\s+)?days?\s+(?:after|from)\b"),
        ),
    ]
    for availability, candidates in patterns:
        matched = _first_match(text, candidates)
        if matched:
            return availability, [f"availability:{matched}"]
    return "unknown", []


def _tenor(
    text: str,
    availability: AvailabilityType,
) -> tuple[int | None, TenorStartEvent, str | None, list[str]]:
    # A day count in a sight clause usually describes document presentation, expiry,
    # notice, or another operational period. It must not become payment tenor merely
    # because it appears in the same reviewed fragment.
    if availability == "sight":
        return None, "unknown", None, []

    match = re.search(
        r"(?P<days>\d{1,4})\s*(?:calendar\s+)?days?\s*(?:after|from)\s+"
        r"(?P<anchor>b\s*/\s*l(?:\s+date)?|bill\s+of\s+lading(?:\s+date)?|"
        r"shipment(?:\s+date)?|date\s+of\s+shipment|invoice(?:\s+date)?|"
        r"presentation(?:\s+date)?|documents?\s+presented|acceptance(?:\s+date)?|sight)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        anchor = match.group("anchor")
        event: TenorStartEvent = "unknown"
        for candidate, patterns in _START_EVENT_PATTERNS:
            if _first_match(anchor, patterns):
                event = candidate
                break
        return int(match.group("days")), event, match.group(0), [f"tenor:{match.group(0)}"]

    if availability not in _DEFERRED_AVAILABILITY:
        return None, "unknown", None, []

    # An unanchored day count is retained only when it occurs in an explicit deferred
    # payment context. This preserves "deferred payment 60 days" as partial while
    # rejecting unrelated periods such as "documents within 21 days".
    for pattern in _SIMPLE_TENOR_CONTEXT_PATTERNS:
        simple = re.search(pattern, text, flags=re.IGNORECASE)
        if simple:
            matched_text = simple.group(0)
            return (
                int(simple.group("days")),
                "unknown",
                matched_text,
                ["tenor:days_without_start_event"],
            )
    return None, "unknown", None, []


def _acceptance_party(text: str) -> str | None:
    match = re.search(
        r"(?:accepted|acceptance)\s+by\s+(?P<party>[a-z0-9&.,()'\-/ ]{2,80})",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    party = re.split(r"[;\n]", match.group("party"))[0].strip(" .,;")
    return party or None


def normalize_payment_terms(reviewed_text: str) -> NormalizedPaymentTerms:
    """Normalize one human-reviewed payment wording fragment without inference beyond rules."""

    text = _normalize_text(reviewed_text)
    if not text:
        raise ValueError("reviewed_text must not be empty")

    instrument, matches = _instrument(text)
    availability, availability_matches = _availability(text, instrument)
    tenor_days, start_event, tenor_text, tenor_matches = _tenor(text, availability)
    matches.extend(availability_matches)
    matches.extend(tenor_matches)

    draft_required: bool | None
    if re.search(r"\b(?:draft|bill\s+of\s+exchange)\b", text):
        draft_required = True
        matches.append("draft:explicit")
    elif availability == "acceptance":
        draft_required = True
        matches.append("draft:required_by_acceptance_structure")
    else:
        draft_required = None

    party = _acceptance_party(text)
    if party:
        matches.append("acceptance_party:explicit")

    unresolved: list[str] = []
    if instrument == "other":
        unresolved.append("instrument: no supported payment instrument was identified")
    if availability == "unknown":
        unresolved.append(
            "availability_type: sight, usance, deferred payment, acceptance, or negotiation is not explicit"
        )
    if availability in _DEFERRED_AVAILABILITY:
        if tenor_days is None:
            unresolved.append(
                "tenor_days: deferred or acceptance timing lacks an explicit day count"
            )
        if start_event == "unknown":
            unresolved.append(
                "tenor_start_event: deferred or acceptance timing lacks an explicit start event"
            )
    if availability == "acceptance" and not party:
        unresolved.append(
            "acceptance_party: the party expected to accept the draft is not explicit"
        )
    if draft_required and not tenor_text and availability != "sight":
        unresolved.append("draft_tenor_text: required draft timing is not explicit")

    trigger = None
    if availability == "sight":
        trigger = "at sight"
    elif tenor_days is not None and start_event != "unknown":
        trigger = f"{tenor_days} days after {start_event}"
    elif tenor_text:
        trigger = tenor_text

    return NormalizedPaymentTerms(
        instrument=instrument,
        availability_type=availability,
        tenor_days=tenor_days,
        tenor_start_event=start_event,
        draft_required=draft_required,
        draft_tenor_text=tenor_text if draft_required else None,
        acceptance_party=party,
        normalized_trigger=trigger,
        reviewed_text=reviewed_text,
        matched_patterns=matches,
        unresolved_fields=unresolved,
    )
