"""Manual National Tax Service API smoke test with friendly failure handling."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_providers import (  # noqa: E402
    NTSBusinessStatusProvider,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderResponseError,
)
from src.data_providers.nts_business import normalize_business_number  # noqa: E402


def _resolve_business_number(cli_value: str | None) -> str:
    value = cli_value or os.getenv("TEST_BUSINESS_NUMBER") or ""
    if not value:
        value = input("조회할 사업자등록번호 10자리를 입력하세요: ").strip()
    if not value:
        raise ValueError("사업자등록번호가 입력되지 않았습니다.")
    return normalize_business_number(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="국세청 사업자 상태조회 smoke test")
    parser.add_argument("business_number", nargs="?", help="10자리 사업자등록번호")
    args = parser.parse_args()

    try:
        business_number = _resolve_business_number(args.business_number)
        provider = NTSBusinessStatusProvider()
        result = provider.check_status([business_number])
    except ValueError as exc:
        print(f"입력 오류: {exc}")
        return 4
    except ProviderConfigurationError as exc:
        print(f"설정 오류: {exc}")
        return 2
    except ProviderRequestError as exc:
        print("국세청 API 호출 보류: 외부 서버가 요청을 처리하지 못했습니다.")
        print(str(exc))
        print("환경변수와 로컬 코드는 정상일 수 있으므로 나중에 다시 실행하세요.")
        return 3
    except ProviderResponseError as exc:
        print(f"응답 오류: {exc}")
        return 5

    redacted = {
        "provider": result["provider"],
        "operation": result["operation"],
        "retrieved_at": result["retrieved_at"],
        "requested_count": result["requested_count"],
        "results": result["results"],
        "response_hash": result["response_hash"],
        "limitations": result["limitations"],
    }
    print(json.dumps(redacted, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
