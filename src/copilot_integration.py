"""Application integration boundary for the Global Trade Copilot workspace.

This module converts the current Streamlit/session data structures into the governed
``UnifiedCopilotCase`` contract and returns a renderer-neutral workspace payload.
It performs no financial arithmetic and does not approve transactions or scenarios.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Iterable

from .copilot_case import (
    CaseDataAsset,
    CaseEvidenceItem,
    CaseIdentity,
    MissingInput,
    UnifiedCopilotCase,
)
from .copilot_workspace import CopilotWorkspace, build_copilot_workspace


def _records(value: Any) -> list[dict[str, Any]]:
    """Normalize pandas-like tables or record collections without importing pandas."""

    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            records = value.to_dict("records")
            return [dict(item) for item in records]
        except TypeError:
            pass
    if isinstance(value, dict):
        return [dict(value)]
    return [dict(item) for item in value]


def _stable_evidence_id(source_name: str, transaction_ids: Iterable[str]) -> str:
    payload = {
        "source_name": source_name,
        "transaction_ids": sorted(set(transaction_ids)),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"EVD-{digest}"


def _as_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _foreign_cash_records(company: dict[str, Any]) -> list[dict[str, Any]]:
    foreign_cash = company.get("foreign_cash") or {}
    if isinstance(foreign_cash, dict):
        return [
            {"currency": str(currency).upper(), "amount_fc": amount}
            for currency, amount in sorted(foreign_cash.items())
        ]
    return _records(foreign_cash)


def _build_evidence(transactions: list[dict[str, Any]]) -> list[CaseEvidenceItem]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in transactions:
        source_name = str(
            row.get("source_filename")
            or row.get("document_reference")
            or row.get("source_type")
            or "manual-or-bundled-portfolio"
        )
        grouped.setdefault(source_name, []).append(row)

    evidence: list[CaseEvidenceItem] = []
    for source_name, rows in sorted(grouped.items()):
        transaction_ids = [
            str(row.get("transaction_id") or row.get("id"))
            for row in rows
            if row.get("transaction_id") or row.get("id")
        ]
        warnings = sorted(
            {
                str(warning)
                for row in rows
                for warning in (row.get("warnings") or [])
                if warning
            }
        )
        source_type = str(rows[0].get("source_type") or "portfolio_record")
        evidence.append(
            CaseEvidenceItem(
                evidence_id=_stable_evidence_id(source_name, transaction_ids),
                evidence_type=source_type,
                source_name=source_name,
                status="approved",
                linked_transaction_ids=transaction_ids,
                warnings=warnings,
            )
        )
    return evidence


def _fx_asset(fx_rates: Any, analysis_as_of: date | None) -> CaseDataAsset | None:
    records = _records(fx_rates)
    if not records:
        return None
    return CaseDataAsset(
        asset_name="public_or_disclosed_fx_reference",
        status="available",
        source="current application FX-rate table",
        as_of_date=analysis_as_of,
        retrieved_at=datetime.now(timezone.utc),
        payload=records,
        limitations=[
            "The table is a public or disclosed reference input, not an executable KB quote."
        ],
    )


def _financial_asset(company: dict[str, Any], analysis_as_of: date | None) -> CaseDataAsset | None:
    fields = {
        key: company.get(key)
        for key in (
            "business_type",
            "customer_segment",
            "current_cash_krw",
            "monthly_fixed_cost_krw",
            "data_timestamp",
        )
        if company.get(key) is not None
    }
    if not fields:
        return None
    return CaseDataAsset(
        asset_name="financial_health_pre_screening_context",
        status="available",
        source="current application company profile",
        as_of_date=analysis_as_of,
        payload=fields,
        limitations=[
            "재무건전성 사전 스크리닝용 컨텍스트이며 공식 신용등급이 아닙니다."
        ],
    )


def build_unified_case_from_app_state(
    *,
    company: dict[str, Any],
    approved_transactions: Any,
    fx_rates: Any = None,
    cash_allocations: Any = None,
    audit_events: Any = None,
    case_id: str | None = None,
) -> UnifiedCopilotCase:
    """Translate current application state into one governed case snapshot."""

    transactions = _records(approved_transactions)
    analysis_as_of = _as_date(company.get("as_of_date"))
    resolved_case_id = case_id or str(company.get("case_id") or "KB-DEMO-CASE")

    monthly_cost = {}
    if company.get("monthly_fixed_cost_krw") is not None:
        monthly_cost["monthly_fixed_cost_krw"] = company["monthly_fixed_cost_krw"]
    if company.get("current_cash_krw") is not None:
        monthly_cost["current_cash_krw"] = company["current_cash_krw"]

    missing_inputs: list[MissingInput] = []
    if not transactions:
        missing_inputs.append(
            MissingInput(
                input_name="human-approved transactions",
                reason="No approved portfolio records were supplied by the application.",
                blocks=["exposure", "maturity", "cash-flow", "scenario execution"],
                requested_from="trade-finance reviewer",
            )
        )
    if not monthly_cost:
        missing_inputs.append(
            MissingInput(
                input_name="monthly cost assumptions",
                reason="Cash-flow and settlement-delay review require disclosed cost inputs.",
                blocks=["cash-flow", "settlement-delay stress"],
                requested_from="company reviewer",
                can_use_disclosed_assumption=True,
            )
        )

    policy_payload = {
        "cash_allocations": _records(cash_allocations),
        "audit_event_count": len(_records(audit_events)),
    }

    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id=resolved_case_id,
            company_name=company.get("company_name"),
            business_registration_number=company.get("business_registration_number"),
            analysis_as_of_date=analysis_as_of,
        ),
        evidence=_build_evidence(transactions),
        approved_transactions=transactions,
        foreign_cash_positions=_foreign_cash_records(company),
        monthly_cost_assumptions=monthly_cost,
        official_fx_reference=_fx_asset(fx_rates, analysis_as_of),
        financial_context=_financial_asset(company, analysis_as_of),
        policy_context=CaseDataAsset(
            asset_name="application_review_context",
            status="available" if policy_payload["audit_event_count"] else "partial",
            source="current Streamlit session",
            as_of_date=analysis_as_of,
            payload=policy_payload,
            limitations=["Session metadata is workflow context, not a financial calculation."],
        ),
        missing_inputs=missing_inputs,
    )


def build_workspace_from_app_state(
    *,
    user_objective: str,
    company: dict[str, Any],
    approved_transactions: Any,
    fx_rates: Any = None,
    cash_allocations: Any = None,
    audit_events: Any = None,
    case_id: str | None = None,
) -> CopilotWorkspace:
    """Build the primary Copilot workspace directly from current application state."""

    case = build_unified_case_from_app_state(
        company=company,
        approved_transactions=approved_transactions,
        fx_rates=fx_rates,
        cash_allocations=cash_allocations,
        audit_events=audit_events,
        case_id=case_id,
    )
    return build_copilot_workspace(case, user_objective)


def workspace_render_payload(workspace: CopilotWorkspace) -> dict[str, Any]:
    """Return a compact payload suitable for Streamlit section rendering."""

    return {
        "header": {
            "workspace_id": workspace.workspace_id,
            "case_id": workspace.case_id,
            "case_hash": workspace.case_hash,
            "objective": workspace.user_objective,
            "disclaimer": workspace.disclaimer,
            "authority_boundary": workspace.authority_boundary,
        },
        "sections": [section.model_dump(mode="json") for section in workspace.sections],
        "trace": [step.model_dump(mode="json") for step in workspace.trace],
        "audit_export": workspace.audit_export,
    }
