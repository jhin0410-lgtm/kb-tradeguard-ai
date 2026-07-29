"""Risk-first, mobile-friendly presentation helpers for the V2 assessment UI.

This module is presentation-only. It indexes already governed evidence and turns a
completed deterministic run into compact view models and a self-contained HTML
snapshot. It does not calculate exposure, create findings, alter disposition, or make
institution-specific decisions.
"""

from __future__ import annotations

from html import escape
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from .assessment_app_presentation import disposition_presentation, scenario_narrative
from .assessment_app_support import assessment_summary
from .intelligence.single_transaction_package import SingleTransactionPackageRun


class EvidenceDrawerItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_id: str
    record_type: str
    title: str
    summary: str
    status: str
    source_name: str | None = None
    source_locator: str | None = None
    as_of_date: str | None = None
    linked_reference_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RiskFirstCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    concern_id: str
    rank: int
    severity: str
    category: str
    title: str
    factual_basis: str
    unresolved_facts: list[str] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)


class ActionCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str
    sequence: int
    title: str
    responsible_party: str
    status: str
    rationale: str
    dependency_action_ids: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    supporting_risk_signal_ids: list[str] = Field(default_factory=list)


class RiskFirstSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    disposition: str
    disposition_label: str
    disposition_headline: str
    disposition_explanation: str
    top_risks: list[RiskFirstCard]
    next_actions: list[ActionCard]
    missing_information: list[str]
    evidence_reference_count: int
    completed_stage_count: int
    stage_count: int


def _source_fields(record: Any) -> tuple[str | None, str | None, str | None]:
    source = getattr(record, "source", None)
    if source is None:
        return None, None, None
    as_of_date = getattr(source, "as_of_date", None)
    return (
        getattr(source, "source_name", None),
        getattr(source, "source_locator", None),
        as_of_date.isoformat() if as_of_date is not None else None,
    )


def _item(
    *,
    reference_id: str,
    record_type: str,
    title: str,
    summary: str,
    status: str,
    record: Any | None = None,
    source_name: str | None = None,
    source_locator: str | None = None,
    as_of_date: str | None = None,
    linked_reference_ids: Iterable[str] = (),
    limitations: Iterable[str] = (),
) -> EvidenceDrawerItem:
    if record is not None:
        record_source_name, record_source_locator, record_as_of_date = _source_fields(record)
        source_name = source_name or record_source_name
        source_locator = source_locator or record_source_locator
        as_of_date = as_of_date or record_as_of_date
    return EvidenceDrawerItem(
        reference_id=reference_id,
        record_type=record_type,
        title=title,
        summary=summary,
        status=status,
        source_name=source_name,
        source_locator=source_locator,
        as_of_date=as_of_date,
        linked_reference_ids=list(dict.fromkeys(linked_reference_ids)),
        limitations=list(dict.fromkeys(limitations)),
    )


def build_reference_index(
    run: SingleTransactionPackageRun,
) -> dict[str, list[EvidenceDrawerItem]]:
    """Index governed records by the IDs used in Decision Brief references."""

    case = run.updated_case
    domain = case.trade_finance
    index: dict[str, list[EvidenceDrawerItem]] = {}

    def add(item: EvidenceDrawerItem) -> None:
        index.setdefault(item.reference_id, []).append(item)

    for evidence in case.evidence:
        add(
            _item(
                reference_id=evidence.evidence_id,
                record_type="evidence",
                title=evidence.source_name,
                summary=evidence.excerpt or evidence.evidence_type,
                status=evidence.status,
                source_name=evidence.source_name,
                source_locator=evidence.source_locator,
                linked_reference_ids=evidence.linked_transaction_ids,
                limitations=evidence.warnings,
            )
        )

    for signal in domain.risk_signals:
        linked = (
            signal.evidence_ids
            + signal.calculation_ids
            + signal.country_fact_ids
            + signal.clause_finding_ids
        )
        add(
            _item(
                reference_id=signal.signal_id,
                record_type="risk_signal",
                title=signal.title,
                summary=signal.factual_trigger,
                status=signal.severity,
                record=signal,
                linked_reference_ids=linked,
                limitations=signal.limitations + signal.unresolved_facts,
            )
        )

    for screening in domain.compliance_screenings:
        add(
            _item(
                reference_id=screening.screening_id,
                record_type="compliance_screening",
                title=screening.subject_name,
                summary=(
                    f"{screening.screening_type} · {screening.result} · "
                    f"method={screening.method}"
                ),
                status=screening.record_status,
                record=screening,
                limitations=screening.limitations,
            )
        )

    for fact in domain.country_risk_facts:
        add(
            _item(
                reference_id=fact.fact_id,
                record_type="country_fact",
                title=fact.metric_name,
                summary=fact.interpretation,
                status=fact.record_status,
                record=fact,
                limitations=fact.limitations,
            )
        )

    for counterparty in domain.counterparties:
        add(
            _item(
                reference_id=counterparty.counterparty_id,
                record_type="counterparty",
                title=counterparty.legal_name,
                summary=(
                    f"관계={counterparty.relationship_status} · "
                    f"실사={counterparty.due_diligence_status} · "
                    f"지급이력={counterparty.prior_payment_history}"
                ),
                status=counterparty.record_status,
                record=counterparty,
                limitations=counterparty.limitations,
            )
        )

    for finding in domain.clause_findings:
        add(
            _item(
                reference_id=finding.clause_finding_id,
                record_type="clause_finding",
                title=finding.issue_type,
                summary=finding.failure_path,
                status=finding.severity,
                record=finding,
                linked_reference_ids=finding.evidence_ids + [finding.document_id],
                limitations=finding.limitations,
            )
        )

    for document in domain.trade_documents:
        summary_parts = [document.document_type]
        if document.currency:
            summary_parts.append(document.currency)
        if document.amount is not None:
            summary_parts.append(f"{document.amount}")
        item = _item(
            reference_id=document.document_id,
            record_type="trade_document",
            title=document.document_reference or document.document_id,
            summary=" · ".join(summary_parts),
            status=document.record_status,
            record=document,
            linked_reference_ids=[document.evidence_id] + document.linked_transaction_ids,
            limitations=document.limitations,
        )
        add(item)
        add(item.model_copy(update={"reference_id": document.evidence_id}))

    for calculation in case.calculations.values():
        add(
            _item(
                reference_id=calculation.calculation_id,
                record_type="calculation",
                title=calculation.calculation_name,
                summary=calculation.selected_analysis_basis,
                status="derived",
                source_name=calculation.data_source,
                as_of_date=calculation.as_of_date,
                linked_reference_ids=calculation.source_data_identifiers,
                limitations=calculation.limitations,
            )
        )

    return index


def build_evidence_drawer_items(
    run: SingleTransactionPackageRun,
    reference_ids: Iterable[str],
    *,
    include_linked: bool = True,
) -> list[EvidenceDrawerItem]:
    """Resolve selected references and one linked layer without inventing records."""

    index = build_reference_index(run)
    requested = list(dict.fromkeys(reference_ids))
    items: list[EvidenceDrawerItem] = []
    seen: set[tuple[str, str]] = set()

    def collect(reference_id: str) -> None:
        for item in index.get(reference_id, []):
            key = (item.reference_id, item.record_type)
            if key in seen:
                continue
            seen.add(key)
            items.append(item)

    for reference_id in requested:
        collect(reference_id)

    if include_linked:
        linked = [identifier for item in items for identifier in item.linked_reference_ids]
        for reference_id in linked:
            collect(reference_id)

    return items


def build_risk_first_summary(
    run: SingleTransactionPackageRun,
    *,
    max_risks: int = 3,
    max_actions: int = 3,
) -> RiskFirstSummary:
    """Build the 60-second view without adding an opaque aggregate score."""

    summary = assessment_summary(run)
    brief = run.assessment_result.brief
    presentation = disposition_presentation(brief.disposition)
    risks = [
        RiskFirstCard(
            concern_id=item.concern_id,
            rank=item.rank,
            severity=item.severity,
            category=item.category,
            title=item.title,
            factual_basis=item.factual_basis,
            unresolved_facts=item.unresolved_facts,
            reference_ids=item.source_ids,
        )
        for item in brief.ranked_concerns[:max_risks]
    ]
    actions = [
        ActionCard(
            action_id=item.action_id,
            sequence=item.sequence,
            title=item.title,
            responsible_party=item.responsible_party,
            status=item.status,
            rationale=item.rationale,
            dependency_action_ids=item.dependency_action_ids,
            required_documents=item.required_documents,
            supporting_risk_signal_ids=item.supporting_risk_signal_ids,
        )
        for item in sorted(brief.action_plan, key=lambda record: record.sequence)[:max_actions]
    ]
    references = {
        reference_id for risk in risks for reference_id in risk.reference_ids
    }
    return RiskFirstSummary(
        disposition=brief.disposition,
        disposition_label=summary["disposition_label"],
        disposition_headline=presentation.headline,
        disposition_explanation=presentation.explanation,
        top_risks=risks,
        next_actions=actions,
        missing_information=brief.missing_information,
        evidence_reference_count=len(references),
        completed_stage_count=summary["completed_stage_count"],
        stage_count=summary["stage_count"],
    )


def build_presentation_snapshot_v2(
    run: SingleTransactionPackageRun,
    *,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """Build the mobile and presentation snapshot used by V2 downloads."""

    summary = build_risk_first_summary(run)
    narrative = scenario_narrative(scenario_id)
    return {
        "snapshot_version": "competition-presentation/2.0",
        "view_contract": "risk_first_60_second_brief",
        "scenario_id": scenario_id,
        "scenario_business_problem": narrative.business_problem if narrative else None,
        "scenario_decision_question": narrative.decision_question if narrative else None,
        "pipeline_id": run.assessment_result.pipeline_id,
        "brief_id": run.assessment_result.brief.brief_id,
        "transaction_id": run.assessment_result.transaction_id,
        "input_package_hash": run.input_package_hash,
        "input_case_hash": run.input_case_hash,
        "output_case_hash": run.output_case_hash,
        "disposition": summary.disposition,
        "disposition_label": summary.disposition_label,
        "disposition_headline": summary.disposition_headline,
        "top_risks": [item.model_dump(mode="json") for item in summary.top_risks],
        "next_actions": [item.model_dump(mode="json") for item in summary.next_actions],
        "missing_information": summary.missing_information,
        "evidence_reference_count": summary.evidence_reference_count,
        "stage_statuses": [
            {
                "sequence": item.sequence,
                "stage_name": item.stage_name,
                "status": item.status,
                "generated_record_count": len(item.generated_record_ids),
            }
            for item in run.assessment_result.stage_traces
        ],
        "mobile_compact_query": "?view=compact",
        "authority_boundary": run.assessment_result.authority_boundary,
    }


def render_presentation_snapshot_html(snapshot: dict[str, Any]) -> str:
    """Render a self-contained, offline HTML snapshot for presentation or phone review."""

    risks = snapshot.get("top_risks") or []
    actions = snapshot.get("next_actions") or []
    risk_html = "".join(
        (
            '<article class="risk">'
            f'<span class="badge {escape(str(item.get("severity", "info")))}">'
            f'{escape(str(item.get("severity", "info"))).upper()}</span>'
            f'<h3>{escape(str(item.get("rank", "-")))}. {escape(str(item.get("title", "-")))}</h3>'
            f'<p>{escape(str(item.get("factual_basis", "-")))}</p>'
            f'<small>REF · {escape(", ".join(item.get("reference_ids") or []))}</small>'
            "</article>"
        )
        for item in risks
    ) or '<article class="risk"><h3>표시할 상위 위험 없음</h3></article>'
    action_html = "".join(
        (
            '<li>'
            f'<strong>{escape(str(item.get("sequence", "-")))}. '
            f'{escape(str(item.get("title", "-")))}</strong>'
            f'<span>{escape(str(item.get("responsible_party", "-")))} · '
            f'{escape(str(item.get("status", "-")))}</span>'
            "</li>"
        )
        for item in actions
    ) or "<li>표시할 실행계획 없음</li>"
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KB TradeGuard AI · Presentation Snapshot</title>
<style>
:root{{--navy:#07172d;--blue:#1b63e9;--ink:#172033;--muted:#647084;--line:#dce4ef;--soft:#f5f8fc}}
*{{box-sizing:border-box}} body{{margin:0;background:#edf2f8;color:var(--ink);font-family:Arial,"Noto Sans KR",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:28px}}
.hero{{background:linear-gradient(125deg,#07172d,#103c79 65%,#0d7e95);color:#fff;padding:32px;border-radius:24px}}
.hero small{{letter-spacing:.12em;font-weight:700;opacity:.75}} .hero h1{{margin:10px 0 6px;font-size:34px}}
.hero p{{margin:0;line-height:1.55;opacity:.94}} .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}}
.risk,.panel{{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 8px 24px rgba(8,31,64,.07)}}
.risk h3{{margin:10px 0 8px;font-size:18px}} .risk p{{color:var(--muted);line-height:1.5}} .risk small{{color:#52627a}}
.badge{{display:inline-block;padding:5px 8px;border-radius:999px;font-size:11px;font-weight:800;background:#eef3fa}}
.badge.critical{{background:#fde8e8;color:#a51f2b}} .badge.high{{background:#fff0db;color:#a85c00}}
.panel h2{{margin-top:0}} ul{{padding-left:20px}} li{{margin:12px 0}} li span{{display:block;color:var(--muted);font-size:13px;margin-top:3px}}
.meta{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}} .meta div{{background:var(--soft);padding:12px;border-radius:12px;word-break:break-all}}
footer{{color:var(--muted);font-size:12px;line-height:1.5;margin-top:16px}}
@media(max-width:760px){{main{{padding:12px}}.hero{{padding:22px;border-radius:18px}}.hero h1{{font-size:26px}}.grid,.meta{{grid-template-columns:1fr}}}}
</style>
</head>
<body><main>
<section class="hero"><small>RISK-FIRST 60 SECOND BRIEF</small><h1>KB TradeGuard AI</h1>
<p><strong>{escape(str(snapshot.get("disposition_headline", "-")))}</strong><br>{escape(str(snapshot.get("scenario_decision_question") or "결정론적 거래 사전진단 결과"))}</p></section>
<section class="grid">{risk_html}</section>
<section class="panel"><h2>다음 실행 행동</h2><ol>{action_html}</ol></section>
<section class="panel"><h2>감사 식별자</h2><div class="meta">
<div><strong>Input Package</strong><br>{escape(str(snapshot.get("input_package_hash", "-")))}</div>
<div><strong>Input Case</strong><br>{escape(str(snapshot.get("input_case_hash", "-")))}</div>
<div><strong>Output Case</strong><br>{escape(str(snapshot.get("output_case_hash", "-")))}</div>
</div></section>
<footer>{escape(str(snapshot.get("authority_boundary", "")))}</footer>
</main></body></html>"""
