import pytest

from src.intelligence import analyze_financial_health
from src.intelligence.financial_health import parse_dart_amount


def _row(account_id, account_nm, amount, sj_nm="재무상태표"):
    return {
        "account_id": account_id,
        "account_nm": account_nm,
        "thstrm_amount": amount,
        "sj_nm": sj_nm,
    }


def test_parse_dart_amount_supports_commas_parentheses_and_missing():
    assert parse_dart_amount("1,234") == 1234.0
    assert parse_dart_amount("(1,234)") == -1234.0
    assert parse_dart_amount("-") is None
    assert parse_dart_amount(None) is None


def test_parse_dart_amount_rejects_non_numeric_text():
    with pytest.raises(ValueError, match="not numeric"):
        parse_dart_amount("금액없음")


def test_financial_health_calculates_ratios_and_preserves_account_provenance():
    rows = [
        _row("ifrs-full_Assets", "자산총계", "1,000"),
        _row("ifrs-full_CurrentAssets", "유동자산", "400"),
        _row("ifrs-full_Liabilities", "부채총계", "600"),
        _row("ifrs-full_CurrentLiabilities", "유동부채", "200"),
        _row("ifrs-full_Equity", "자본총계", "400"),
        _row("ifrs-full_Revenue", "매출액", "2,000", "손익계산서"),
        _row("dart_OperatingIncomeLoss", "영업이익", "200", "손익계산서"),
        _row("ifrs-full_ProfitLoss", "당기순이익", "120", "손익계산서"),
        _row("ifrs-full_FinanceCosts", "금융원가", "50", "손익계산서"),
        _row(
            "ifrs-full_CashFlowsFromUsedInOperatingActivities",
            "영업활동으로 인한 현금흐름",
            "150",
            "현금흐름표",
        ),
    ]

    result = analyze_financial_health(rows)
    metrics = result.metrics.set_index("metric")["value"]

    assert metrics["current_ratio_pct"] == pytest.approx(200.0)
    assert metrics["debt_ratio_pct"] == pytest.approx(150.0)
    assert metrics["equity_ratio_pct"] == pytest.approx(40.0)
    assert metrics["operating_margin_pct"] == pytest.approx(10.0)
    assert metrics["net_margin_pct"] == pytest.approx(6.0)
    assert metrics["interest_coverage_ratio"] == pytest.approx(4.0)
    assert metrics["operating_cash_flow_krw"] == pytest.approx(150.0)
    assert result.data_coverage_ratio == pytest.approx(1.0)
    assert result.screening_band == "no_major_flag_detected"

    extracted = result.extracted_accounts.set_index("account_key")
    assert extracted.loc["assets", "matched_by"] == "account_id"
    assert extracted.loc["assets", "account_name"] == "자산총계"


def test_account_id_has_priority_over_name_alias():
    rows = [
        _row("custom_Wrong", "자산총계", "999"),
        _row("ifrs-full_Assets", "총자산", "1,000"),
    ]
    result = analyze_financial_health(rows)
    extracted = result.extracted_accounts.set_index("account_key")
    assert extracted.loc["assets", "value"] == pytest.approx(1000.0)
    assert extracted.loc["assets", "matched_by"] == "account_id"


def test_negative_profit_and_weak_liquidity_create_high_review_priority():
    rows = [
        _row("ifrs-full_Assets", "자산총계", "1,000"),
        _row("ifrs-full_CurrentAssets", "유동자산", "80"),
        _row("ifrs-full_Liabilities", "부채총계", "900"),
        _row("ifrs-full_CurrentLiabilities", "유동부채", "200"),
        _row("ifrs-full_Equity", "자본총계", "100"),
        _row("ifrs-full_Revenue", "매출액", "1,000", "손익계산서"),
        _row("dart_OperatingIncomeLoss", "영업이익(손실)", "(100)", "손익계산서"),
        _row("ifrs-full_FinanceCosts", "금융원가", "50", "손익계산서"),
        _row(
            "ifrs-full_CashFlowsFromUsedInOperatingActivities",
            "영업활동현금흐름",
            "(20)",
            "현금흐름표",
        ),
    ]

    result = analyze_financial_health(rows)
    severity = result.flags.set_index("metric")["severity"]

    assert severity["current_ratio_pct"] == "high"
    assert severity["debt_ratio_pct"] == "high"
    assert severity["operating_margin_pct"] == "high"
    assert severity["interest_coverage_ratio"] == "high"
    assert result.screening_band == "high_review_priority"


def test_missing_accounts_are_not_fabricated_and_reduce_coverage():
    rows = [_row("ifrs-full_Assets", "자산총계", "1,000")]
    result = analyze_financial_health(rows)

    assert result.metrics["available"].sum() == 0
    assert result.data_coverage_ratio == 0.0
    assert result.screening_band == "insufficient_data"
    extracted = result.extracted_accounts.set_index("account_key")
    assert extracted.loc["revenue", "value"] is None


def test_zero_denominator_returns_missing_metric_instead_of_infinity():
    rows = [
        _row("ifrs-full_CurrentAssets", "유동자산", "100"),
        _row("ifrs-full_CurrentLiabilities", "유동부채", "0"),
        _row("ifrs-full_Liabilities", "부채총계", "100"),
        _row("ifrs-full_Equity", "자본총계", "0"),
    ]
    result = analyze_financial_health(rows)
    metrics = result.metrics.set_index("metric")
    assert metrics.loc["current_ratio_pct", "available"] == False  # noqa: E712
    assert metrics.loc["debt_ratio_pct", "available"] == False  # noqa: E712


def test_financial_rows_require_current_period_amount_column():
    with pytest.raises(ValueError, match="thstrm_amount"):
        analyze_financial_health([{"account_id": "ifrs-full_Assets"}])
