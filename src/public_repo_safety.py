"""Local public-repository safety checks with no network calls.

The scanner looks for credential-shaped text and tracked paths that should remain
local. It is a release guardrail, not a substitute for provider-side secret
rotation, GitHub secret scanning, or manual review of repository history.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

_EXCLUDED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "venv",
}

_FORBIDDEN_DIRECTORY_PARTS = {
    "artifacts",
    "customer_data",
    "evidence",
    "exports",
    "local_data",
    "outputs",
    "temp",
    "tmp",
    "uploads",
}

_FORBIDDEN_RELATIVE_PREFIXES = {
    "data/cache",
    "data/private",
    "data/raw",
    "data/uploads",
    "reports/generated",
    "screenshots/private",
}

_FORBIDDEN_FILENAMES = {
    ".env",
    "credentials.json",
    "secrets.toml",
}

_FORBIDDEN_SUFFIXES = {
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
}

_SECRET_PATTERNS = {
    "openai_api_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{50,})\b"
    ),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b"),
    "private_key_block": re.compile(
        re.escape("-----BEGIN " + "PRIVATE KEY-----")
        + r"|"
        + re.escape("-----BEGIN RSA " + "PRIVATE KEY-----")
    ),
}

_MAX_TEXT_SCAN_BYTES = 5 * 1024 * 1024
_BINARY_SAMPLE_BYTES = 8192


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_excluded(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return any(part in _EXCLUDED_DIRECTORIES for part in relative_parts)


def _forbidden_path_reason(path: Path, root: Path) -> str | None:
    relative = _relative(path, root)
    parts = set(path.relative_to(root).parts)
    if path.name in _FORBIDDEN_FILENAMES:
        return "credential_or_secret_filename"
    if path.suffix.lower() in _FORBIDDEN_SUFFIXES:
        return "credential_or_certificate_suffix"
    if parts & _FORBIDDEN_DIRECTORY_PARTS:
        return "private_or_generated_directory"
    if any(
        relative == prefix or relative.startswith(prefix + "/")
        for prefix in _FORBIDDEN_RELATIVE_PREFIXES
    ):
        return "private_or_generated_prefix"
    if path.name.startswith("service-account") and path.suffix.lower() == ".json":
        return "service_account_file"
    return None


def _read_text(path: Path) -> str | None:
    """Read every bounded UTF-8-decodable non-binary file regardless of suffix."""

    try:
        if path.stat().st_size > _MAX_TEXT_SCAN_BYTES:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:_BINARY_SAMPLE_BYTES]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def build_public_repo_safety_report(root: str | Path | None = None) -> dict[str, Any]:
    """Return a deterministic report for the current working tree."""

    repository_root = Path(root).resolve() if root is not None else ROOT
    findings: list[dict[str, Any]] = []
    scanned_file_count = 0
    text_scanned_file_count = 0

    for path in sorted(repository_root.rglob("*")):
        if not path.is_file() or _is_excluded(path, repository_root):
            continue
        scanned_file_count += 1
        relative = _relative(path, repository_root)

        path_reason = _forbidden_path_reason(path, repository_root)
        if path_reason is not None:
            findings.append(
                {
                    "path": relative,
                    "kind": "forbidden_path",
                    "reason": path_reason,
                }
            )

        text = _read_text(path)
        if text is None:
            continue
        text_scanned_file_count += 1
        for pattern_name, pattern in _SECRET_PATTERNS.items():
            match = pattern.search(text)
            if match is None:
                continue
            line_number = text.count("\n", 0, match.start()) + 1
            findings.append(
                {
                    "path": relative,
                    "kind": "credential_pattern",
                    "reason": pattern_name,
                    "line": line_number,
                }
            )

    return {
        "report_version": "public-repo-safety/1.1",
        "status": "safe" if not findings else "review_required",
        "network_calls": "none",
        "scanned_file_count": scanned_file_count,
        "text_scanned_file_count": text_scanned_file_count,
        "finding_count": len(findings),
        "findings": findings,
        "limitations": [
            "UTF-8 text-like files larger than 5 MiB and binary or non-UTF-8 files are not content-scanned.",
            "Pattern scanning cannot prove that repository history, forks, caches, Actions logs, or external systems contain no secrets.",
            "Any exposed credential must be revoked or rotated even after the file is removed.",
        ],
    }
