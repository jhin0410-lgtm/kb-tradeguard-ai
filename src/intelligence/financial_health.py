"""Transparent financial-health screening from OpenDART statement rows.

This module produces review metrics and flags only. It does not create an
official credit rating, lending decision, default probability, or product
suitability determination.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class FinancialHealthResult:
    """Structured financial-health screening with extraction provenance."""

    metrics: pd.DataFrame
    extracted_accounts: pd.DataFrame
    flags: pd.DataFrame
    screening_band: str
    data_coverage_ratio: float
    limitations: tuple[str, ...]


_ACCOUNT_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "assets": {
        "ids": ("ifrs-full_Assets",),
        "names": ("자산총계", "자산"),
    },
    "current_assets": {
        "ids": ("ifrs-full_CurrentAssets",),
        "names": ("유동자산",),
    },
    "liabilities": {
        "ids": ("ifrs-full_Liabilities",),
        "names": ("부채총계", "부채"),
    },
    "current_liabilities": {
        "ids": ("ifrs-full_CurrentLiabilities",),
        "names": ("유동부채",),
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
    "net_income": {
        "ids": ("ifrs-full_ProfitLoss",),
        "names": ("당기순이익", "당기순이익(손실)", "연결당기순이익"),
    },
    "interest_expense": {
        "ids": ("ifrs-full_FinanceCosts",),
        "names": ("금융원가", "이자비용"),
    },
    "operating_cash_flow": {
        "ids": ("ifrs-full_CashFlowsFromUsedInOperatingActivities",),
        "names": (
            "영업활동으로 인한 현금흐름",
            "영업활동현금흐름",
            "영업활동으로부터의 순현금흐름",
        ),
    },
}

_REQUIRED_METRICS = (
    "current_ratio_pct",
    "debt_ratio_pct",
    "equity_ratio_pct",
    "operating_margin_pct",
    "net_margin_pct",
    "interest_coverage_ratio",
    "operating_cash_flow_krw",
)


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def parse_dart_amount(value: Any) -> float | None:
    """Parse OpenDART amount strings without silently replacing invalid values."""

    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text or text in {"-", "--"}:
        return None
    negative_parentheses = text.startswith("(") and text.endswith(")")
    cleaned = text.replace(",", "").replace(" ", "")
    if negative_parentheses:
        cleaned = cleaned[1:-1]
    try:
        amount = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"OpenDART amount is not numeric: {value}") from exc
    return -amount if negative_parentheses else amount


def _prepare_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not isinstance(rows, list):
        raise TypeError("OpenDART financial rows must be a list")
    if not rows:
        return pd.DataFrame()
    if any(not isinstance(row, dict) for row in rows):
        raise TypeError("Every OpenDART financial row must be a mapping")

    frame = pd.DataFrame(rows).copy()
    for column in ("account_id", "account_nm", "sj_div", "sj_nm"):
        if column not in frame.columns:
            frame[column] = None
    if "thstrm_amount" not in frame.columns:
        raise ValueError("OpenDART financial rows are missing thstrm_amount")
    frame["parsed_amount"] = frame["thstrm_amount"].map(parse_dart_amount)
    frame["normalized_account_id"] = frame["account_id"].map(_normalize_text)
    frame["normalized_account_name"] = frame["account_nm"].map(_normalize_text)
    frame["row_order"] = range(len(frame))
    return frame


def _find_account(frame: pd.DataFrame, key: str) -> dict[str, Any]:
    aliases = _ACCOUNT_ALIASES[key]
    if frame.empty:
        return {
            "account_key": key,
            "value": None,
            "matched_by": None,
            "account_id": None,
            "account_name": None,
            "statement_name": None,
            "raw_amount": None,
            "row_order": None,
        }

    id_aliases = [_normalize_text(value) for value in aliases["ids"]]
    name_aliases = [_normalize_text(value) for value in aliases["names"]]

    candidates: list[tuple[int, int, pd.Series, str]] = []
    for _, row in frame.iterrows():
        if row["parsed_amount"] is None or pd.isna(row["parsed_amount"]):
            continue
        normalized_id = row["normalized_account_id"]
        normalized_name = row["normalized_account_name"]
        for priority, alias in enumerate(id_aliases):
            if normalized_id == alias:
                candidates.append((0, priority, row, "account_id"))
        for priority, alias in enumerate(name_aliases):
            if normalized_name == alias:
                candidates.append((1, priority, row, "account_name"))

    if not candidates:
        return {
            "account_key": key,
            "value": None,
            "matched_by": None,
            "account_id": None,
            "account_name": None,
            "statement_name": None,
            "raw_amount": None,
            "row_order": None,
        }

    candidates.sort(key=lambda item: (item[0], item[1], int(item[2]["row_order"])))
    _, _, row, matched_by = candidates[0]
    return {
        "account_key": key,
        "value": float(row["parsed_amount"]),
        "matched_by": matched_by,
        "account_id": row.get("account_id"),
        "account_name": row.get("account_nm"),
        "statement_name": row.get("sj_nm"),
        "raw_amount": row.get("thstrm_amount"),
        "row_order": int(row["row_order"]),
    }


def _safe_ratio(numerator: float | None, denominator: float | None, scale: float = 1.0) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator / denominator * scale)


def _metric_row(
    metric: str,
    value: float | None,
    unit: str,
    formula: str,
    inputs: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "metric": metric,
        "value": value,
        "unit": unit,
        "formula": formula,
        "inputs": ", ".join(inputs),
        "available": value is not None,
    }


def _build_flags(metric_values: dict[str, float | None]) -> pd.DataFrame:
    flags: list[dict[str, str | float | None]] = []

    def add(metric: str, severity: str, message: str) -> None:
        flags.append(
            {
                "metric": metric,
                "value": metric_values.get(metric),
                "severity": severity,
                "message": message,
            }
        )

    current_ratio = metric_values["current_ratio_pct"]
    if current_ratio is not None:
        if current_ratio < 100:
            add("current_ratio_pct", "high", "유동자산이 유동부채보다 적어 단기 지급여력 검토가 필요합니다.")
        elif current_ratio < 150:
            add("current_ratio_pct", "review", "유동비율이 150% 미만이므로 운전자금 여유를 확인해야 합니다.")
        else:
            add("current_ratio_pct", "stable", "유동비율이 내부 스크리닝 기준상 양호한 범위입니다.")

    debt_ratio = metric_values["debt_ratio_pct"]
    if debt_ratio is not None:
        if debt_ratio > 200:
            add("debt_ratio_pct", "high", "부채비율이 200%를 초과해 레버리지 부담 검토가 필요합니다.")
        elif debt_ratio > 100:
            add("debt_ratio_pct", "review", "부채비율이 100%를 초과해 자본구조 확인이 필요합니다.")
        else:
            add("debt_ratio_pct", "stable", "부채비율이 내부 스크리닝 기준상 낮은 범위입니다.")

    equity_ratio = metric_values["equity_ratio_pct"]
    if equity_ratio is not None:
        if equity_ratio < 20:
            add("equity_ratio_pct", "high", "자기자본비율이 20% 미만으로 손실흡수력 검토가 필요합니다.")
        elif equity_ratio < 40:
            add("equity_ratio_pct", "review", "자기자본비율이 40% 미만이므로 재무완충력을 확인해야 합니다.")
        else:
            add("equity_ratio_pct", "stable", "자기자본비율이 내부 스크리닝 기준상 양호한 범위입니다.")

    operating_margin = metric_values["operating_margin_pct"]
    if operating_margin is not None:
        if operating_margin < 0:
            add("operating_margin_pct", "high", "영업손실이 발생해 본업 수익성 검토가 필요합니다.")
        elif operating_margin < 5:
            add("operating_margin_pct", "review", "영업이익률이 5% 미만으로 비용 충격 흡수력이 제한적일 수 있습니다.")
        else:
            add("operating_margin_pct", "stable", "영업이익률이 내부 스크리닝 기준상 양호한 범위입니다.")

    coverage = metric_values["interest_coverage_ratio"]
    if coverage is not None:
        if coverage < 1:
            add("interest_coverage_ratio", "high", "영업이익이 금융원가를 충당하지 못하는 수준입니다.")
        elif coverage < 3:
            add("interest_coverage_ratio", "review", "이자보상 여력이 제한적이므로 차입조건 확인이 필요합니다.")
        else:
            add("interest_coverage_ratio", "stable", "이자보상배율이 내부 스크리닝 기준상 양호한 범위입니다.")

    operating_cash_flow = metric_values["operating_cash_flow_krw"]
    if operating_cash_flow is not None:
        if operating_cash_flow < 0:
            add("operating_cash_flow_krw", "review", "영업현금흐름이 음수여서 이익의 현금전환과 운전자금을 확인해야 합니다.")
        else:
            add("operating_cash_flow_krw", "stable", "영업현금흐름이 양수입니다.")

    return pd.DataFrame(flags, columns=["metric", "value", "severity", "message"])


def analyze_financial_health(rows: list[dict[str, Any]]) -> FinancialHealthResult:
    """Calculate transparent ratios and internal review flags from OpenDART rows."""

    frame = _prepare_rows(rows)
    extracted = [_find_account(frame, key) for key in _ACCOUNT_ALIASES]
    extracted_frame = pd.DataFrame(extracted)
    account_values = {
        row["account_key"]: row["value"] for row in extracted
    }

    metric_values = {
        "current_ratio_pct": _safe_ratio(
            account_values["current_assets"],
            account_values["current_liabilities"],
            100.0,
        ),
        "debt_ratio_pct": _safe_ratio(
            account_values["liabilities"], account_values["equity"], 100.0
        ),
        "equity_ratio_pct": _safe_ratio(
            account_values["equity"], account_values["assets"], 100.0
        ),
        "operating_margin_pct": _safe_ratio(
            account_values["operating_profit"], account_values["revenue"], 100.0
        ),
        "net_margin_pct": _safe_ratio(
            account_values["net_income"], account_values["revenue"], 100.0
        ),
        "interest_coverage_ratio": _safe_ratio(
            account_values["operating_profit"],
            abs(account_values["interest_expense"])
            if account_values["interest_expense"] not in {None, 0}
            else None,
        ),
        "operating_cash_flow_krw": account_values["operating_cash_flow"],
    }

    metrics = pd.DataFrame(
        [
            _metric_row("current_ratio_pct", metric_values["current_ratio_pct"], "%", "current_assets / current_liabilities × 100", ("current_assets", "current_liabilities")),
            _metric_row("debt_ratio_pct", metric_values["debt_ratio_pct"], "%", "liabilities / equity × 100", ("liabilities", "equity")),
            _metric_row("equity_ratio_pct", metric_values["equity_ratio_pct"], "%", "equity / assets × 100", ("equity", "assets")),
            _metric_row("operating_margin_pct", metric_values["operating_margin_pct"], "%", "operating_profit / revenue × 100", ("operating_profit", "revenue")),
            _metric_row("net_margin_pct", metric_values["net_margin_pct"], "%", "net_income / revenue × 100", ("net_income", "revenue")),
            _metric_row("interest_coverage_ratio", metric_values["interest_coverage_ratio"], "x", "operating_profit / abs(finance_costs)", ("operating_profit", "interest_expense")),
            _metric_row("operating_cash_flow_krw", metric_values["operating_cash_flow_krw"], "KRW", "reported operating cash flow", ("operating_cash_flow",)),
        ]
    )

    available_count = int(metrics["available"].sum())
    coverage_ratio = available_count / len(_REQUIRED_METRICS)
    flags = _build_flags(metric_values)
    severity_counts = flags["severity"].value_counts() if not flags.empty else pd.Series(dtype=int)
    if int(severity_counts.get("high", 0)) >= 2:
        screening_band = "high_review_priority"
    elif int(severity_counts.get("high", 0)) == 1 or int(severity_counts.get("review", 0)) >= 2:
        screening_band = "review_required"
    elif coverage_ratio < 0.6:
        screening_band = "insufficient_data"
    else:
        screening_band = "no_major_flag_detected"

    limitations = (
        "내부 사전 스크리닝이며 공식 신용등급·부도확률·대출승인 판단이 아닙니다.",
        "업종, 기업규모, 연결범위, 회계정책, 일회성 손익과 공시 정정 여부를 별도 검토해야 합니다.",
        "계정 매핑은 표준 account_id를 우선하고 계정명을 보조로 사용하므로 추출 근거를 확인해야 합니다.",
        "단일 기간 비율만으로 추세와 현금흐름 변동성을 판단할 수 없습니다.",
    )
    return FinancialHealthResult(
        metrics=metrics,
        extracted_accounts=extracted_frame,
        flags=flags,
        screening_band=screening_band,
        data_coverage_ratio=coverage_ratio,
        limitations=limitations,
    )
