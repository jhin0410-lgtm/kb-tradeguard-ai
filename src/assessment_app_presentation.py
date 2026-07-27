"""Presentation-only models for the competition assessment application.

This module contains no trade-finance rules or calculations.  It turns already governed
results into stable Korean labels, judge-facing narratives, and a downloadable presentation
snapshot without changing the underlying assessment records.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .assessment_app_support import assessment_summary
from .intelligence.single_transaction_package import SingleTransactionPackageRun


APP_CSS = """
<style>
:root {
  --tg-navy: #091a33;
  --tg-blue: #1463ff;
  --tg-cyan: #17b7c8;
  --tg-ink: #162033;
  --tg-muted: #5e6b7d;
  --tg-border: #dce4ef;
  --tg-soft: #f5f8fc;
}
.block-container {padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1440px;}
[data-testid="stSidebar"] {border-right: 1px solid var(--tg-border);}
.tg-hero {
  padding: 2rem 2.2rem;
  border-radius: 22px;
  color: white;
  background: linear-gradient(125deg, #07172d 0%, #103c79 62%, #0d7e95 100%);
  box-shadow: 0 16px 40px rgba(8, 31, 64, 0.18);
  margin-bottom: 1rem;
}
.tg-eyebrow {font-size: .78rem; letter-spacing: .14em; font-weight: 800; opacity: .8;}
.tg-hero h1 {font-size: 2.2rem; line-height: 1.2; margin: .5rem 0 .65rem;}
.tg-hero p {font-size: 1.03rem; line-height: 1.65; max-width: 970px; margin: 0; opacity: .93;}
.tg-trust-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: .7rem;
  margin: .85rem 0 1.2rem;
}
.tg-trust-item {
  border: 1px solid var(--tg-border);
  border-radius: 14px;
  background: white;
  padding: .85rem 1rem;
  min-height: 72px;
}
.tg-trust-item strong {display: block; color: var(--tg-ink); font-size: .93rem; margin-bottom: .25rem;}
.tg-trust-item span {color: var(--tg-muted); font-size: .8rem; line-height: 1.4;}
.tg-scenario-card {
  padding: 1rem 1.05rem;
  border: 1px solid var(--tg-border);
  border-left: 5px solid var(--tg-blue);
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #f7faff 100%);
  margin: .55rem 0 .75rem;
}
.tg-scenario-card h4 {margin: 0 0 .35rem; color: var(--tg-ink);}
.tg-scenario-card p {margin: .18rem 0; color: var(--tg-muted); font-size: .88rem; line-height: 1.5;}
.tg-verdict {
  border-radius: 17px;
  padding: 1.15rem 1.3rem;
  margin: .4rem 0 1rem;
  border: 1px solid var(--tg-border);
  background: white;
}
.tg-verdict[data-tone="critical"] {border-left: 7px solid #c22b35; background: #fff7f7;}
.tg-verdict[data-tone="warning"] {border-left: 7px solid #d98300; background: #fffaf1;}
.tg-verdict[data-tone="info"] {border-left: 7px solid #1463ff; background: #f4f8ff;}
.tg-verdict[data-tone="clear"] {border-left: 7px solid #16845b; background: #f3fbf7;}
.tg-verdict .label {font-size: .76rem; letter-spacing: .08em; font-weight: 800; color: var(--tg-muted);}
.tg-verdict h3 {margin: .28rem 0 .35rem; color: var(--tg-ink);}
.tg-verdict p {margin: 0; color: var(--tg-muted); line-height: 1.55;}
.tg-stepper {display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .55rem; margin: .7rem 0 1.1rem;}
.tg-step {border: 1px solid var(--tg-border); border-radius: 12px; padding: .72rem .75rem; background: white;}
.tg-step strong {display: block; font-size: .82rem; color: var(--tg-ink); margin-bottom: .22rem;}
.tg-step span {font-size: .74rem; color: var(--tg-muted);}
.tg-step[data-status="completed"] {border-color: #9dd9c2; background: #f3fbf7;}
.tg-step[data-status="skipped"] {border-color: #d8dee8; background: #f7f8fa;}
.tg-callout {padding: 1rem 1.1rem; border: 1px solid var(--tg-border); border-radius: 14px; background: var(--tg-soft);}
.tg-callout strong {color: var(--tg-ink);}
.tg-callout p {margin: .3rem 0 0; color: var(--tg-muted); line-height: 1.55;}
@media (max-width: 900px) {
  .tg-trust-strip, .tg-stepper {grid-template-columns: 1fr 1fr;}
  .tg-hero h1 {font-size: 1.7rem;}
}
</style>
"""


class ScenarioNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str
    business_problem: str
    decision_question: str
    judge_watch: str
    walkthrough: list[str] = Field(min_length=3, max_length=5)


class DispositionPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    disposition: str
    tone: str
    eyebrow: str
    headline: str
    explanation: str
    next_focus: str


_SCENARIO_NARRATIVES = {
    "missing_information": ScenarioNarrative(
        scenario_id="missing_information",
        business_problem="최소 거래자료조차 갖춰지지 않은 초기 문의에서 시스템이 값을 지어내는 위험",
        decision_question="무엇을 분석할 수 없으며 어떤 자료를 먼저 받아야 하는가?",
        judge_watch="1~4단계를 명시적으로 건너뛰고 누락정보와 후속 행동만 생성하는 fail-closed 동작",
        walkthrough=[
            "입력 Coverage가 부족한 Package를 선택합니다.",
            "5단계 Trace에서 생략 사유를 확인합니다.",
            "누락정보와 요청자료가 임의 추정 없이 생성되는지 봅니다.",
        ],
    ),
    "oa_high_risk": ScenarioNarrative(
        scenario_id="oa_high_risk",
        business_problem="신규 해외 바이어와 O/A 90일 거래를 수주했지만 문서 불일치와 선적 전 자금부담이 동시에 존재",
        decision_question="거래 확정 전에 어떤 조건을 보완하고 어떤 금융·보험 상담을 준비해야 하는가?",
        judge_watch="바이어·문서·재무감내·상담 후보를 하나의 거래 Brief와 의존형 Action Plan으로 연결",
        walkthrough=[
            "요약에서 조건 보완 필요 판정과 Critical·High 건수를 확인합니다.",
            "위험·문서 탭에서 통화·금액 불일치와 계약조건 근거 ID를 확인합니다.",
            "재무·상품 탭에서 자금부담과 상담 후보를 비교합니다.",
            "실행계획과 감사 ZIP으로 검토 가능한 결과물을 확인합니다.",
        ],
    ),
    "complex_lc": ScenarioNarrative(
        scenario_id="complex_lc",
        business_problem="Acceptance L/C의 유효기일·제시기간·바이어 통제서류·인수주체가 서로 충돌하거나 불완전",
        decision_question="선적 전에 어떤 조항을 은행·법무·물류 전문가에게 넘겨야 하는가?",
        judge_watch="Sight·Usance·Acceptance를 분리하고 Critical 조항을 전문가 확인 대상으로 남기는 구조",
        walkthrough=[
            "전문가 확인 선행 필요 판정을 확인합니다.",
            "문서 탭에서 L/C Finding과 specialist role을 확인합니다.",
            "문장별 Reference ID와 보고서 근거 연결을 확인합니다.",
        ],
    ),
    "reviewed_clean": ScenarioNarrative(
        scenario_id="reviewed_clean",
        business_problem="충분한 자료가 있는 거래에서도 시스템이 무조건 경고를 생성하면 실무 신뢰를 잃는 문제",
        decision_question="현재 검토자료에서 중대한 사전검사 경보가 실제로 없는가?",
        judge_watch="정상 근접 입력에서 no-material-screening-flags를 내되 승인·안전 인증으로 과장하지 않는 경계",
        walkthrough=[
            "중대한 경보 없음 판정을 확인합니다.",
            "문서 정합성·바이어 실사·재무 Coverage가 갖춰졌는지 확인합니다.",
            "권한 경계 문구가 승인 표현을 차단하는지 확인합니다.",
        ],
    ),
}


_DISPOSITION_PRESENTATIONS = {
    "specialist_clearance_required": DispositionPresentation(
        disposition="specialist_clearance_required",
        tone="critical",
        eyebrow="SPECIALIST GATE",
        headline="전문가 확인이 선행되어야 합니다",
        explanation="Critical 사전검사 경보가 있어 거래조건 확정이나 선적 진행 전에 지정 전문가 검토가 필요합니다.",
        next_focus="Critical Finding, 담당 전문영역, 선행 Action과 연결 근거를 먼저 확인하십시오.",
    ),
    "conditions_required_before_commitment": DispositionPresentation(
        disposition="conditions_required_before_commitment",
        tone="warning",
        eyebrow="CONDITIONS BEFORE COMMITMENT",
        headline="거래 확정 전 조건 보완이 필요합니다",
        explanation="확인된 High 우려와 자금·문서 조건을 완화한 뒤 거래 확정 여부를 다시 검토해야 합니다.",
        next_focus="상위 우려, 자금부담, 상담 후보와 의존형 Action Plan을 순서대로 확인하십시오.",
    ),
    "additional_information_required": DispositionPresentation(
        disposition="additional_information_required",
        tone="info",
        eyebrow="EVIDENCE REQUIRED",
        headline="추가 정보가 있어야 분석을 진행할 수 있습니다",
        explanation="최소 Coverage가 부족하므로 누락값을 추정하지 않고 필요한 자료와 후속 확인사항을 제시합니다.",
        next_focus="생략된 단계의 이유와 부족한 정보 목록을 먼저 확인하십시오.",
    ),
    "review_required": DispositionPresentation(
        disposition="review_required",
        tone="info",
        eyebrow="REVIEW QUEUE",
        headline="검토사항이 남아 있습니다",
        explanation="중간 또는 낮은 수준의 확인사항이 남아 있어 담당자의 검토와 기록이 필요합니다.",
        next_focus="남은 Finding과 미해결 사실을 확인하십시오.",
    ),
    "no_material_screening_flags": DispositionPresentation(
        disposition="no_material_screening_flags",
        tone="clear",
        eyebrow="NO MATERIAL SCREENING FLAGS",
        headline="현재 검토자료에서 중대한 경보가 확인되지 않았습니다",
        explanation="이는 입력된 검토자료 범위의 사전검사 결과이며 거래 승인, 안전 인증 또는 적격성 확정이 아닙니다.",
        next_focus="Coverage, 권한 경계와 감사 기록을 함께 확인하십시오.",
    ),
}


def scenario_narrative(scenario_id: str | None) -> ScenarioNarrative | None:
    if scenario_id is None:
        return None
    return _SCENARIO_NARRATIVES.get(scenario_id)


def disposition_presentation(disposition: str) -> DispositionPresentation:
    return _DISPOSITION_PRESENTATIONS.get(
        disposition,
        DispositionPresentation(
            disposition=disposition,
            tone="info",
            eyebrow="DETERMINISTIC ASSESSMENT",
            headline=disposition,
            explanation="결정론적 평가 결과를 확인하십시오.",
            next_focus="근거와 제한사항을 함께 확인하십시오.",
        ),
    )


def build_presentation_snapshot(
    run: SingleTransactionPackageRun,
    *,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """Build a compact, deterministic snapshot for presentation and screenshot review."""

    summary = assessment_summary(run)
    brief = run.assessment_result.brief
    narrative = scenario_narrative(scenario_id)
    top_concern = brief.ranked_concerns[0] if brief.ranked_concerns else None
    first_action = (
        sorted(brief.action_plan, key=lambda item: item.sequence)[0]
        if brief.action_plan
        else None
    )
    return {
        "snapshot_version": "competition-presentation/1.0",
        "scenario_id": scenario_id,
        "scenario_business_problem": narrative.business_problem if narrative else None,
        "pipeline_id": run.assessment_result.pipeline_id,
        "brief_id": brief.brief_id,
        "transaction_id": run.assessment_result.transaction_id,
        "input_package_hash": run.input_package_hash,
        "input_case_hash": run.input_case_hash,
        "output_case_hash": run.output_case_hash,
        "disposition": summary["disposition"],
        "disposition_label": summary["disposition_label"],
        "critical_high_concern_count": summary["critical_high_concerns"],
        "missing_information_count": summary["missing_information_count"],
        "product_candidate_count": summary["product_candidate_count"],
        "stage_statuses": [
            {
                "sequence": item.sequence,
                "stage_name": item.stage_name,
                "status": item.status,
            }
            for item in run.assessment_result.stage_traces
        ],
        "top_concern": (
            {
                "title": top_concern.title,
                "severity": top_concern.severity,
                "reference_ids": top_concern.source_ids,
            }
            if top_concern
            else None
        ),
        "first_action": (
            {
                "action_id": first_action.action_id,
                "title": first_action.title,
                "responsible_party": first_action.responsible_party,
            }
            if first_action
            else None
        ),
        "authority_boundary": run.assessment_result.authority_boundary,
    }
