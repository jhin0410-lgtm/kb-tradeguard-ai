"""Manual no-key smoke test for official country-context sources.

Usage:
    python scripts/country_context_smoke_test.py VN --country-name Vietnam
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_providers import (  # noqa: E402
    ProviderRequestError,
    ProviderResponseError,
    WorldBankCountryProvider,
)
from src.intelligence import (  # noqa: E402
    build_fatf_country_fact,
    build_fatf_country_screening,
    build_world_bank_country_facts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("country_code", help="Two-letter country code, for example VN or US")
    parser.add_argument("--country-name", default=None)
    parser.add_argument("--start-year", type=int, default=date.today().year - 8)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    args = parser.parse_args()

    country_code = args.country_code.upper()
    country_name = args.country_name or country_code
    try:
        payloads = WorldBankCountryProvider().get_reference_macro_indicators(
            country_code,
            start_year=args.start_year,
            end_year=args.end_year,
        )
        facts = build_world_bank_country_facts(payloads)
        fatf_fact = build_fatf_country_fact(
            country_code,
            analysis_as_of_date=date.today(),
        )
        fatf_screening = build_fatf_country_screening(
            country_code,
            country_name,
            analysis_as_of_date=date.today(),
        )
    except (ProviderRequestError, ProviderResponseError, ValueError) as exc:
        print(json.dumps({"status": "provider_error", "error": str(exc)}, ensure_ascii=False))
        return 1

    output = {
        "status": "ok",
        "country_code": country_code,
        "authority_boundary": (
            "Official observations and public-list screening only; no country score, "
            "transaction approval, buyer credit conclusion, or institution-specific AML decision."
        ),
        "world_bank_facts": [item.model_dump(mode="json") for item in facts],
        "fatf_fact": fatf_fact.model_dump(mode="json"),
        "fatf_screening": fatf_screening.model_dump(mode="json"),
        "missing_indicator_payloads": [
            payload["indicator_code"] for payload in payloads if payload["results"] is None
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
