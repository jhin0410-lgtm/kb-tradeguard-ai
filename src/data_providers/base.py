"""Shared errors and metadata helpers for external data providers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


class ProviderError(RuntimeError):
    """Base exception for external data-provider failures."""


class ProviderConfigurationError(ProviderError):
    """Raised when required local provider configuration is unavailable."""


class ProviderRequestError(ProviderError):
    """Raised when an external provider request cannot be completed."""


class ProviderResponseError(ProviderError):
    """Raised when a provider returns an invalid or unexpected response."""


def utc_now_iso() -> str:
    """Return a stable UTC retrieval timestamp."""

    return datetime.now(timezone.utc).isoformat()


def canonical_json_sha256(value: Any) -> str:
    """Hash JSON-compatible data using deterministic serialization."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
