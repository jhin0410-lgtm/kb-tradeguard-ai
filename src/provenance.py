"""Session-level audit trail with explicit JSON export."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


class AuditTrail:
    """In-memory events only; documents are not persisted by this class."""

    def __init__(self, events: list[dict[str, Any]] | None = None):
        self.events = events if events is not None else []

    def record(self, event_type: str, **details: Any) -> dict[str, Any]:
        event = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        self.events.append(event)
        return event

    def export_json(self, assumptions: dict[str, Any] | None = None) -> str:
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "privacy_notice": (
                "Session audit metadata only; uploaded document bytes are not included."
            ),
            "calculation_assumptions": assumptions or {},
            "events": self.events,
        }
        return json.dumps(report, ensure_ascii=False, indent=2, default=_json_default)
