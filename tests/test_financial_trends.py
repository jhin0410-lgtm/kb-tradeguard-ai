import pandas as pd
import pytest

from src.intelligence import analyze_financial_trends


def _row(account_id, account_nm, amount, sj_nm="재무상태표"):
    return {
        "account_id": account_id,
        "account_nm": account_nm,
        "thstrm_amount": amount,
        "sj_nm": sj_nm,
    }


def _statement(
    *,
    assets,
    current_assets,
    liabilities,
    current_liabilities,
    equity,
    revenue,
    operating_profit,
    net_income,
    finance_costs,
    operating_cash_flow,
):
    return [
        _row("ifrs-full_Assets", "자산총계", assets),
        _row("ifrs-full_CurrentAssets", "유동자산", current_assets),
        _row("ifrs-full_Liabilities", "부채총계", liabilities),
        _row("ifrs-full_CurrentLiabilities", "유동부채", current_liabilities),
        _row("ifrs-full_Equity", "자본총계", equity),
        _row("ifrs-full_Revenue", "매출액", revenue, "손익계산서"),
        _row(
            "dart_OperatingIncomeLoss",
            "영업이익",
            operating_profit,
            "손익계산서",
        ),
        _row("ifrs-full_ProfitLoss", "당기순이익", net_income, "손익계산서"),
        _row("ifrs-full_FinanceCosts", "금융원가", finance_costs, "손익계산서"),
        _row(
            "ifrs-full_CashFlowsFromUsedInOperatingActivities",
            "영업활동현금흐름",
            operating_cash_flow,
            "현금흐름표",
        ),
    ]


def _snapshot(year, rows, **overrides):
    snapshot = {
        "business_year": str(year),
        "corp_code": "00126380",
        "report_code": "11011",
        "fs_div": "CFS",
        "retrieved_at": f"{year}-04-01T00:00:00+00:00",
        "response_hash": str(year) * 16,
        "results": rows,
    }
    snapshot.update(overrides)
    return snapshot


def test_three_year_trend_calculates_changes_and_flags_deterioration():
    snapshots = {
        2023: _snapshot(
            2023,
            _statement(
                assets="1,000",
                current_assets="400",
                liabilities="500",
                current_liabilities="200",
                equity="500",
                revenue="1,000",
                operating_profit="100",
                net_income="80",
                finance_costs="20",
                operating_cash_flow="100",
            ),
        ),
        2024: _snapshot(
            2024,
            _statement(
                assets="1,000",
                current_assets="300",
                liabilities="600",
                current_liabilities="200",
                equity="400",
                revenue="900",
                operating_profit="45",
                net_income="20",
                finance_costs="30",
                operating_cash_flow="(10)",
            ),
        ),
        2025: _snapshot(
            2025,
            _statement(
                assets="1,000",
                current_assets="180",
                liabilities="700",
                current_liabilities="200",
                equity="300",
                revenue="800",
                operating_profit="(40)",
                net_income="(30)",
                finance_costs="40",
                operating_cash_flow="(20)",
            ),
        ),
    }

    result = analyze_financial_trends(snapshots)

    assert result.years == ("2023", "2024", "2025")
    assert result.latest_year == "2025"
    assert result.overall_coverage_ratio == pytest.approx(1.0)
    assert result.trend_screening_band == "high_review_priority"

    revenue_change = result.changes[
        (result.changes["source"] == "account")
        & (result.changes["series"] == "revenue")
        & (result.changes["year"] == "2024")
    ].iloc[0]
    assert revenue_change["change_pct"] == pytest.approx(-10.0)
    assert revenue_change["change_basis"] == "year_over_year"

    flags = result.flags.set_index("series")
    assert flags.loc["revenue", "severity"] == "review"
    assert flags.loc["current_ratio_pct", "severity"] == "high"
    assert flags.loc["debt_ratio_pct", "severity"] == "high"
    assert flags.loc["operating_margin_pct", "severity"] == "high"
    assert flags.loc["net_income", "severity"] == "high"
    assert flags.loc["operating_cash_flow", "severity"] == "high"

    summary = result.year_summary.set_index("year")
    assert summary.loc["2025", "response_hash"] == "2025" * 16
    assert summary.loc["2025", "fs_div"] == "CFS"


def test_zero_base_growth_is_not_fabricated():
    snapshots = {
        2024: _snapshot(
            2024,
            _statement(
                assets="100",
                current_assets="50",
                liabilities="50",
                current_liabilities="25",
                equity="50",
                revenue="0",
                operating_profit="0",
                net_income="0",
                finance_costs="10",
                operating_cash_flow="0",
            ),
        ),
        2025: _snapshot(
            2025,
            _statement(
                assets="120",
                current_assets="60",
                liabilities="60",
                current_liabilities="30",
                equity="60",
                revenue="100",
                operating_profit="10",
                net_income="5",
                finance_costs="10",
                operating_cash_flow="10",
            ),
        ),
    }

    result = analyze_financial_trends(snapshots)
    row = result.changes[
        (result.changes["source"] == "account")
        & (result.changes["series"] == "revenue")
    ].iloc[0]
    assert pd.isna(row["change_pct"])
    assert row["change_basis"] == "zero_base_not_comparable"


def test_missing_year_data_is_preserved_and_flagged():
    snapshots = {
        2024: _snapshot(2024, []),
        2025: _snapshot(
            2025,
            _statement(
                assets="100",
                current_assets="50",
                liabilities="50",
                current_liabilities="25",
                equity="50",
                revenue="100",
                operating_profit="10",
                net_income="5",
                finance_costs="2",
                operating_cash_flow="8",
            ),
        ),
    }

    result = analyze_financial_trends(snapshots)
    flag = result.flags[result.flags["series"] == "data_availability"].iloc[0]
    assert flag["severity"] == "review"
    assert "2024" in flag["message"]
    assert result.year_summary.set_index("year").loc["2024", "result_count"] == 0


def test_inconsistent_statement_scope_is_rejected():
    rows = _statement(
        assets="100",
        current_assets="50",
        liabilities="50",
        current_liabilities="25",
        equity="50",
        revenue="100",
        operating_profit="10",
        net_income="5",
        finance_costs="2",
        operating_cash_flow="8",
    )
    snapshots = {
        2024: _snapshot(2024, rows, fs_div="CFS"),
        2025: _snapshot(2025, rows, fs_div="OFS"),
    }
    with pytest.raises(ValueError, match="financial-statement scope"):
        analyze_financial_trends(snapshots)


def test_snapshot_year_mismatch_is_rejected():
    with pytest.raises(ValueError, match="does not match"):
        analyze_financial_trends(
            {
                2024: _snapshot(2023, []),
                2025: _snapshot(2025, []),
            }
        )


def test_at_least_two_years_are_required():
    with pytest.raises(ValueError, match="at least two years"):
        analyze_financial_trends({2025: _snapshot(2025, [])})
