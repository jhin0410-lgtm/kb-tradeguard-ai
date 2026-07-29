"""Small standard-library HTTP helpers for public-data providers."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import ProviderRequestError, ProviderResponseError

RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
GetTransport = Callable[[str, dict[str, str], float], bytes]
Sleeper = Callable[[float], None]


class RetryableProviderRequestError(ProviderRequestError):
    """Request error carrying whether another attempt is appropriate."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = bool(retryable)


def default_get_transport(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = Request(url=url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RetryableProviderRequestError(
            f"request failed with HTTP {exc.code}: {detail[:300]}",
            retryable=exc.code in RETRYABLE_HTTP_CODES,
        ) from exc
    except URLError as exc:
        raise RetryableProviderRequestError(
            f"request failed: {exc.reason}", retryable=True
        ) from exc


def get_json_with_retry(
    url: str,
    *,
    timeout: float = 15.0,
    max_attempts: int = 3,
    backoff_seconds: float = 0.75,
    transport: GetTransport | None = None,
    sleep: Sleeper | None = None,
) -> Any:
    """GET and decode JSON with bounded exponential backoff."""

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds must be non-negative")

    transport = transport or default_get_transport
    sleep = sleep or time.sleep
    raw: bytes | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            raw = transport(url, {"Accept": "application/json"}, timeout)
            break
        except RetryableProviderRequestError as exc:
            if not exc.retryable or attempt >= max_attempts:
                raise
            sleep(backoff_seconds * (2 ** (attempt - 1)))

    if raw is None:
        raise ProviderRequestError("request did not produce a response")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderResponseError("provider returned invalid JSON") from exc
