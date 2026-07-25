"""Multi-year financial trend screening built on OpenDART statement snapshots.

The output is an internal review aid. It does not create an official credit
rating, default probability, lending decision, or product suitability result.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .financial_health import analyze_financial_health


@dataclass(frozen=True)
class FinancialTrendResult:
    """Structured multi-year metrics, changes, flags, and provenance."""

    annual_metrics: pd.DataFrame
    annual_accounts: pd.DataFrame
    year_summary: pd.DataFrame
    changes: pd.DataFrame
    flags: pd.DataFrame
    years: tuple[str, ...]
    latest_year: str
    latest_screening_band: str
    trend_screening_band: str
    overall_coverage_ratio: float
    limitations: tuple[str, ...]


_TREND_ACCOUNT_KEYS = (
    "assets",
    "current_assets",
    "liabilities",
    "current_liabilities",
    "equity",
    "revenue",
    "operating_profit",
    "net_income",
    "interest_expense",
    "operating_cash_flow",
)


def _normalize_year(value: Any) -> str:
    text = str(value).strip()
    if len(text) != 4 or not text.isdigit():
        raise ValueError(f"financial trend year must contain four digits: {value}")
    return text


def _clean_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if not math.isfinite(number) else number


def _normalize_snapshot(year: str, value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return {"business_year": year, "results": value}
    if not isinstance(value, Mapping):
        raise TypeError("each financial trend snapshot must be a mapping or result list")
    snapshot = dict(value)
    stated_year = snapshot.get("business_year")
    if stated_year is not None and _normalize_year(stated_year) != year:
        raise ValueError(
            f"snapshot business_year {stated_year} does not match mapping year {year}"
        )
    rows = snapshot.get("results")
    if not isinstance(rows, list):
        raise ValueError(f"OpenDART snapshot for {year} is missing a results list")
    snapshot["business_year"] = year
    return snapshot


def _validate_consistent_scope(snapshots: list[dict[str, Any]]) -> None:
    labels = {
        "corp_code": "corporation code",
        "report_code": "report type",
        "fs_div": "financial-statement scope",
    }
    for field, label in labels.items():
        values = {
            str(snapshot.get(field)).strip()
            for snapshot in snapshots
            if snapshot.get(field) not in {None, ""}
        }
        if len(values) > 1:
            raise ValueError(f"multi-year comparison requires one consistent {label}")


def _build_changes(
    annual_metrics: pd.DataFrame, annual_accounts: pd.DataFrame
) -> pd.DataFrame:
    metric_series = annual_metrics[
        ["year", "metric", "value", "unit"]
    ].rename(columns={"metric": "series"})
    metric_series["source"] = "metric"

    account_series = annual_accounts[
        annual_accounts["account_key"].isin(_TREND_ACCOUNT_KEYS)
    ][["year", "account_key", "value"]].rename(
        columns={"account_key": "series"}
    )
    account_series["unit"] = "KRW"
    account_series["source"] = "account"

    combined = pd.concat(
        [metric_series, account_series], ignore_index=True, sort=False
    )
    rows: list[dict[str, Any]] = []
    for (source, series), group in combined.groupby(["source", "series"], sort=True):
        ordered = group.sort_values("year")
        previous_year: str | None = None
        previous_value: float | None = None
        for row in ordered.itertuples(index=False):
            value = _clean_number(row.value)
            current_year = str(row.year)
            if previous_year is not None:
                year_gap = int(current_year) - int(previous_year)
                absolute_change = (
                    value - previous_value
                    if value is not None and previous_value is not None
                    else None
                )
                if value is None or previous_value is None:
                    change_pct = None
                    change_basis = "missing_value"
                elif previous_value == 0:
                    change_pct = None
                    change_basis = "zero_base_not_comparable"
                else:
                    change_pct = (value - previous_value) / abs(previous_value) * 100.0
                    change_basis = "year_over_year" if year_gap == 1 else "multi_year_gap"
                if absolute_change is None:
                    direction = "unknown"
                elif absolute_change > 0:
                    direction = "up"
                elif absolute_change < 0:
                    direction = "down"
                else:
                    direction = "flat"
                rows.append(
                    {
                        "source": source,
                        "series": series,
                        "year": current_year,
                        "previous_year": previous_year,
                        "year_gap": year_gap,
                        "value": value,
                        "previous_value": previous_value,
                        "absolute_change": absolute_change,
                        "change_pct": change_pct,
                        "direction": direction,
                        "change_basis": change_basis,
                        "unit": row.unit,
                    }
                )
            previous_year = current_year
            previous_value = value
    return pd.DataFrame(
        rows,
        columns=[
            "source",
            "series",
            "year",
            "previous_year",
            "year_gap",
            "value",
            "previous_value",
            "absolute_change",
            "change_pct",
            "direction",
            "change_basis",
            "unit",
        ],
    )


def _series_values(
    frame: pd.DataFrame, key_column: str, key: str
) -> list[tuple[int, float]]:
    subset = frame[frame[key_column] == key][["year", "value"]].sort_values("year")
    result: list[tuple[int, float]] = []
    for row in subset.itertuples(index=False):
        value = _clean_number(row.value)
        if value is not None:
            result.append((int(row.year), value))
    return result


def _last_three_consecutive(values: list[tuple[int, float]]) -> list[float] | None:
    if len(values) < 3:
        return None
    last = values[-3:]
    if last[1][0] - last[0][0] != 1 or last[2][0] - last[1][0] != 1:
        return None
    return [item[1] for item in last]


def _build_trend_flags(
    annual_metrics: pd.DataFrame,
    annual_accounts: pd.DataFrame,
    year_summary: pd.DataFrame,
) -> pd.DataFrame:
    flags: list[dict[str, Any]] = []

    def add(
        series: str,
        severity: str,
        message: str,
        latest_value: float | None = None,
    ) -> None:
        flags.append(
            {
                "series": series,
                "severity": severity,
                "latest_value": latest_value,
                "message": message,
            }
        )

    revenue = _last_three_consecutive(
        _series_values(annual_accounts, "account_key", "revenue")
    )
    if revenue and revenue[0] > revenue[1] > revenue[2]:
        add(
            "revenue",
            "review",
            "매출이 최근 3개 연속 사업연도에 걸쳐 감소했습니다.",
            revenue[-1],
        )

    current_ratio = _last_three_consecutive(
        _series_values(annual_metrics, "metric", "current_ratio_pct")
    )
    if current_ratio and current_ratio[0] > current_ratio[1] > current_ratio[2]:
        severity = "high" if current_ratio[-1] < 100 else "review"
        add(
            "current_ratio_pct",
            severity,
            "유동비율이 최근 3개 연속 사업연도에 걸쳐 하락했습니다.",
            current_ratio[-1],
        )

    debt_ratio = _last_three_consecutive(
        _series_values(annual_metrics, "metric", "debt_ratio_pct")
    )
    if debt_ratio and debt_ratio[0] < debt_ratio[1] < debt_ratio[2]:
        severity = "high" if debt_ratio[-1] > 200 else "review"
        add(
            "debt_ratio_pct",
            severity,
            "부채비율이 최근 3개 연속 사업연도에 걸쳐 상승했습니다.",
            debt_ratio[-1],
        )

    operating_margin = _last_three_consecutive(
        _series_values(annual_metrics, "metric", "operating_margin_pct")
    )
    if operating_margin and operating_margin[0] > operating_margin[1] > operating_margin[2]:
        severity = "high" if operating_margin[-1] < 0 else "review"
        add(
            "operating_margin_pct",
            severity,
            "영업이익률이 최근 3개 연속 사업연도에 걸쳐 하락했습니다.",
            operating_margin[-1],
        )

    net_income = _series_values(annual_accounts, "account_key", "net_income")
    if len(net_income) >= 2 and net_income[-2][1] >= 0 > net_income[-1][1]:
        add(
            "net_income",
            "high",
            "최근 사업연도 당기순이익이 전년 흑자에서 적자로 전환했습니다.",
            net_income[-1][1],
        )

    operating_cash_flow = _series_values(
        annual_accounts, "account_key", "operating_cash_flow"
    )
    if operating_cash_flow and operating_cash_flow[-1][1] < 0:
        severity = (
            "high"
            if len(operating_cash_flow) >= 2 and operating_cash_flow[-2][1] < 0
            else "review"
        )
        add(
            "operating_cash_flow",
            severity,
            "최근 사업연도 영업현금흐름이 음수입니다."
            if severity == "review"
            else "영업현금흐름이 최근 2개 사업연도 연속 음수입니다.",
            operating_cash_flow[-1][1],
        )

    missing_years = year_summary[year_summary["result_count"] == 0]["year"].tolist()
    if missing_years:
        add(
            "data_availability",
            "review",
            "재무제표가 없는 사업연도가 있어 추세 비교가 불완전합니다: "
            + ", ".join(missing_years),
        )

    return pd.DataFrame(
        flags,
        columns=["series", "severity", "latest_value", "message"],
    )


def analyze_financial_trends(
    snapshots_by_year: Mapping[Any, Any],
) -> FinancialTrendResult:
    """Compare consistent OpenDART statement snapshots across multiple years."""

    if not isinstance(snapshots_by_year, Mapping):
        raise TypeError("snapshots_by_year must be a mapping")
    if len(snapshots_by_year) < 2:
        raise ValueError("financial trend analysis requires at least two years")

    normalized_pairs = sorted(
        (
            (_normalize_year(year), _normalize_snapshot(_normalize_year(year), snapshot))
            for year, snapshot in snapshots_by_year.items()
        ),
        key=lambda item: item[0],
    )
    years = tuple(year for year, _ in normalized_pairs)
    if len(set(years)) != len(years):
        raise ValueError("financial trend years must be unique")
    snapshots = [snapshot for _, snapshot in normalized_pairs]
    _validate_consistent_scope(snapshots)

    metric_frames: list[pd.DataFrame] = []
    account_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    latest_band = "insufficient_data"

    for year, snapshot in normalized_pairs:
        health = analyze_financial_health(snapshot["results"])
        metrics = health.metrics.copy()
        metrics.insert(0, "year", year)
        metric_frames.append(metrics)

        accounts = health.extracted_accounts.copy()
        accounts.insert(0, "year", year)
        account_frames.append(accounts)

        result_count = len(snapshot["results"])
        summary_rows.append(
            {
                "year": year,
                "screening_band": health.screening_band,
                "data_coverage_ratio": health.data_coverage_ratio,
                "result_count": result_count,
                "corp_code": snapshot.get("corp_code"),
                "report_code": snapshot.get("report_code"),
                "fs_div": snapshot.get("fs_div"),
                "retrieved_at": snapshot.get("retrieved_at"),
                "response_hash": snapshot.get("response_hash"),
            }
        )
        latest_band = health.screening_band

    annual_metrics = pd.concat(metric_frames, ignore_index=True, sort=False)
    annual_accounts = pd.concat(account_frames, ignore_index=True, sort=False)
    year_summary = pd.DataFrame(summary_rows)
    changes = _build_changes(annual_metrics, annual_accounts)
    flags = _build_trend_flags(annual_metrics, annual_accounts, year_summary)

    overall_coverage = float(year_summary["data_coverage_ratio"].mean())
    severity_counts = (
        flags["severity"].value_counts() if not flags.empty else pd.Series(dtype=int)
    )
    if overall_coverage < 0.5:
        trend_band = "insufficient_data"
    elif int(severity_counts.get("high", 0)) > 0:
        trend_band = "high_review_priority"
    elif int(severity_counts.get("review", 0)) > 0:
        trend_band = "review_required"
    else:
        trend_band = "no_major_trend_flag_detected"

    limitations = (
        "내부 다년 추세 스크리닝이며 공식 신용등급·부도확률·대출승인 판단이 아닙니다.",
        "동일 기업·보고서 유형·연결범위의 공시만 비교하며 서로 다른 범위는 비교하지 않습니다.",
        "공시 정정, 회계정책 변경, 사업결합·분할과 일회성 손익은 별도 검토해야 합니다.",
        "전년 값이 0이면 증감률을 계산하지 않고 비교 불가로 표시합니다.",
        "계정 매핑과 데이터 충족률을 함께 확인해야 하며 누락값을 추정하지 않습니다.",
    )
    return FinancialTrendResult(
        annual_metrics=annual_metrics,
        annual_accounts=annual_accounts,
        year_summary=year_summary,
        changes=changes,
        flags=flags,
        years=years,
        latest_year=years[-1],
        latest_screening_band=latest_band,
        trend_screening_band=trend_band,
        overall_coverage_ratio=overall_coverage,
        limitations=limitations,
    )
