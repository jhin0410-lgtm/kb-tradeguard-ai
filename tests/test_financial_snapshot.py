from datetime import date
from decimal import Decimal

import pytest

from src.intelligence.financial_snapshot import build_financial_statement_snapshot


def _payload(rows=None, **updates):
    payload = {
        "provider": "Financial Supervisory Service OpenDART API",
        "operation": "financial_statements",
        "source_url": "https://opendart.fss.or.kr/guide/main.do",
        "retrieved_at": "2026-07-26T10:00:00+00:00",
        "corp_code": "00126380",
        "business_year": "2025",
        "report_code": "11011",
        "fs_div": "CFS",
        "results": rows
        or [
            {
                "account_id": "ifrs-full_CashAndCashEquivalents",
                "account_nm": "현금및현금성자산",
                "thstrm_amount": "300,000,000",
            },
            {
                "account_id": "ifrs-full_OtherCurrentFinancialAssets",
                "account_nm": "기타유동금융자산",
                "thstrm_amount": "100,000,000",
            },
            {
                "account_id": "ifrs-full_TradeAndOtherCurrentReceivables",
                "account_nm": "매출채권및기타유동채권",
                "thstrm_amount": "250,000,000",
            },
            {
                "account_id": "ifrs-full_Inventories",
                "account_nm": "재고자산",
                "thstrm_amount": "200,000,000",
            },
            {
                "account_id": "ifrs-full_CurrentAssets",
                "account_nm": "유동자산",
                "thstrm_amount": "1,000,000,000",
            },
            {
                "account_id": "ifrs-full_CurrentLiabilities",
                "account_nm": "유동부채",
                "thstrm_amount": "600,000,000",
            },
            {
                "account_id": "dart_ShortTermBorrowings",
                "account_nm": "단기차입금",
                "thstrm_amount": "150,000,000",
            },
            {
                "account_id": "ifrs-full_Liabilities",
                "account_nm": "부채총계",
                "thstrm_amount": "1,500,000,000",
            },
            {
                "account_id": "ifrs-full_Assets",
                "account_nm": "자산총계",
                "thstrm_amount": "2,000,000,000",
            },
            {
                "account_id": "ifrs-full_Equity",
                "account_nm": "자본총계",
                "thstrm_amount": "500,000,000",
            },
            {
                "account_id": "ifrs-full_Revenue",
                "account_nm": "매출액",
                "thstrm_amount": "5,000,000,000",
            },
            {
                "account_id": "dart_OperatingIncomeLoss",
                "account_nm": "영업이익",
                "thstrm_amount": "250,000,000",
            },
            {
                "account_id": "ifrs-full_CashFlowsFromUsedInOperatingActivities",
                "account_nm": "영업활동으로 인한 현금흐름",
                "thstrm_amount": "180,000,000",
            },
            {
                "account_id": "ifrs-full_FinanceCosts",
                "account_nm": "금융원가",
                "thstrm_amount": "40,000,000",
            },
        ],
        "response_hash": "a" * 64,
        "limitations": "Issuer-filed public statements require normalization.",
    }
    payload.update(updates)
    return payload


def test_builds_typed_annual_consolidated_snapshot_with_provenance():
    snapshot = build_financial_statement_snapshot(
        _payload(), company_id="COMPANY-001", statement_id="FS-2025-CFS"
    )

    assert snapshot.statement_id == "FS-2025-CFS"
    assert snapshot.company_id == "COMPANY-001"
    assert snapshot.report_type == "annual"
    assert snapshot.consolidation_scope == "consolidated"
    assert snapshot.period_start == date(2025, 1, 1)
    assert snapshot.period_end == date(2025, 12, 31)
    assert snapshot.cash_and_cash_equivalents == Decimal("300000000.0")
    assert snapshot.short_term_financial_assets == Decimal("100000000.0")
    assert snapshot.current_assets == Decimal("1000000000.0")
    assert snapshot.equity == Decimal("500000000.0")
    assert snapshot.revenue == Decimal("5000000000.0")
    assert snapshot.source.source_kind == "official_api"
    assert snapshot.source.content_hash == "a" * 64
    assert snapshot.record_status == "verified"
    assert snapshot.original_account_names["cash_and_cash_equivalents"] == (
        "현금및현금성자산"
    )


def test_exact_account_id_has_priority_over_name_only_match():
    rows = [
        {
            "account_id": "custom_cash",
            "account_nm": "현금및현금성자산",
            "thstrm_amount": "999",
        },
        {
            "account_id": "ifrs-full_CashAndCashEquivalents",
            "account_nm": "Issuer specific cash label",
            "thstrm_amount": "123",
        },
        *[row for row in _payload()["results"] if row["account_nm"] != "현금및현금성자산"],
    ]
    snapshot = build_financial_statement_snapshot(
        _payload(rows=rows), company_id="COMPANY-001"
    )

    assert snapshot.cash_and_cash_equivalents == Decimal("123.0")
    assert snapshot.original_account_names["cash_and_cash_equivalents"] == (
        "Issuer specific cash label"
    )


def test_missing_core_accounts_produces_partial_snapshot_without_imputation():
    rows = [
        {
            "account_id": "ifrs-full_CashAndCashEquivalents",
            "account_nm": "현금및현금성자산",
            "thstrm_amount": "300000000",
        }
    ]
    snapshot = build_financial_statement_snapshot(
        _payload(rows=rows), company_id="COMPANY-001"
    )

    assert snapshot.record_status == "partial"
    assert snapshot.current_assets is None
    assert snapshot.revenue is None
    assert any("Missing core normalized accounts" in item for item in snapshot.limitations)


def test_period_override_prevents_non_calendar_inference():
    snapshot = build_financial_statement_snapshot(
        _payload(report_code="11012"),
        company_id="COMPANY-001",
        period_start=date(2024, 7, 1),
        period_end=date(2024, 12, 31),
    )

    assert snapshot.report_type == "semiannual"
    assert snapshot.period_start == date(2024, 7, 1)
    assert snapshot.period_end == date(2024, 12, 31)
    assert not any("period dates were inferred" in item for item in snapshot.limitations)


def test_empty_or_wrong_provider_payload_is_rejected():
    with pytest.raises(ValueError, match="operation"):
        build_financial_statement_snapshot(
            {**_payload(), "operation": "company_profile"}, company_id="COMPANY-001"
        )
    with pytest.raises(ValueError, match="no statement rows"):
        build_financial_statement_snapshot(
            _payload(rows=[], results=[]), company_id="COMPANY-001"
        )


def test_non_numeric_reported_amount_is_not_silently_replaced():
    rows = [
        {
            "account_id": "ifrs-full_Assets",
            "account_nm": "자산총계",
            "thstrm_amount": "not-a-number",
        }
    ]
    with pytest.raises(ValueError, match="not numeric"):
        build_financial_statement_snapshot(
            _payload(rows=rows), company_id="COMPANY-001"
        )
