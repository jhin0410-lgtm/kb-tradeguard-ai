"""Manual smoke test for ECOS, KEXIM, OpenDART, and NTS providers."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_providers import (  # noqa: E402
    BOKECOSProvider,
    KEXIMFXProvider,
    NTSBusinessStatusProvider,
    OpenDARTProvider,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderResponseError,
)


def _run(name, function):
    try:
        result = function()
    except ProviderConfigurationError as exc:
        return {"provider": name, "status": "not_configured", "detail": str(exc)}
    except ProviderRequestError as exc:
        return {"provider": name, "status": "external_unavailable", "detail": str(exc)}
    except ProviderResponseError as exc:
        return {"provider": name, "status": "provider_response_error", "detail": str(exc)}
    except ValueError as exc:
        return {"provider": name, "status": "input_error", "detail": str(exc)}
    return {
        "provider": name,
        "status": "passed",
        "operation": result.get("operation"),
        "retrieved_at": result.get("retrieved_at"),
        "observation_date": result.get("observation_date"),
        "result_count": len(result.get("results") or []),
        "response_hash": result.get("response_hash"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="한국 공식 데이터 API smoke test")
    parser.add_argument(
        "--dart-corp-code",
        default="00126380",
        help="OpenDART 8자리 고유번호 (기본값은 공개 예시 코드)",
    )
    parser.add_argument(
        "--business-number",
        help="선택: 국세청 조회용 10자리 사업자등록번호",
    )
    parser.add_argument(
        "--as-of-date",
        default=date.today().isoformat(),
        help="수출입은행 기준일 YYYY-MM-DD",
    )
    args = parser.parse_args()

    checks = [
        _run("BOK ECOS", lambda: BOKECOSProvider().get_key_statistics(1, 5)),
        _run(
            "Korea Eximbank FX",
            lambda: KEXIMFXProvider().fetch_latest_rates(args.as_of_date, lookback_days=10),
        ),
        _run(
            "OpenDART",
            lambda: OpenDARTProvider().get_company(args.dart_corp_code),
        ),
    ]
    if args.business_number:
        checks.append(
            _run(
                "National Tax Service",
                lambda: NTSBusinessStatusProvider().check_status([args.business_number]),
            )
        )
    else:
        checks.append(
            {
                "provider": "National Tax Service",
                "status": "skipped",
                "detail": "--business-number was not supplied",
            }
        )

    print(json.dumps({"checks": checks}, ensure_ascii=False, indent=2))
    passed = sum(item["status"] == "passed" for item in checks)
    unavailable = sum(item["status"] == "external_unavailable" for item in checks)
    print(f"\n요약: passed={passed}, external_unavailable={unavailable}, total={len(checks)}")

    hard_failures = {
        "not_configured",
        "provider_response_error",
        "input_error",
    }
    return 1 if any(item["status"] in hard_failures for item in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
