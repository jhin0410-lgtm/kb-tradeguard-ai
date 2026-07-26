"""Normalize governed OpenDART statement payloads into typed financial snapshots.

The normalizer preserves account-selection provenance and never imputes a missing
financial value.  It is a public-filing pre-screening layer, not an accounting audit,
credit rating, lending decision, or default model.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from ..trade_finance_domain import FinancialStatementSnapshot, SourceReference
from .financial_health import parse_dart_amount


_ACCOUNT_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "cash_and_cash_equivalents": {
        "ids": ("ifrs-full_CashAndCashEquivalents",),
        "names": ("현금및현금성자산", "현금 및 현금성자산"),
    },
    "short_term_financial_assets": {
        "ids": (
            "ifrs-full_CurrentFinancialAssets",
            "ifrs-full_OtherCurrentFinancialAssets",
        ),
        "names": (
            "단기금융자산",
            "단기금융상품",
            "기타유동금융자산",
            "유동금융자산",
        ),
    },
    "trade_receivables": {
        "ids": (
            "ifrs-full_TradeAndOtherCurrentReceivables",
            "ifrs-full_CurrentTradeReceivables",
        ),
        "names": (
            "매출채권및기타유동채권",
            "매출채권 및 기타유동채권",
            "매출채권",
        ),
    },
    "inventories": {
        "ids": ("ifrs-full_Inventories",),
        "names": ("재고자산",),
    },
    "current_assets": {
        "ids": ("ifrs-full_CurrentAssets",),
        "names": ("유동자산",),
    },
    "current_liabilities": {
        "ids": ("ifrs-full_CurrentLiabilities",),
        "names": ("유동부채",),
    },
    "short_term_borrowings": {
        "ids": (
            "dart_ShortTermBorrowings",
            "ifrs-full_ShorttermBorrowings",
            "ifrs-full_CurrentBorrowings",
        ),
        "names": ("단기차입금", "단기차입부채"),
    },
    "current_portion_of_long_term_debt": {
        "ids": (
            "ifrs-full_CurrentPortionOfLongtermBorrowings",
            "ifrs-full_CurrentPortionOfLongtermDebt",
        ),
        "names": (
            "유동성장기차입금",
            "유동성 장기차입금",
            "유동성장기부채",
            "유동성 장기부채",
        ),
    },
    "total_borrowings": {
        "ids": ("dart_TotalBorrowings", "ifrs-full_Borrowings"),
        "names": ("총차입금", "차입금합계"),
    },
    "total_liabilities": {
        "ids": ("ifrs-full_Liabilities",),
        "names": ("부채총계", "부채"),
    },
    "total_assets": {
        "ids": ("ifrs-full_Assets",),
        "names": ("자산총계", "자산"),
    },
    "equity": {
        "ids": (
            "ifrs-full_Equity",
            "ifrs-full_EquityAttributableToOwnersOfParent",
        ),
        "names": ("자본총계", "자본"),
    },
    "revenue": {
        "ids": ("ifrs-full_Revenue",),
        "names": ("매출액", "영업수익", "수익(매출액)"),
    },
    "operating_profit": {
        "ids": (
            "dart_OperatingIncomeLoss",
            "ifrs-full_ProfitLossFromOperatingActivities",
        ),
        "names": ("영업이익", "영업이익(손실)", "영업손익"),
    },
    "operating_cash_flow": {
        "ids": ("ifrs-full_CashFlowsFromUsedInOperatingActivities",),
        "names": (
            "영업활동으로인한현금흐름",
            "영업활동으로 인한 현금흐름",
            "영업활동현금흐름",
            "영업활동으로부터의순현금흐름",
        ),
    },
    "interest_expense": {
        "ids": ("ifrs-full_FinanceCosts",),
        "names": ("금융원가", "이자비용"),
    },
}

_REPORT_TYPES = {
    "11013": "quarterly",
    "11012": "semiannual",
    "11014": "quarterly",
    "11011": "annual",
}
_REPORT_END_MONTH_DAY = {
    "11013": (3, 31),
    "11012": (6, 30),
    "11014": (9, 30),
    "11011": (12, 31),
}


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def _parse_retrieved_at(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _extract_account(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    aliases = _ACCOUNT_ALIASES[key]
    normalized_ids = [_normalize_text(item) for item in aliases["ids"]]
    normalized_names = [_normalize_text(item) for item in aliases["names"]]
    candidates: list[tuple[int, int, int, dict[str, Any], str]] = []

    for row_order, row in enumerate(rows):
        account_id = _normalize_text(row.get("account_id"))
        account_name = _normalize_text(row.get("account_nm"))
        amount = parse_dart_amount(row.get("thstrm_amount"))
        if amount is None:
            continue
        for priority, alias in enumerate(normalized_ids):
            if account_id == alias:
                candidates.append((0, priority, row_order, row, "account_id"))
        for priority, alias in enumerate(normalized_names):
            if account_name == alias:
                candidates.append((1, priority, row_order, row, "account_name"))

    if not candidates:
        return {
            "value": None,
            "account_name": None,
            "account_id": None,
            "matched_by": None,
        }
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    _, _, _, row, matched_by = candidates[0]
    return {
        "value": Decimal(str(parse_dart_amount(row.get("thstrm_amount")))),
        "account_name": row.get("account_nm"),
        "account_id": row.get("account_id"),
        "matched_by": matched_by,
    }


def _resolve_period(
    business_year: str,
    report_code: str,
    period_start: date | None,
    period_end: date | None,
) -> tuple[date, date, bool]:
    year = int(business_year)
    inferred = False
    if period_start is None:
        period_start = date(year, 1, 1)
        inferred = True
    if period_end is None:
        month, day = _REPORT_END_MONTH_DAY[report_code]
        period_end = date(year, month, day)
        inferred = True
    if period_start > period_end:
        raise ValueError("period_start must not be after period_end")
    return period_start, period_end, inferred


def build_financial_statement_snapshot(
    provider_payload: dict[str, Any],
    *,
    company_id: str,
    statement_id: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> FinancialStatementSnapshot:
    """Convert one governed OpenDART provider payload into a typed snapshot."""

    if provider_payload.get("operation") != "financial_statements":
        raise ValueError("OpenDART payload operation must be financial_statements")
    rows = provider_payload.get("results")
    if not isinstance(rows, list):
        raise ValueError("OpenDART financial statement results must be a list")
    if not rows:
        raise ValueError("OpenDART financial statement payload contains no statement rows")

    business_year = str(provider_payload.get("business_year") or "")
    report_code = str(provider_payload.get("report_code") or "")
    fs_div = str(provider_payload.get("fs_div") or "").upper()
    if len(business_year) != 4 or not business_year.isdigit():
        raise ValueError("OpenDART payload business_year must contain four digits")
    if report_code not in _REPORT_TYPES:
        raise ValueError("OpenDART payload contains an unsupported report_code")
    if fs_div not in {"CFS", "OFS"}:
        raise ValueError("OpenDART payload fs_div must be CFS or OFS")

    resolved_start, resolved_end, period_inferred = _resolve_period(
        business_year,
        report_code,
        period_start,
        period_end,
    )
    extracted = {key: _extract_account(rows, key) for key in _ACCOUNT_ALIASES}
    core_keys = {
        "current_assets",
        "current_liabilities",
        "total_assets",
        "equity",
        "revenue",
    }
    missing_core = sorted(key for key in core_keys if extracted[key]["value"] is None)
    limitations = [
        str(provider_payload.get("limitations") or "Issuer-filed public statement data."),
        "Account selection uses a governed exact-ID and exact-name alias registry; issuer-specific taxonomy and restatements require review.",
        "Missing values are preserved as missing and are not imputed.",
    ]
    if period_inferred:
        limitations.append(
            "Statement period dates were inferred from business year and report code; confirm non-calendar fiscal periods."
        )
    if missing_core:
        limitations.append("Missing core normalized accounts: " + ", ".join(missing_core))

    corp_code = str(provider_payload.get("corp_code") or "unknown")
    source_id = f"OPENDART-FS-{corp_code}-{business_year}-{report_code}-{fs_div}"
    source = SourceReference(
        source_id=source_id,
        source_name=str(
            provider_payload.get("provider")
            or "Financial Supervisory Service OpenDART API"
        ),
        source_tier="tier_1",
        source_kind="official_api",
        source_locator=(
            f"{provider_payload.get('source_url') or 'https://opendart.fss.or.kr/guide/main.do'}"
            f"#corp_code={corp_code}&business_year={business_year}&report_code={report_code}&fs_div={fs_div}"
        ),
        as_of_date=resolved_end,
        retrieved_at=_parse_retrieved_at(provider_payload.get("retrieved_at")),
        content_hash=provider_payload.get("response_hash"),
        effective_date_verified=False,
    )
    original_names = {
        key: str(value["account_name"])
        for key, value in extracted.items()
        if value["account_name"]
    }

    return FinancialStatementSnapshot(
        statement_id=statement_id or source_id,
        company_id=company_id,
        period_start=resolved_start,
        period_end=resolved_end,
        report_type=_REPORT_TYPES[report_code],
        consolidation_scope="consolidated" if fs_div == "CFS" else "separate",
        currency="KRW",
        unit_multiplier=Decimal("1"),
        cash_and_cash_equivalents=extracted["cash_and_cash_equivalents"]["value"],
        short_term_financial_assets=extracted["short_term_financial_assets"]["value"],
        trade_receivables=extracted["trade_receivables"]["value"],
        inventories=extracted["inventories"]["value"],
        current_assets=extracted["current_assets"]["value"],
        current_liabilities=extracted["current_liabilities"]["value"],
        short_term_borrowings=extracted["short_term_borrowings"]["value"],
        current_portion_of_long_term_debt=extracted[
            "current_portion_of_long_term_debt"
        ]["value"],
        total_borrowings=extracted["total_borrowings"]["value"],
        total_liabilities=extracted["total_liabilities"]["value"],
        total_assets=extracted["total_assets"]["value"],
        equity=extracted["equity"]["value"],
        revenue=extracted["revenue"]["value"],
        operating_profit=extracted["operating_profit"]["value"],
        operating_cash_flow=extracted["operating_cash_flow"]["value"],
        interest_expense=extracted["interest_expense"]["value"],
        original_account_names=original_names,
        source=source,
        record_status="partial" if missing_core else "verified",
        limitations=limitations,
    )
