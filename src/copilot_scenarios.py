"""Governed scenario proposal and validation for the trade-finance copilot.

The module may propose structured stress candidates from reviewed case data, but it
never performs financial arithmetic.  Execution remains the responsibility of the
existing deterministic engines and an executed scenario must reference calculation
IDs stored on the unified case.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .copilot_case import CaseScenario, UnifiedCopilotCase

ScenarioType = Literal[
    "settlement_delay",
    "fx_shock",
    "import_cost_increase",
    "combined_stress",
]
ScenarioReadiness = Literal["ready", "blocked"]


class ScenarioCandidate(BaseModel):
    scenario_id: str
    source_case_hash: str
    scenario_type: ScenarioType
    name: str
    rationale: str
    target_transaction_ids: list[str] = Field(default_factory=list)
    parameter_changes: dict[str, Any] = Field(default_factory=dict)
    parameter_sources: dict[str, str] = Field(default_factory=dict)
    required_inputs: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    readiness: ScenarioReadiness
    execution_tool: str
    priority: Literal["high", "medium", "low"] = "medium"
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def blocked_candidate_requires_missing_input(self):
        if self.readiness == "blocked" and not self.missing_inputs:
            raise ValueError("Blocked scenarios must disclose missing inputs.")
        if self.readiness == "ready" and self.missing_inputs:
            raise ValueError("Ready scenarios cannot contain missing inputs.")
        return self


class ScenarioProposalSet(BaseModel):
    case_id: str
    case_hash: str
    analysis_as_of_date: date | None
    candidates: list[ScenarioCandidate]
    authority_boundary: str = (
        "Scenario selection may be AI-assisted, but all financial arithmetic and "
        "scenario execution remain authoritative only in deterministic engines."
    )

    @model_validator(mode="after")
    def candidates_match_proposal_snapshot(self):
        mismatches = [
            item.scenario_id
            for item in self.candidates
            if item.source_case_hash != self.case_hash
        ]
        if mismatches:
            raise ValueError(
                "Scenario candidates must reference the proposal-set case snapshot: "
                + ", ".join(mismatches)
            )
        return self

    @property
    def ready_candidates(self) -> list[ScenarioCandidate]:
        return [item for item in self.candidates if item.readiness == "ready"]


class ScenarioExecutionRequest(BaseModel):
    scenario_id: str
    execution_tool: str
    parameter_changes: dict[str, Any]
    target_transaction_ids: list[str] = Field(default_factory=list)
    case_hash: str
    human_approved: bool = False

    @model_validator(mode="after")
    def approval_required(self):
        if not self.human_approved:
            raise ValueError("Scenario execution requires explicit human approval.")
        return self


def _stable_id(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"SCN-{digest}"


def _transaction_id(row: dict[str, Any]) -> str | None:
    value = row.get("transaction_id") or row.get("id")
    return str(value) if value not in (None, "") else None


def _direction(row: dict[str, Any]) -> str:
    value = row.get("transaction_type") or row.get("direction") or row.get("type")
    return str(value or "").lower()


def _amount(row: dict[str, Any]) -> float:
    for key in ("amount_fc", "amount", "foreign_amount"):
        value = row.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return 0.0


def _status(row: dict[str, Any]) -> str:
    return str(row.get("status") or "").lower()


def _material_receivable(case: UnifiedCopilotCase) -> dict[str, Any] | None:
    exports = [
        row
        for row in case.approved_transactions
        if _direction(row) == "export" and _transaction_id(row)
    ]
    if not exports:
        return None
    return max(exports, key=_amount)


def _active_currencies(case: UnifiedCopilotCase) -> list[str]:
    currencies = {
        str(row.get("currency")).upper()
        for row in case.approved_transactions
        if row.get("currency")
    }
    return sorted(currencies)


def propose_scenarios(case: UnifiedCopilotCase) -> ScenarioProposalSet:
    """Create auditable scenario candidates without calculating financial outcomes."""

    candidates: list[ScenarioCandidate] = []
    material_receivable = _material_receivable(case)
    source_case_hash = case.case_hash

    delay_missing = []
    if material_receivable is None:
        delay_missing.append("approved export receivable")
    if not case.monthly_cost_assumptions:
        delay_missing.append("monthly cost assumptions")
    delay_payload = {
        "type": "settlement_delay",
        "transaction_id": _transaction_id(material_receivable or {}),
        "delay_days": 30,
        "case_hash": source_case_hash,
    }
    candidates.append(
        ScenarioCandidate(
            scenario_id=_stable_id(delay_payload),
            source_case_hash=source_case_hash,
            scenario_type="settlement_delay",
            name="주요 수출채권 30일 수금 지연",
            rationale=(
                "가장 큰 승인 수출채권의 입금 시점을 늦춰 만기 불일치와 "
                "현금부족 시점 변화를 우선 점검합니다."
            ),
            target_transaction_ids=(
                [_transaction_id(material_receivable)] if material_receivable else []
            ),
            parameter_changes={"delay_days": 30},
            parameter_sources={
                "delay_days": "governed default stress assumption",
                "transaction_id": "largest approved export receivable by foreign amount",
            },
            required_inputs=["approved export receivable", "monthly cost assumptions"],
            missing_inputs=delay_missing,
            readiness="blocked" if delay_missing else "ready",
            execution_tool="run_cashflow_delay_scenario",
            priority="high",
            limitations=["30일은 예측값이 아니라 공개된 스트레스 가정입니다."],
        )
    )

    currencies = _active_currencies(case)
    fx_missing = []
    if not case.approved_transactions:
        fx_missing.append("approved transactions")
    if not case.capabilities.official_fx_reference:
        fx_missing.append("official or disclosed FX reference")
    fx_payload = {
        "type": "fx_shock",
        "currencies": currencies,
        "shock_percent": -5,
        "case_hash": source_case_hash,
    }
    candidates.append(
        ScenarioCandidate(
            scenario_id=_stable_id(fx_payload),
            source_case_hash=source_case_hash,
            scenario_type="fx_shock",
            name="주요 거래통화 기준환율 5% 하락",
            rationale=(
                "수출 중심 외화포지션의 원화 환산가치 하락과 헤지비율별 보호효과를 "
                "비교하기 위한 표준 하방 스트레스입니다."
            ),
            parameter_changes={"fx_shock_percent": -5, "currencies": currencies},
            parameter_sources={
                "fx_shock_percent": "governed default stress assumption",
                "currencies": "approved transaction currencies",
            },
            required_inputs=["approved transactions", "official or disclosed FX reference"],
            missing_inputs=fx_missing,
            readiness="blocked" if fx_missing else "ready",
            execution_tool="compare_hedge_ratios",
            priority="medium",
            limitations=[
                "공개 참고환율 기반 시뮬레이션이며 실제 KB 실행 가능 견적이 아닙니다."
            ],
        )
    )

    imports = [row for row in case.approved_transactions if _direction(row) == "import"]
    cost_missing = [] if imports else ["approved import transaction"]
    cost_payload = {
        "type": "import_cost_increase",
        "transaction_ids": [_transaction_id(row) for row in imports if _transaction_id(row)],
        "increase_percent": 10,
        "case_hash": source_case_hash,
    }
    candidates.append(
        ScenarioCandidate(
            scenario_id=_stable_id(cost_payload),
            source_case_hash=source_case_hash,
            scenario_type="import_cost_increase",
            name="수입 결제금액 10% 증가",
            rationale=(
                "원재료·운송비 등 수입 관련 지급액 증가가 유동성 공백을 얼마나 "
                "확대하는지 점검합니다."
            ),
            target_transaction_ids=[
                _transaction_id(row) for row in imports if _transaction_id(row)
            ],
            parameter_changes={"import_amount_increase_percent": 10},
            parameter_sources={
                "import_amount_increase_percent": "governed default stress assumption"
            },
            required_inputs=["approved import transaction"],
            missing_inputs=cost_missing,
            readiness="blocked" if cost_missing else "ready",
            execution_tool="run_import_cost_scenario",
            priority="medium",
            limitations=["10%는 예측이 아니라 공개된 스트레스 가정입니다."],
        )
    )

    combined_missing = sorted(set(delay_missing + fx_missing))
    combined_payload = {
        "type": "combined_stress",
        "transaction_id": _transaction_id(material_receivable or {}),
        "delay_days": 30,
        "fx_shock_percent": -5,
        "case_hash": source_case_hash,
    }
    candidates.append(
        ScenarioCandidate(
            scenario_id=_stable_id(combined_payload),
            source_case_hash=source_case_hash,
            scenario_type="combined_stress",
            name="수금 30일 지연 + 기준환율 5% 하락",
            rationale=(
                "결제시점 충격과 환율 충격이 동시에 발생하는 경우를 분리 시나리오와 "
                "비교해 복합 취약성을 확인합니다."
            ),
            target_transaction_ids=(
                [_transaction_id(material_receivable)] if material_receivable else []
            ),
            parameter_changes={"delay_days": 30, "fx_shock_percent": -5},
            parameter_sources={
                "delay_days": "governed default stress assumption",
                "fx_shock_percent": "governed default stress assumption",
            },
            required_inputs=[
                "approved export receivable",
                "monthly cost assumptions",
                "official or disclosed FX reference",
            ],
            missing_inputs=combined_missing,
            readiness="blocked" if combined_missing else "ready",
            execution_tool="run_combined_trade_stress_scenario",
            priority="high",
            limitations=[
                "복합 시나리오는 각 충격의 동시 발생을 가정하며 발생확률을 제시하지 않습니다.",
                "공개 참고환율 기반이며 실제 KB 실행 가능 견적이 아닙니다.",
            ],
        )
    )

    return ScenarioProposalSet(
        case_id=case.identity.case_id,
        case_hash=source_case_hash,
        analysis_as_of_date=case.identity.analysis_as_of_date,
        candidates=candidates,
    )


def build_execution_request(
    case: UnifiedCopilotCase,
    candidate: ScenarioCandidate,
    *,
    human_approved: bool,
) -> ScenarioExecutionRequest:
    """Convert a ready candidate into an immutable execution request."""

    if candidate.readiness != "ready":
        raise ValueError("Blocked scenario candidates cannot be executed.")
    if candidate.source_case_hash != case.case_hash:
        raise ValueError(
            "Scenario candidate was generated from a different case snapshot; "
            "regenerate and reapprove the scenario before execution."
        )
    return ScenarioExecutionRequest(
        scenario_id=candidate.scenario_id,
        execution_tool=candidate.execution_tool,
        parameter_changes=candidate.parameter_changes,
        target_transaction_ids=candidate.target_transaction_ids,
        case_hash=case.case_hash,
        human_approved=human_approved,
    )


def attach_proposed_scenarios(
    case: UnifiedCopilotCase,
    proposals: ScenarioProposalSet,
) -> UnifiedCopilotCase:
    """Attach proposals to a copied case without mutating the original case."""

    if proposals.case_hash != case.case_hash:
        raise ValueError("Scenario proposals were generated from a different case snapshot.")
    existing = {item.scenario_id: item for item in case.scenarios}
    for candidate in proposals.candidates:
        existing[candidate.scenario_id] = CaseScenario(
            scenario_id=candidate.scenario_id,
            name=candidate.name,
            rationale=candidate.rationale,
            status="proposed",
            parameter_changes=candidate.parameter_changes,
            parameter_sources=candidate.parameter_sources,
            required_inputs=candidate.required_inputs,
            missing_inputs=candidate.missing_inputs,
            limitations=candidate.limitations,
        )
    return case.model_copy(update={"scenarios": list(existing.values())})
