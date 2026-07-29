"""Run sanitized live smoke tests for official-data providers.

The script always requires the no-key World Bank and UN Comtrade paths used by the
three public case studies. Secret-dependent providers are attempted only when their
deployment credentials and, where necessary, reviewed lookup identifiers are present.
No secret value or credential-bearing request URL is written to the report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.official_case_studies import (  # noqa: E402
    PinnedOfficialContextDataset,
    build_official_context_query,
    load_official_context_query_manifest,
    pin_official_context_case,
)
from src.official_data_hub import OfficialDataHub  # noqa: E402


def _configured_inputs() -> dict[str, bool]:
    data_go = bool(os.getenv("DATA_GO_KR_SERVICE_KEY"))
    return {
        "kexim_fx_reference": bool(os.getenv("KEXIM_API_KEY")),
        "korea_customs_country_product_trade": bool(
            os.getenv("KCS_TRADE_API_KEY") or data_go
        ),
        "bok_ecos_key_statistics": bool(os.getenv("BOK_ECOS_API_KEY")),
        "opendart_company_profile": bool(
            os.getenv("OPENDART_API_KEY")
            and os.getenv("TRADEGUARD_SMOKE_DART_CORP_CODE")
        ),
        "opendart_financial_statements": bool(
            os.getenv("OPENDART_API_KEY")
            and os.getenv("TRADEGUARD_SMOKE_DART_CORP_CODE")
            and os.getenv("TRADEGUARD_SMOKE_DART_BUSINESS_YEAR")
        ),
        "nts_business_status": bool(
            (os.getenv("NTS_BUSINESS_API_KEY") or data_go)
            and os.getenv("TRADEGUARD_SMOKE_BUSINESS_NUMBER")
        ),
    }


def _safe_snapshot_status(snapshot: Any) -> dict[str, Any]:
    return {
        "asset_key": snapshot.asset_key,
        "provider": snapshot.provider,
        "operation": snapshot.operation,
        "status": snapshot.status,
        "source_url": snapshot.source_url,
        "retrieved_at": (
            snapshot.retrieved_at.isoformat() if snapshot.retrieved_at else None
        ),
        "observation_date": (
            snapshot.observation_date.isoformat() if snapshot.observation_date else None
        ),
        "response_hash": snapshot.response_hash,
        "result_count": _result_count(snapshot.payload),
        "error": snapshot.error,
        "limitations": snapshot.limitations,
    }


def _result_count(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return len(payload) if isinstance(payload, list) else None
    rows = payload.get("results")
    if isinstance(rows, list):
        return len(rows)
    if rows in (None, {}, []):
        return 0
    return 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default=str(ROOT / "data" / "case_studies" / "official_context_queries_v1.json"),
    )
    parser.add_argument(
        "--as-of-date",
        default=date.today().isoformat(),
        help="Live lookup anchor in YYYY-MM-DD format.",
    )
    parser.add_argument("--output-report", required=True)
    parser.add_argument("--output-snapshots", required=True)
    parser.add_argument(
        "--require-configured",
        action="store_true",
        help="Fail when any secret-dependent smoke path is not configured.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    anchor = date.fromisoformat(args.as_of_date)
    manifest = load_official_context_query_manifest(args.manifest)
    hub = OfficialDataHub()
    configured = _configured_inputs()
    generated_at = datetime.now(timezone.utc)

    failures: list[str] = []
    case_runs: list[dict[str, Any]] = []
    pinned_cases = []

    for index, definition in enumerate(manifest.cases):
        query = build_official_context_query(
            definition,
            as_of_date=anchor,
            business_registration_number=(
                os.getenv("TRADEGUARD_SMOKE_BUSINESS_NUMBER") if index == 0 else None
            ),
            dart_corp_code=(
                os.getenv("TRADEGUARD_SMOKE_DART_CORP_CODE") if index == 0 else None
            ),
            dart_business_year=(
                int(os.environ["TRADEGUARD_SMOKE_DART_BUSINESS_YEAR"])
                if index == 0 and os.getenv("TRADEGUARD_SMOKE_DART_BUSINESS_YEAR")
                else None
            ),
        )
        bundle = hub.collect(query)
        statuses = [_safe_snapshot_status(item) for item in bundle.snapshots]
        case_failure: str | None = None
        try:
            pinned = pin_official_context_case(definition, bundle)
            pinned_cases.append(pinned)
        except ValueError as exc:
            case_failure = str(exc)
            failures.append(case_failure)

        for item in bundle.snapshots:
            if configured.get(item.asset_key) and item.status == "error":
                message = (
                    f"Configured provider failed for {definition.case_id}: "
                    f"{item.asset_key}: {item.error}"
                )
                failures.append(message)

        case_runs.append(
            {
                "case_id": definition.case_id,
                "country_code": definition.country_code,
                "hs_code": definition.hs_code,
                "trade_flow_code": definition.trade_flow_code,
                "comtrade_period": definition.comtrade_period,
                "status_counts": bundle.status_counts,
                "snapshot_statuses": statuses,
                "pinning_error": case_failure,
            }
        )

    if args.require_configured:
        missing = sorted(key for key, value in configured.items() if not value)
        if missing:
            failures.append(
                "Secret-dependent smoke paths are not fully configured: " + ", ".join(missing)
            )

    dataset = PinnedOfficialContextDataset(
        dataset_version="official-context-snapshots/1.0",
        generated_at=generated_at,
        authority_boundary=manifest.authority_boundary,
        cases=pinned_cases,
    ) if len(pinned_cases) == len(manifest.cases) else None

    report = {
        "report_version": "official-data-live-smoke/1.0",
        "generated_at": generated_at.isoformat(),
        "as_of_date": anchor.isoformat(),
        "live_network_attempted": True,
        "case_count": len(manifest.cases),
        "pinned_case_count": len(pinned_cases),
        "secret_dependent_paths_configured": configured,
        "case_runs": case_runs,
        "failures": list(dict.fromkeys(failures)),
        "status": "passed" if not failures else "failed",
        "authority_boundary": (
            "A passed smoke test proves only that the selected public endpoints returned "
            "parseable responses at this run time. It does not prove future availability, "
            "data completeness, customer eligibility, credit quality, compliance clearance, "
            "product approval, or executable pricing."
        ),
    }

    report_path = Path(args.output_report)
    snapshot_path = Path(args.output_snapshots)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if dataset is not None:
        snapshot_path.write_text(
            json.dumps(
                dataset.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    elif snapshot_path.exists():
        snapshot_path.unlink()

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
