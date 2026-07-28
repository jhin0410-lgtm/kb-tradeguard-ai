"""Deterministic transaction decision brief and dependency-based action plan.

The brief synthesizes existing reviewed case records.  It deliberately uses no opaque
risk score and does not approve or reject a transaction, clear compliance obligations,
provide legal advice, or predict institutional decisions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..copilot_case import UnifiedCopilotCase
from ..trade_finance_domain import (
    ActionPlanItem,
    ComplianceScreeningResult,
    ConsultationRequirement,
    CounterpartyProfile,
    CountryRiskFact,
    ProductCandidate,
    SourceReference,
    TradeRiskSignal,
)

Disposition = Literal[
    "specialist_clearance_required",
    "conditions_required_before_commitment",
    "additional_information_required",
    "review_required",
    "no_material_screening_flags",
]


class TransactionDecisionBriefRuleRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    registry_name: str
    registry_version: str
    effective_date: date
    authority_boundary: str
    severity_order: list[str]
    category_order: list[str]
    minimum_coverage: list[str]
    disposition_precedence: list[str]
    action_priority: dict[str, int]

    @model_validator(mode="after")
    def registry_orders_are_unique(self):
        for label, values in (
            ("severity_order", self.severity_order),
            ("category_order", self.category_order),
            ("minimum_coverage", self.minimum_coverage),
            ("disposition_precedence", self.disposition_precedence),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} values must be unique")
        return self


class TransactionDecisionBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    brief_id: str
    transaction_id: str
    counterparty_id: str | None = None
    country_code: str | None = None
    product_candidate_ids: list[str] = Field(default_factory=list)
    consultation_requirement_ids: list[str] = Field(default_factory=list)
    max_ranked_concerns: int = Field(default=5, ge=1, le=10)

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("country_code must contain two letters")
        return normalized

    @model_validator(mode="after")
    def selected_ids_are_unique(self):
        for label, values in (
            ("product_candidate_ids", self.product_candidate_ids),
            ("consultation_requirement_ids", self.consultation_requirement_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} values must be unique")
        return self


class DecisionConcern(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    concern_id: str
    rank: int = Field(ge=1)
    source_type: Literal[
        "risk_signal", "compliance_screening", "country_fact", "counterparty"
    ]
    source_ids: list[str]
    category: str
    severity: Literal["critical", "high", "medium", "low", "informational"]
    title: str
    factual_basis: str
    unresolved_facts: list[str] = Field(default_factory=list)


class TransactionDecisionBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief_id: str
    transaction_id: str
    disposition: Disposition
    disposition_rationale: list[str]
    ranked_concerns: list[DecisionConcern]
    country_fact_ids: list[str]
    compliance_screening_ids: list[str]
    calculation_ids: list[str]
    product_candidate_ids: list[str]
    consultation_requirement_ids: list[str]
    missing_information: list[str]
    action_plan: list[ActionPlanItem]
    authority_boundary: str
    source: SourceReference


class TransactionDecisionBriefOutcome(BaseModel):
    case_before_hash: str
    case_after_hash: str
    brief_id: str
    transaction_id: str
    disposition: Disposition
    action_ids: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


def default_transaction_decision_brief_registry_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "reference"
        / "transaction_decision_brief_rules_v1.json"
    )


def load_transaction_decision_brief_registry(
    path: str | Path | None = None,
) -> TransactionDecisionBriefRuleRegistry:
    registry_path = (
        Path(path)
        if path is not None
        else default_transaction_decision_brief_registry_path()
    )
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Unable to load transaction decision brief registry: {registry_path}"
        ) from exc
    return TransactionDecisionBriefRuleRegistry.model_validate(payload)


def _stable_registry_locator(path: Path) -> str:
    """Return a checkout-independent locator for an auditable project registry."""

    parts = path.resolve().parts
    for index in range(len(parts) - 1):
        if parts[index : index + 2] == ("data", "reference"):
            return Path(*parts[index:]).as_posix()
    return f"project-rule://transaction-decision-brief/{path.name}"


def _registry_source(
    registry: TransactionDecisionBriefRuleRegistry,
    path: Path,
) -> SourceReference:
    return SourceReference(
        source_id=f"TRANSACTION-DECISION-BRIEF-{registry.registry_version}",
        source_name=registry.registry_name,
        source_tier="derived",
        source_kind="project_rule",
        source_locator=_stable_registry_locator(path),
        as_of_date=registry.effective_date,
        content_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
        effective_date_verified=True,
    )


def _find_approved_transaction(case: UnifiedCopilotCase, transaction_id: str) -> dict:
    matches = [
        item
        for item in case.approved_transactions
        if str(item.get("transaction_id")) == transaction_id
    ]
    if not matches:
        raise ValueError(f"Approved transaction not found: {transaction_id}")
    if len(matches) > 1:
        raise ValueError(f"Approved transaction ID is duplicated: {transaction_id}")
    return matches[0]


def _select_counterparty(
    case: UnifiedCopilotCase, counterparty_id: str | None
) -> CounterpartyProfile | None:
    if counterparty_id is None:
        return None
    matches = [
        item
        for item in case.trade_finance.counterparties
        if item.counterparty_id == counterparty_id
    ]
    if not matches:
        raise ValueError(f"Counterparty not found: {counterparty_id}")
    return matches[0]


def _select_by_ids(records: list, ids: list[str], attribute: str, label: str) -> list:
    by_id = {getattr(item, attribute): item for item in records}
    missing = [identifier for identifier in ids if identifier not in by_id]
    if missing:
        raise ValueError(f"Unknown {label} IDs: " + ", ".join(missing))
    return [by_id[identifier] for identifier in ids]


def _transaction_signals(
    case: UnifiedCopilotCase, transaction_id: str
) -> list[TradeRiskSignal]:
    return [
        item
        for item in case.trade_finance.risk_signals
        if transaction_id in item.affected_transaction_ids
    ]


def _related_country_facts(
    case: UnifiedCopilotCase, country_code: str | None
) -> list[CountryRiskFact]:
    if country_code is None:
        return []
    return [
        item
        for item in case.trade_finance.country_risk_facts
        if item.country_code == country_code
    ]


def _related_screenings(
    case: UnifiedCopilotCase,
    counterparty: CounterpartyProfile | None,
    country_code: str | None,
) -> list[ComplianceScreeningResult]:
    selected = []
    for item in case.trade_finance.compliance_screenings:
        if (
            counterparty is not None
            and item.subject_type == "counterparty"
            and item.subject_id == counterparty.counterparty_id
        ):
            selected.append(item)
        elif (
            country_code is not None
            and item.subject_type == "country"
            and item.subject_id == country_code
        ):
            selected.append(item)
    return selected


def _capacity_calculation_ids(
    case: UnifiedCopilotCase, transaction_id: str
) -> list[str]:
    return sorted(
        calculation_id
        for calculation_id, calculation in case.calculations.items()
        if calculation.calculation_name == "Transaction financial capacity assessment"
        and str(calculation.input_assumptions.get("transaction_id")) == transaction_id
    )


def _coverage_gaps(
    case: UnifiedCopilotCase,
    request: TransactionDecisionBriefRequest,
    counterparty: CounterpartyProfile | None,
    country_facts: list[CountryRiskFact],
    screenings: list[ComplianceScreeningResult],
    calculation_ids: list[str],
) -> list[str]:
    gaps: list[str] = []
    if counterparty is None:
        gaps.append("counterparty_identity: transaction counterparty has not been selected")
    else:
        if not counterparty.registration_number:
            gaps.append("counterparty_identity: registration number is missing")
        if counterparty.due_diligence_status in {"not_started", "identity_only"}:
            gaps.append(
                "counterparty_due_diligence: public information or professional credit investigation is incomplete"
            )
    if request.country_code is None:
        gaps.append("country_context: transaction country has not been selected")
    elif not country_facts:
        gaps.append("country_context: no country facts are attached for the selected country")
    elif all(item.record_status == "stale" for item in country_facts):
        gaps.append("country_context: all selected country facts are stale")
    if not screenings:
        gaps.append("compliance_screening: no related country or counterparty screening is attached")
    elif any(item.record_status == "stale" for item in screenings):
        gaps.append(
            "compliance_screening: at least one related screening is stale and must be refreshed"
        )
    elif any(item.result == "not_screened" for item in screenings):
        gaps.append("compliance_screening: at least one related subject remains not screened")
    if not any(
        item.transaction_id == request.transaction_id
        for item in case.trade_finance.payment_structures
    ):
        gaps.append("payment_structure: reviewed transaction payment terms are missing")
    if not any(
        request.transaction_id in item.linked_transaction_ids
        and item.document_type
        in {"contract", "purchase_order", "commercial_invoice", "letter_of_credit"}
        and item.record_status in {"verified", "partial"}
        for item in case.trade_finance.trade_documents
    ):
        gaps.append("reviewed_trade_document: no reviewed core trade document is linked")
    if not calculation_ids:
        gaps.append(
            "financial_capacity_calculation: transaction-to-financial-capacity assessment is missing"
        )
    return gaps


def _signal_concerns(signals: list[TradeRiskSignal]) -> list[DecisionConcern]:
    return [
        DecisionConcern(
            concern_id=f"CONCERN-{signal.signal_id}",
            rank=1,
            source_type="risk_signal",
            source_ids=[signal.signal_id],
            category=signal.category,
            severity=signal.severity,
            title=signal.title,
            factual_basis=signal.factual_trigger,
            unresolved_facts=list(signal.unresolved_facts),
        )
        for signal in signals
    ]


def _screening_concerns(
    screenings: list[ComplianceScreeningResult],
) -> list[DecisionConcern]:
    concerns: list[DecisionConcern] = []
    for screening in screenings:
        if screening.result == "clear":
            continue
        if screening.result == "confirmed_match":
            severity = "critical"
        elif screening.result == "potential_match":
            severity = (
                "critical"
                if screening.screening_type in {"sanctions", "restricted_party"}
                else "high"
            )
        else:
            severity = "medium"
        concerns.append(
            DecisionConcern(
                concern_id=f"CONCERN-SCREEN-{screening.screening_id}",
                rank=1,
                source_type="compliance_screening",
                source_ids=[screening.screening_id],
                category="compliance",
                severity=severity,
                title=f"{screening.screening_type} screening: {screening.result}",
                factual_basis=(
                    f"subject={screening.subject_name}; method={screening.method}; "
                    f"human_reviewed={screening.reviewed_by_human}"
                ),
                unresolved_facts=[
                    "Current compliance policy and source-list status require specialist confirmation."
                ],
            )
        )
    return concerns


def _counterparty_concern(
    counterparty: CounterpartyProfile | None,
) -> list[DecisionConcern]:
    if counterparty is None:
        return []
    if counterparty.due_diligence_status == "professional_credit_investigation_completed":
        return []
    if counterparty.due_diligence_status in {
        "not_started",
        "identity_only",
        "professional_credit_investigation_required",
    }:
        severity = "high"
    else:
        severity = "medium"
    return [
        DecisionConcern(
            concern_id=f"CONCERN-COUNTERPARTY-{counterparty.counterparty_id}",
            rank=1,
            source_type="counterparty",
            source_ids=[counterparty.counterparty_id],
            category="counterparty",
            severity=severity,
            title="바이어 신용조사 또는 실사 보완 필요",
            factual_basis=(
                f"relationship_status={counterparty.relationship_status}; "
                f"due_diligence_status={counterparty.due_diligence_status}; "
                f"prior_payment_history={counterparty.prior_payment_history}"
            ),
            unresolved_facts=[
                "법인 식별, 재무정보, 지급이력, 소송·파산 및 전문 신용조사 결과를 확인해야 합니다."
            ],
        )
    ]


def _fatf_country_concerns(country_facts: list[CountryRiskFact]) -> list[DecisionConcern]:
    concerns: list[DecisionConcern] = []
    for fact in country_facts:
        if fact.metric_name != "FATF public-list status":
            continue
        value = str(fact.value)
        if value == "call_for_action":
            severity = "high"
        elif value == "increased_monitoring":
            severity = "medium"
        elif fact.record_status == "stale":
            severity = "medium"
        else:
            continue
        concerns.append(
            DecisionConcern(
                concern_id=f"CONCERN-COUNTRY-{fact.fact_id}",
                rank=1,
                source_type="country_fact",
                source_ids=[fact.fact_id],
                category="compliance",
                severity=severity,
                title="FATF 공개목록 국가 맥락 확인 필요",
                factual_basis=f"{fact.country_code}: {value}; record_status={fact.record_status}",
                unresolved_facts=[
                    "공개목록 상태는 거래금지나 바이어 신용등급이 아니며 현행 내부정책 검토가 필요합니다."
                ],
            )
        )
    return concerns


def _rank_concerns(
    concerns: list[DecisionConcern],
    registry: TransactionDecisionBriefRuleRegistry,
    limit: int,
) -> list[DecisionConcern]:
    severity_rank = {value: index for index, value in enumerate(registry.severity_order)}
    category_rank = {value: index for index, value in enumerate(registry.category_order)}
    ordered = sorted(
        concerns,
        key=lambda item: (
            severity_rank.get(item.severity, len(severity_rank)),
            category_rank.get(item.category, len(category_rank)),
            item.concern_id,
        ),
    )[:limit]
    return [item.model_copy(update={"rank": index}) for index, item in enumerate(ordered, 1)]


def _disposition(
    concerns: list[DecisionConcern], missing_information: list[str]
) -> tuple[Disposition, list[str]]:
    rationale: list[str] = []
    if any(item.severity == "critical" for item in concerns):
        rationale.append("At least one critical screening concern requires specialist clearance.")
        return "specialist_clearance_required", rationale
    if any(item.severity == "high" for item in concerns):
        rationale.append("At least one high-severity concern requires conditions or mitigation before commitment.")
        return "conditions_required_before_commitment", rationale
    if missing_information:
        rationale.append("Minimum evidence coverage is incomplete for a transaction-level review.")
        return "additional_information_required", rationale
    if any(item.severity in {"medium", "low"} for item in concerns):
        rationale.append("Non-critical screening concerns remain for documented review.")
        return "review_required", rationale
    rationale.append("No material screening flags were found in the attached reviewed evidence.")
    rationale.append("This is not an approval, low-risk certification, or compliance clearance.")
    return "no_material_screening_flags", rationale


def _responsible_party(route: str) -> str:
    return {
        "bank_relationship_manager": "bank",
        "trade_finance_specialist": "bank",
        "foreign_exchange_specialist": "bank",
        "ksure": "ksure",
        "legal": "legal_counsel",
        "logistics": "logistics_provider",
    }.get(route, "customer")


def _build_actions(
    request: TransactionDecisionBriefRequest,
    concerns: list[DecisionConcern],
    gaps: list[str],
    candidates: list[ProductCandidate],
    requirements: list[ConsultationRequirement],
    registry: TransactionDecisionBriefRuleRegistry,
    source: SourceReference,
) -> list[ActionPlanItem]:
    raw_actions: list[dict] = []
    concern_by_category: dict[str, list[DecisionConcern]] = {}
    for concern in concerns:
        concern_by_category.setdefault(concern.category, []).append(concern)

    compliance_concerns = concern_by_category.get("compliance", [])
    if compliance_concerns or any(item.startswith("compliance_screening") for item in gaps):
        raw_actions.append(
            {
                "key": "compliance",
                "priority": registry.action_priority["compliance"],
                "title": "제재·AML 및 공개목록 검토 완료",
                "rationale": "관련 screening 결과와 최신 기관 정책을 확인하고 잠재 일치를 사람이 해소해야 합니다.",
                "responsible_party": "bank",
                "documents": ["바이어 법인명·주소·등록번호", "거래은행 및 결제경로 정보"],
                "signal_ids": [
                    source_id
                    for concern in compliance_concerns
                    if concern.source_type == "risk_signal"
                    for source_id in concern.source_ids
                ],
            }
        )

    counterparty_concerns = concern_by_category.get("counterparty", [])
    if counterparty_concerns or any(item.startswith("counterparty_") for item in gaps):
        raw_actions.append(
            {
                "key": "counterparty",
                "priority": registry.action_priority["counterparty"],
                "title": "바이어 법인식별 및 신용조사 보완",
                "rationale": "결제조건을 확정하기 전에 법인 실체, 지급능력, 지급이력과 전문 신용조사 필요성을 확인합니다.",
                "responsible_party": "customer",
                "documents": ["바이어 법인명·주소·등록번호", "기존 거래·지급이력"],
                "signal_ids": [
                    source_id
                    for concern in counterparty_concerns
                    if concern.source_type == "risk_signal"
                    for source_id in concern.source_ids
                ],
            }
        )

    document_concerns = concern_by_category.get("contract_document", []) + concern_by_category.get(
        "payment_instrument", []
    )
    if document_concerns or any(item.startswith("reviewed_trade_document") for item in gaps):
        raw_actions.append(
            {
                "key": "document",
                "priority": registry.action_priority["document"],
                "title": "계약서·L/C 핵심 조건 수정 및 재검토",
                "rationale": "결제기산점, 문서제시 가능성, Incoterms, 당사자·금액·기한 불일치를 수정한 뒤 승인본을 다시 등록합니다.",
                "responsible_party": "customer",
                "documents": ["수정 계약서 또는 L/C amendment", "수정 Invoice 및 관련 운송서류"],
                "signal_ids": [source_id for concern in document_concerns for source_id in concern.source_ids],
            }
        )

    capacity_concerns = (
        concern_by_category.get("liquidity", [])
        + concern_by_category.get("company_capacity", [])
        + concern_by_category.get("concentration", [])
    )
    if capacity_concerns or any(
        item.startswith("financial_capacity_calculation") for item in gaps
    ):
        raw_actions.append(
            {
                "key": "capacity",
                "priority": registry.action_priority["capacity"],
                "title": "거래 자금구조와 손실흡수 여력 재설계",
                "rationale": "필요 운전자금, 선급금, 보험·보증, 가용한도와 지급·회수시점을 기업 유동성과 함께 검토합니다.",
                "responsible_party": "customer",
                "documents": ["최근 재무자료", "필요자금 산출근거", "기존 차입·한도·담보·보증 현황"],
                "signal_ids": [source_id for concern in capacity_concerns for source_id in concern.source_ids],
            }
        )

    if any(item.startswith("country_context") for item in gaps):
        raw_actions.append(
            {
                "key": "country",
                "priority": registry.action_priority["country"],
                "title": "국가위험과 국별 인수조건 최신 확인",
                "rationale": "국가 거시·송금·AML 자료의 기준일과 K-SURE 국별인수방침을 최신 상태로 확인합니다.",
                "responsible_party": "customer",
                "documents": ["거래국가와 결제통화", "바이어 소재지", "예상 선적·결제일"],
                "signal_ids": [],
            }
        )

    non_specific_gaps = [
        item
        for item in gaps
        if not any(
            item.startswith(prefix)
            for prefix in (
                "compliance_screening",
                "counterparty_",
                "reviewed_trade_document",
                "financial_capacity_calculation",
                "country_context",
            )
        )
    ]
    if non_specific_gaps:
        raw_actions.append(
            {
                "key": "information",
                "priority": registry.action_priority["information"],
                "title": "필수 거래정보와 승인 증빙 보완",
                "rationale": "; ".join(non_specific_gaps),
                "responsible_party": "customer",
                "documents": [],
                "signal_ids": [],
            }
        )

    candidate_by_name = {
        item.product_or_service_name: item
        for item in candidates
        if item.candidate_status in {"consultation_candidate", "insufficient_information"}
    }
    for requirement in requirements:
        matching_name = next(
            (
                name
                for name in candidate_by_name
                if name in requirement.purpose
            ),
            None,
        )
        candidate = candidate_by_name.get(matching_name) if matching_name else None
        raw_actions.append(
            {
                "key": f"consult-{requirement.requirement_id}",
                "priority": registry.action_priority["product_consultation"],
                "title": (
                    f"{matching_name} 상담조건 확인"
                    if matching_name
                    else "무역금융 상담조건 확인"
                ),
                "rationale": (
                    candidate.next_action
                    if candidate is not None
                    else requirement.purpose
                ),
                "responsible_party": _responsible_party(requirement.consultation_route),
                "documents": list(requirement.required_documents),
                "signal_ids": [],
            }
        )

    raw_actions.append(
        {
            "key": "reassessment",
            "priority": registry.action_priority["reassessment"],
            "title": "조건 반영 후 거래 사전진단 재실행",
            "rationale": "수정 문서, 최신 조사결과, 금융상담 결과와 실제 보호조건을 반영하여 잔여위험과 실행순서를 재평가합니다.",
            "responsible_party": "customer",
            "documents": ["수정 문서", "최신 조사·상담 결과", "확정된 보험·보증·금융 조건"],
            "signal_ids": [],
        }
    )

    ordered = sorted(raw_actions, key=lambda item: (item["priority"], item["key"]))
    action_ids = {
        item["key"]: f"ACTION-{request.transaction_id}-{item['key'].upper()}"
        for item in ordered
    }
    immediate_keys = {
        item["key"]
        for item in ordered
        if item["key"] in {"compliance", "counterparty", "information", "country"}
    }
    dependency_by_key: dict[str, list[str]] = {}
    for item in ordered:
        key = item["key"]
        dependencies: list[str] = []
        if key == "document" and "counterparty" in action_ids:
            dependencies.append(action_ids["counterparty"])
        elif key == "capacity" and "information" in action_ids:
            dependencies.append(action_ids["information"])
        elif key.startswith("consult-"):
            dependencies.extend(action_ids[name] for name in sorted(immediate_keys))
            if "document" in action_ids:
                dependencies.append(action_ids["document"])
            if "capacity" in action_ids:
                dependencies.append(action_ids["capacity"])
        elif key == "reassessment":
            dependencies.extend(
                action_ids[other]
                for other in ordered_keys(ordered)
                if other != "reassessment"
            )
        dependency_by_key[key] = list(dict.fromkeys(dependencies))

    actions: list[ActionPlanItem] = []
    for sequence, item in enumerate(ordered, 1):
        dependencies = dependency_by_key[item["key"]]
        actions.append(
            ActionPlanItem(
                action_id=action_ids[item["key"]],
                sequence=sequence,
                title=item["title"],
                rationale=item["rationale"],
                responsible_party=item["responsible_party"],
                dependency_action_ids=dependencies,
                required_documents=list(dict.fromkeys(item["documents"])),
                supporting_risk_signal_ids=list(dict.fromkeys(item["signal_ids"])),
                status="ready" if not dependencies else "proposed",
                source=source,
                record_status="verified",
                limitations=[registry.authority_boundary],
            )
        )
    return actions


def ordered_keys(ordered_actions: list[dict]) -> list[str]:
    return [item["key"] for item in ordered_actions]


def build_transaction_decision_brief(
    case: UnifiedCopilotCase,
    request: TransactionDecisionBriefRequest,
    *,
    registry_path: str | Path | None = None,
) -> TransactionDecisionBrief:
    """Build a transaction-specific evidence synthesis with explicit ordering rules."""

    _find_approved_transaction(case, request.transaction_id)
    counterparty = _select_counterparty(case, request.counterparty_id)
    if (
        counterparty is not None
        and request.country_code is not None
        and counterparty.country_code != request.country_code
    ):
        raise ValueError("Selected country does not match the counterparty country")

    candidates = _select_by_ids(
        case.trade_finance.product_candidates,
        request.product_candidate_ids,
        "product_candidate_id",
        "product candidate",
    )
    requirements = _select_by_ids(
        case.trade_finance.consultation_requirements,
        request.consultation_requirement_ids,
        "requirement_id",
        "consultation requirement",
    )
    country_facts = _related_country_facts(case, request.country_code)
    screenings = _related_screenings(case, counterparty, request.country_code)
    calculation_ids = _capacity_calculation_ids(case, request.transaction_id)
    gaps = _coverage_gaps(
        case,
        request,
        counterparty,
        country_facts,
        screenings,
        calculation_ids,
    )

    resolved_path = (
        Path(registry_path)
        if registry_path is not None
        else default_transaction_decision_brief_registry_path()
    )
    registry = load_transaction_decision_brief_registry(resolved_path)
    source = _registry_source(registry, resolved_path)
    all_concerns = (
        _signal_concerns(_transaction_signals(case, request.transaction_id))
        + _screening_concerns(screenings)
        + _counterparty_concern(counterparty)
        + _fatf_country_concerns(country_facts)
    )
    ranked = _rank_concerns(
        all_concerns,
        registry,
        request.max_ranked_concerns,
    )
    disposition, rationale = _disposition(all_concerns, gaps)
    actions = _build_actions(
        request,
        all_concerns,
        gaps,
        candidates,
        requirements,
        registry,
        source,
    )
    return TransactionDecisionBrief(
        brief_id=request.brief_id,
        transaction_id=request.transaction_id,
        disposition=disposition,
        disposition_rationale=rationale,
        ranked_concerns=ranked,
        country_fact_ids=[item.fact_id for item in country_facts],
        compliance_screening_ids=[item.screening_id for item in screenings],
        calculation_ids=calculation_ids,
        product_candidate_ids=[item.product_candidate_id for item in candidates],
        consultation_requirement_ids=[item.requirement_id for item in requirements],
        missing_information=gaps,
        action_plan=actions,
        authority_boundary=registry.authority_boundary,
        source=source,
    )


def apply_transaction_decision_brief(
    case: UnifiedCopilotCase,
    request: TransactionDecisionBriefRequest,
    *,
    registry_path: str | Path | None = None,
) -> tuple[UnifiedCopilotCase, TransactionDecisionBrief, TransactionDecisionBriefOutcome]:
    """Attach the current transaction action plan while preserving other case actions."""

    brief = build_transaction_decision_brief(
        case,
        request,
        registry_path=registry_path,
    )
    retained_actions = [
        item
        for item in case.trade_finance.action_plan
        if not (
            item.source.source_id == brief.source.source_id
            and item.action_id.startswith(f"ACTION-{request.transaction_id}-")
        )
    ]
    updated_domain = case.trade_finance.model_copy(
        update={"action_plan": retained_actions + brief.action_plan}
    )
    updated_case = case.model_copy(update={"trade_finance": updated_domain})
    outcome = TransactionDecisionBriefOutcome(
        case_before_hash=case.case_hash,
        case_after_hash=updated_case.case_hash,
        brief_id=request.brief_id,
        transaction_id=request.transaction_id,
        disposition=brief.disposition,
        action_ids=[item.action_id for item in brief.action_plan],
        missing_information=brief.missing_information,
    )
    return updated_case, brief, outcome
