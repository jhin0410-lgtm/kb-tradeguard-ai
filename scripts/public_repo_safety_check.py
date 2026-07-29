"""Run the local public-repository safety report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.public_repo_safety import build_public_repo_safety_report  # noqa: E402


def main() -> int:
    report = build_public_repo_safety_report(ROOT)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "safe" else 1


if __name__ == "__main__":
    raise SystemExit(main())
