"""Deterministic Markdown renderer for one transaction assessment result.

The renderer translates already-grounded case records into a reviewable report. It does
not add new risk conclusions, calculate new financial values, approve a transaction, or
replace legal, compliance, bank, or K-SURE review.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..copilot_case import UnifiedCopilotCase
from ..trade_finance_domain import ActionPlanItem, ProductCandidate
from .single_transaction_pipeline import SingleTransactionAssessmentResult

_DISPOSITION_LABELS = {
    "specialist_clearance_required": "전문가 확인 선행 필요",
    "conditions_required_before_commitment": "거래 확정 전 조건 보완 필요",
    "additional_information_required": "추가 정보 필요",
    "review_required": "검토 필요",
    "no_material_screening_flags": "현재 검토자료상 중대한 경보 없음",
}
_SEVERITY_LABELS = {
    "critical": "치명",
    "high": "높음",
    "medium": "보통",
    "low": "낮음",
    "informational": "정보",
}
_STAGE_LABELS = {
    "trade_document_screening": "계약서·L/C 사전검사",
    "document_reconciliation": "문서 간 정합성",
    "transaction_capacity": "거래-재무 감내능력",
    "product_matching": "KB·K-SURE 상담 후보",
    "transaction_decision_brief": "통합 거래 Brief",
}
_STAGE_STATUS_LABELS = {"completed": "완료", "skipped": "건너뜀"}
_ACTION_STATUS_LABELS = {
    "proposed": "제안",
    "ready": "실행 가능",
    "blocked": "선행조건 필요",
    "completed": "완료",
    "rejected": "제외",
}


def _escape_cell(value: Any) -> str:
    if value is None:
        return "-"
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _format_number(value: Any) -> str:
    if value is None:
        return "-"
    try:
        number = Decimal(str(value))
    except Exception:
        return str(value)
    if number == number.to_integral_value():
        return f"{int(number):,}"
    normalized = format(number.normalize(), "f")
    integer, dot, fraction = normalized.partition(".")
    return f"{int(integer):,}{dot}{fraction}" if dot else f"{int(integer):,}"


def _transaction(case: UnifiedCopilotCase, transaction_id: str) -> dict[str, Any]:
    matches = [
        item
        for item in case.approved_transactions
        if str(item.get("transaction_id")) == transaction_id
    ]
    if len(matches) != 1:
        raise ValueError(
            "Markdown report requires exactly one approved transaction matching the assessment"
        )
    return matches[0]


def _selected_products(
    case: UnifiedCopilotCase, result: SingleTransactionAssessmentResult
) -> list[ProductCandidate]:
    selected = set(result.brief.product_candidate_ids)
    return [
        item
        for item in case.trade_finance.product_candidates
        if item.product_candidate_id in selected
    ]


def _action_rows(actions: list[ActionPlanItem]) -> list[str]:
    rows = []
    for action in sorted(actions, key=lambda item: item.sequence):
        dependencies = ", ".join(action.dependency_action_ids) or "없음"
        documents = ", ".join(action.required_documents) or "별도 명시 없음"
        rows.append(
            "| {sequence} | {title} | {party} | {status} | {dependencies} | {documents} |".format(
                sequence=action.sequence,
                title=_escape_cell(action.title),
                party=_escape_cell(action.responsible_party),
                status=_escape_cell(_ACTION_STATUS_LABELS.get(action.status, action.status)),
                dependencies=_escape_cell(dependencies),
                documents=_escape_cell(documents),
            )
        )
    return rows


def render_single_transaction_assessment_markdown(
    case: UnifiedCopilotCase,
    result: SingleTransactionAssessmentResult,
) -> str:
    """Render an audit-linked Korean Markdown report from existing assessment records."""

    if case.case_hash != result.case_after_hash:
        raise ValueError("Report case hash does not match the assessment result output hash")
    transaction = _transaction(case, result.transaction_id)
    brief = result.brief
    selected_products = _selected_products(case, result)
    consultation_ids = set(brief.consultation_requirement_ids)
    consultations = [
        item
        for item in case.trade_finance.consultation_requirements
        if item.requirement_id in consultation_ids
    ]

    lines = [
        "# KB TradeGuard 단일 거래 사전진단 보고서",
        "",
        f"- **Case ID:** `{case.identity.case_id}`",
        f"- **Pipeline ID:** `{result.pipeline_id}`",
        f"- **Pipeline 버전:** `{result.pipeline_version}`",
        f"- **거래 ID:** `{result.transaction_id}`",
        f"- **분석 기준일:** `{case.identity.analysis_as_of_date or '-'}`",
        f"- **출력 Case SHA-256:** `{case.case_hash}`",
        "",
        "> **권한 경계:** " + result.authority_boundary,
        "",
        "## 1. 거래 개요",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 기업 | {_escape_cell(case.identity.company_name or '-')} |",
        f"| 거래방향 | {_escape_cell(transaction.get('transaction_type'))} |",
        f"| 통화 | {_escape_cell(transaction.get('currency'))} |",
        f"| 거래금액 | {_format_number(transaction.get('amount_fc'))} |",
        f"| 예정일 | {_escape_cell(transaction.get('expected_date'))} |",
        "",
        "## 2. 사전진단",
        "",
        f"### {_DISPOSITION_LABELS.get(brief.disposition, brief.disposition)}",
        "",
    ]
    lines.extend(f"- {item}" for item in brief.disposition_rationale)

    lines.extend(
        [
            "",
            "## 3. 우선 확인사항",
            "",
            "| 순위 | 심각도 | 범주 | 확인사항 | 확인된 근거 | 미해결 사실 | 근거 ID |",
            "|---:|---|---|---|---|---|---|",
        ]
    )
    if brief.ranked_concerns:
        for concern in brief.ranked_concerns:
            lines.append(
                "| {rank} | {severity} | {category} | {title} | {basis} | {unresolved} | {sources} |".format(
                    rank=concern.rank,
                    severity=_escape_cell(
                        _SEVERITY_LABELS.get(concern.severity, concern.severity)
                    ),
                    category=_escape_cell(concern.category),
                    title=_escape_cell(concern.title),
                    basis=_escape_cell(concern.factual_basis),
                    unresolved=_escape_cell("; ".join(concern.unresolved_facts) or "없음"),
                    sources=_escape_cell(", ".join(concern.source_ids)),
                )
            )
    else:
        lines.append("| - | - | - | 현재 검토자료에서 표시할 우려사항 없음 | - | - | - |")

    lines.extend(["", "## 4. 부족한 정보", ""])
    if brief.missing_information:
        lines.extend(f"- {item}" for item in brief.missing_information)
    else:
        lines.append("- 현재 최소 Coverage 기준에서 별도 누락정보가 식별되지 않았습니다.")

    lines.extend(["", "## 5. KB·K-SURE 상담 후보", ""])
    if selected_products:
        lines.extend(
            [
                "| 제공기관 | 상품·서비스 | 상태 | 연결된 필요 | 다음 행동 | 후보 ID |",
                "|---|---|---|---|---|---|",
            ]
        )
        for candidate in selected_products:
            lines.append(
                "| {provider} | {name} | {status} | {need} | {action} | `{identifier}` |".format(
                    provider=_escape_cell(candidate.provider),
                    name=_escape_cell(candidate.product_or_service_name),
                    status=_escape_cell(candidate.candidate_status),
                    need=_escape_cell(candidate.matched_need),
                    action=_escape_cell(candidate.next_action),
                    identifier=_escape_cell(candidate.product_candidate_id),
                )
            )
    else:
        lines.append("- 이번 Brief에 선택된 상담 후보가 없습니다.")

    lines.extend(["", "### 상담 시 확인할 조건", ""])
    if consultations:
        for requirement in consultations:
            lines.append(
                f"- **{requirement.consultation_route}** · `{requirement.requirement_id}`: "
                + requirement.purpose
            )
            for question in requirement.questions_to_confirm:
                lines.append(f"  - 확인: {question}")
            for missing in requirement.blocked_by_missing_inputs:
                lines.append(f"  - 선행 입력: {missing}")
    else:
        lines.append("- 선택된 상담 요구사항이 없습니다.")

    lines.extend(
        [
            "",
            "## 6. 실행계획",
            "",
            "| 순서 | 작업 | 담당 | 상태 | 선행 작업 | 준비자료 |",
            "|---:|---|---|---|---|---|",
        ]
    )
    if brief.action_plan:
        lines.extend(_action_rows(brief.action_plan))
    else:
        lines.append("| - | 생성된 실행계획 없음 | - | - | - | - |")

    lines.extend(
        [
            "",
            "## 7. 파이프라인 실행기록",
            "",
            "| 순서 | 단계 | 상태 | 입력 Case hash | 출력 Case hash | 생성 레코드 |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for trace in result.stage_traces:
        lines.append(
            "| {sequence} | {stage} | {status} | `{before}` | `{after}` | {records} |".format(
                sequence=trace.sequence,
                stage=_escape_cell(_STAGE_LABELS.get(trace.stage_name, trace.stage_name)),
                status=_escape_cell(_STAGE_STATUS_LABELS.get(trace.status, trace.status)),
                before=trace.case_before_hash,
                after=trace.case_after_hash,
                records=_escape_cell(", ".join(trace.generated_record_ids) or "없음"),
            )
        )

    lines.extend(
        [
            "",
            "## 8. 근거 및 감사 참조",
            "",
            f"- Country fact IDs: {', '.join(brief.country_fact_ids) or '없음'}",
            f"- Compliance screening IDs: {', '.join(brief.compliance_screening_ids) or '없음'}",
            f"- Calculation IDs: {', '.join(brief.calculation_ids) or '없음'}",
            f"- Product candidate IDs: {', '.join(brief.product_candidate_ids) or '없음'}",
            f"- Consultation requirement IDs: {', '.join(brief.consultation_requirement_ids) or '없음'}",
            f"- Brief source ID: `{brief.source.source_id}`",
            f"- Brief rule hash: `{brief.source.content_hash or '-'}`",
            "",
            "## 9. 제한사항",
            "",
        ]
    )
    limitations = list(dict.fromkeys([brief.authority_boundary, *result.limitations]))
    lines.extend(f"- {item}" for item in limitations)
    lines.extend(
        [
            "",
            "---",
            "이 보고서는 검토된 입력과 결정론적 사전검사 결과를 사람이 검토하기 쉽게 정리한 문서입니다. 거래 승인·거절, 법률의견, 제재·AML 해소, 은행 신용승인, K-SURE 인수승인 또는 실행 가능한 조건 제시가 아닙니다.",
            "",
        ]
    )
    return "\n".join(lines)
