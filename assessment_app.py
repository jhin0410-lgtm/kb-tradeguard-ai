"""Streamlit demo for the governed single-transaction assessment pipeline."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st

from src.assessment_app_presentation import (
    APP_CSS,
    build_presentation_snapshot,
    disposition_presentation,
    scenario_narrative,
)
from src.assessment_app_support import (
    assessment_summary,
    build_audit_bundle_bytes,
    concern_rows,
    package_json_bytes,
    parse_package_json_bytes,
    stage_rows,
)
from src.assessment_live_ai_panel import render_grounded_live_ai_panel
from src.demo_scenarios import (
    DemoScenarioMetadata,
    list_demo_scenarios,
    load_demo_scenario,
)
from src.intelligence.decision_brief_report import (
    render_single_transaction_assessment_markdown,
)
from src.intelligence.finding_review import latest_finding_review_decisions
from src.intelligence.single_transaction_package import (
    SingleTransactionAssessmentPackage,
    SingleTransactionPackageRun,
    run_single_transaction_package,
)

_DISPOSITION_HELP = {
    "specialist_clearance_required": "Critical 경보가 있어 전문가 확인이 선행되어야 합니다.",
    "conditions_required_before_commitment": "High 우려를 완화하거나 거래조건을 보완해야 합니다.",
    "additional_information_required": "최소 Coverage가 부족하며 누락정보를 추정하지 않습니다.",
    "review_required": "중간·낮은 수준의 검토사항이 남아 있습니다.",
    "no_material_screening_flags": "현재 검토자료에서 중대한 경보가 없다는 뜻이며 승인이나 안전 인증은 아닙니다.",
}
_STAGE_LABELS = {
    "trade_document_screening": "계약서·L/C 사전검사",
    "document_reconciliation": "문서 간 정합성",
    "transaction_capacity": "거래-재무 감내능력",
    "product_matching": "KB·K-SURE 상담 후보",
    "transaction_decision_brief": "통합 거래 Brief",
}
_SEVERITY_LABELS = {
    "critical": "치명",
    "high": "높음",
    "medium": "보통",
    "low": "낮음",
    "informational": "정보",
}
_STATUS_LABELS = {
    "completed": "완료",
    "skipped": "명시적 생략",
    "failed": "중단",
}


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _format_money(value: Any) -> str:
    if value is None:
        return "-"
    number = Decimal(str(value))
    return f"₩{number:,.0f}"


def _render_scenario_card(metadata: DemoScenarioMetadata) -> None:
    narrative = scenario_narrative(metadata.scenario_id)
    if narrative is None:
        return
    st.markdown(
        f"""
        <div class="tg-scenario-card">
          <h4>{metadata.highlight}</h4>
          <p><strong>업무 문제</strong> · {narrative.business_problem}</p>
          <p><strong>결정 질문</strong> · {narrative.decision_question}</p>
          <p><strong>심사 포인트</strong> · {narrative.judge_watch}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("추천 시연 동선", expanded=False):
        for index, step in enumerate(narrative.walkthrough, start=1):
            st.write(f"**{index}.** {step}")


def _select_package() -> tuple[SingleTransactionAssessmentPackage | None, str | None]:
    scenarios = list_demo_scenarios()
    by_title = {item.title: item for item in scenarios}
    default_index = next(
        (
            index
            for index, item in enumerate(scenarios)
            if item.scenario_id == "oa_high_risk"
        ),
        0,
    )

    with st.sidebar:
        st.markdown("## 데모 입력")
        mode = st.radio(
            "분석 패키지",
            ["대표 시나리오", "JSON 패키지 업로드"],
            label_visibility="collapsed",
        )
        if mode == "대표 시나리오":
            title = st.selectbox(
                "시나리오",
                list(by_title),
                index=default_index,
                help="메인 시연에는 O/A 90일 고위험 수출 시나리오를 권장합니다.",
            )
            metadata = by_title[title]
            st.caption(metadata.summary)
            st.caption("데이터 모드 · " + " · ".join(metadata.source_modes))
            package = load_demo_scenario(metadata.scenario_id)
            with st.expander("입력 Package 메모"):
                for note in package.notes:
                    st.write(f"- {note}")
            return package, metadata.scenario_id

        uploaded = st.file_uploader("Assessment package JSON", type=["json"])
        st.caption(
            "검토된 단일 거래 Package만 허용합니다. 입력값은 자동 보정하거나 추정하지 않습니다."
        )
        if uploaded is None:
            return None, None
        try:
            package = parse_package_json_bytes(
                uploaded.getvalue(), source_name=uploaded.name
            )
        except ValueError as exc:
            st.error(str(exc))
            return None, None
        return package, uploaded.name


def _render_header() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <section class="tg-hero">
          <div class="tg-eyebrow">DETERMINISTIC TRADE FINANCE COPILOT · COMPETITION PROTOTYPE</div>
          <h1>KB TradeGuard AI</h1>
          <p>기업정보·무역문서·거래조건·바이어·국가위험·외환 및 재무노출을 단일 거래 단위로 결합해, 거래 전 위험과 금융·보험·보증 상담 준비사항을 근거 기반으로 제시합니다.</p>
        </section>
        <div class="tg-trust-strip">
          <div class="tg-trust-item"><strong>결정론적 판단 기준</strong><span>룰·계산·검증된 입력이 기준이며 AI가 Finding을 만들거나 바꾸지 않습니다.</span></div>
          <div class="tg-trust-item"><strong>근거 ID 연결</strong><span>Finding·RiskSignal·Calculation·Evidence를 문장과 Action에 연결합니다.</span></div>
          <div class="tg-trust-item"><strong>Human Review Overlay</strong><span>전문가 확인·기각·추가정보 요청을 원본 Finding과 분리해 기록합니다.</span></div>
          <div class="tg-trust-item"><strong>감사 가능한 산출물</strong><span>Case hash, Stage Trace, Markdown·JSON·Manifest·ZIP을 함께 제공합니다.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "본 프로토타입은 거래 승인·거절, 법률의견, 제재·AML 해소, 은행 신용승인, "
        "실행 금리·한도 또는 K-SURE 인수승인을 제공하지 않습니다."
    )


def _run_controls(
    package: SingleTransactionAssessmentPackage | None,
    source_key: str | None,
) -> None:
    with st.sidebar:
        st.markdown("## 실행·검증")
        if package is not None:
            st.caption(f"Case hash · `{package.case.case_hash[:16]}…`")
            st.download_button(
                "입력 Package 다운로드",
                data=package_json_bytes(package),
                file_name=f"{source_key or 'assessment'}-input-package.json",
                mime="application/json",
                use_container_width=True,
            )
        run_clicked = st.button(
            "5단계 거래 사전진단 실행",
            type="primary",
            disabled=package is None,
            use_container_width=True,
        )
        st.caption("같은 Package는 같은 결정론적 Case·Brief 결과를 생성합니다.")

    if run_clicked and package is not None:
        try:
            with st.spinner("문서·정합성·재무·상품·Brief 파이프라인을 실행합니다."):
                run = run_single_transaction_package(package)
        except Exception as exc:
            st.session_state.pop("assessment_run", None)
            st.session_state.pop("assessment_package", None)
            st.error(f"평가 실행이 중단되었습니다: {exc}")
        else:
            st.session_state["assessment_run"] = run
            st.session_state["assessment_package"] = package
            st.session_state["assessment_source_key"] = source_key
            for key in (
                "live_ai_packet",
                "live_ai_execution",
                "live_ai_error",
                "live_ai_case_hash",
            ):
                st.session_state.pop(key, None)


def _render_verdict(run: SingleTransactionPackageRun) -> None:
    presentation = disposition_presentation(
        run.assessment_result.brief.disposition
    )
    st.markdown(
        f"""
        <section class="tg-verdict" data-tone="{presentation.tone}">
          <div class="label">{presentation.eyebrow}</div>
          <h3>{presentation.headline}</h3>
          <p>{presentation.explanation}<br><strong>다음 확인</strong> · {presentation.next_focus}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_stage_stepper(run: SingleTransactionPackageRun) -> None:
    blocks = []
    for trace in run.assessment_result.stage_traces:
        label = _STAGE_LABELS.get(trace.stage_name, trace.stage_name)
        status = _STATUS_LABELS.get(trace.status, trace.status)
        blocks.append(
            f'<div class="tg-step" data-status="{trace.status}">'
            f"<strong>{trace.sequence}. {label}</strong><span>{status} · 생성 {len(trace.generated_record_ids)}건</span></div>"
        )
    st.markdown(
        '<div class="tg-stepper">' + "".join(blocks) + "</div>",
        unsafe_allow_html=True,
    )


def _render_metrics(run: SingleTransactionPackageRun) -> None:
    summary = assessment_summary(run)
    _render_verdict(run)
    columns = st.columns(5)
    columns[0].metric("사전진단", summary["disposition_label"])
    columns[1].metric("Critical·High", summary["critical_high_concerns"])
    columns[2].metric("누락정보", summary["missing_information_count"])
    columns[3].metric("상담 후보", summary["product_candidate_count"])
    columns[4].metric(
        "Pipeline",
        f"{summary['completed_stage_count']}/{summary['stage_count']} 완료",
    )
    st.caption(
        _DISPOSITION_HELP.get(summary["disposition"], summary["disposition"])
    )
    _render_stage_stepper(run)


def _render_executive_snapshot(run: SingleTransactionPackageRun) -> None:
    brief = run.assessment_result.brief
    top_concern = brief.ranked_concerns[0] if brief.ranked_concerns else None
    actions = sorted(brief.action_plan, key=lambda item: item.sequence)
    first_action = actions[0] if actions else None

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown("#### 가장 먼저 볼 위험")
            if top_concern is None:
                st.success("현재 Brief에 순위화된 우려사항이 없습니다.")
            else:
                st.markdown(
                    f"**{_SEVERITY_LABELS.get(top_concern.severity, top_concern.severity)} · {top_concern.title}**"
                )
                st.write(top_concern.factual_basis)
                st.caption("근거 · " + ", ".join(top_concern.source_ids))
    with right:
        with st.container(border=True):
            st.markdown("#### 첫 번째 실행 행동")
            if first_action is None:
                st.info("별도 실행계획이 생성되지 않았습니다.")
            else:
                st.markdown(f"**{first_action.sequence}. {first_action.title}**")
                st.write(first_action.rationale)
                st.caption(
                    f"담당 · {first_action.responsible_party} · Action ID · {first_action.action_id}"
                )


def _render_summary_tab(run: SingleTransactionPackageRun) -> None:
    case = run.updated_case
    result = run.assessment_result
    transaction = next(
        item
        for item in case.approved_transactions
        if str(item.get("transaction_id")) == result.transaction_id
    )
    _render_executive_snapshot(run)

    left, right = st.columns([1, 1])
    with left:
        st.subheader("거래 개요")
        st.dataframe(
            pd.DataFrame(
                [
                    {"항목": "기업", "값": case.identity.company_name or "-"},
                    {"항목": "거래 ID", "값": result.transaction_id},
                    {"항목": "거래방향", "값": transaction.get("transaction_type")},
                    {"항목": "통화", "값": transaction.get("currency")},
                    {"항목": "금액", "값": transaction.get("amount_fc")},
                    {"항목": "예정일", "값": transaction.get("expected_date")},
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    with right:
        st.subheader("판정 근거와 Coverage")
        for item in result.brief.disposition_rationale:
            st.write(f"- {item}")
        st.markdown("**부족한 정보**")
        if result.brief.missing_information:
            for item in result.brief.missing_information:
                st.write(f"- {item}")
        else:
            st.write("- 최소 Coverage 기준에서 별도 누락정보가 없습니다.")

    st.subheader("상세 실행 Trace")
    stages = pd.DataFrame(stage_rows(run))
    stages["단계"] = stages["단계"].map(
        lambda value: _STAGE_LABELS.get(value, value)
    )
    stages["상태"] = stages["상태"].map(
        lambda value: _STATUS_LABELS.get(value, value)
    )
    st.dataframe(stages, hide_index=True, use_container_width=True)


def _render_risk_tab(run: SingleTransactionPackageRun) -> None:
    rows = concern_rows(run)
    if rows:
        frame = pd.DataFrame(rows)
        frame["심각도"] = frame["심각도"].map(
            lambda value: _SEVERITY_LABELS.get(value, value)
        )
        st.dataframe(frame, hide_index=True, use_container_width=True)
        severity = pd.DataFrame(
            [
                {
                    "심각도": _SEVERITY_LABELS.get(label, label),
                    "건수": count,
                }
                for label, count in assessment_summary(run)["severity_counts"].items()
                if count
            ]
        )
        if not severity.empty:
            st.subheader("우려 심각도 분포")
            st.bar_chart(severity.set_index("심각도"))
    else:
        st.success("현재 검토자료에서 표시할 우려사항이 없습니다.")

    st.subheader("문장별 근거 연결")
    st.caption("보고서와 선택형 Live AI는 아래 Reference ID 범위만 사용합니다.")
    references = []
    for concern in run.assessment_result.brief.ranked_concerns:
        for source_id in concern.source_ids:
            references.append(
                {
                    "문장": concern.title,
                    "Reference ID": source_id,
                    "유형": concern.source_type,
                }
            )
    if references:
        st.dataframe(pd.DataFrame(references), hide_index=True, use_container_width=True)
    else:
        st.info("표시할 Concern Reference가 없습니다.")


def _render_document_tab(run: SingleTransactionPackageRun) -> None:
    case = run.updated_case
    documents = [
        {
            "문서 ID": item.document_id,
            "Evidence ID": item.evidence_id,
            "종류": item.document_type,
            "통화": item.currency,
            "금액": item.amount,
            "발행일": item.issue_date,
            "선적일": item.shipment_date,
            "만료일": item.expiry_date,
            "상태": item.record_status,
        }
        for item in case.trade_finance.trade_documents
    ]
    if documents:
        st.dataframe(pd.DataFrame(documents), hide_index=True, use_container_width=True)
    else:
        st.warning("연결된 검토 문서가 없습니다.")

    st.subheader("조항 Finding 및 전문가 검토")
    reviews = latest_finding_review_decisions(case)
    findings = [
        {
            "Finding ID": item.clause_finding_id,
            "문서 ID": item.document_id,
            "심각도": _SEVERITY_LABELS.get(item.severity, item.severity),
            "위치": item.clause_locator,
            "발췌·필드": item.clause_excerpt,
            "전문가": ", ".join(item.specialist_review),
            "검토상태": (
                reviews[item.clause_finding_id].decision
                if item.clause_finding_id in reviews
                else "unreviewed"
            ),
        }
        for item in case.trade_finance.clause_findings
    ]
    if findings:
        st.dataframe(pd.DataFrame(findings), hide_index=True, use_container_width=True)
    else:
        st.success("현재 검토문서에서 생성된 조항 Finding이 없습니다.")


def _capacity_metrics(run: SingleTransactionPackageRun) -> dict[str, Any]:
    for calculation in run.updated_case.calculations.values():
        if calculation.calculation_name == "Transaction financial capacity assessment":
            return dict(calculation.result.get("metrics") or {})
    return {}


def _render_financial_tab(run: SingleTransactionPackageRun) -> None:
    statements = run.updated_case.trade_finance.financial_statements
    if statements:
        statement = statements[0]
        st.subheader("재무 Snapshot")
        st.dataframe(
            pd.DataFrame(
                [
                    {"항목": "현금및현금성자산", "금액": _format_money(statement.cash_and_cash_equivalents)},
                    {"항목": "단기금융자산", "금액": _format_money(statement.short_term_financial_assets)},
                    {"항목": "유동자산", "금액": _format_money(statement.current_assets)},
                    {"항목": "유동부채", "금액": _format_money(statement.current_liabilities)},
                    {"항목": "자기자본", "금액": _format_money(statement.equity)},
                    {"항목": "연 매출", "금액": _format_money(statement.revenue)},
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )

    metrics = _capacity_metrics(run)
    if not metrics:
        st.warning("거래-재무 감내능력 계산이 실행되지 않았습니다.")
        return
    labels = {
        "gross_transaction_krw": "거래 원화환산액",
        "identified_liquid_assets_krw": "식별 유동성",
        "unprotected_exposure_krw": "보호되지 않은 노출",
        "pre_shipment_funding_need_krw": "선적 전 필요자금",
        "post_funding_liquidity_krw": "자금투입 후 유동성",
    }
    chart = pd.DataFrame(
        [
            {"항목": labels[key], "금액": metrics.get(key)}
            for key in labels
            if metrics.get(key) is not None
        ]
    )
    if not chart.empty:
        st.subheader("거래 규모와 유동성 비교")
        st.bar_chart(chart.set_index("항목"))

    ratio_rows = [
        {"지표": key, "값(%)": value}
        for key, value in metrics.items()
        if key.endswith("_pct") and value is not None
    ]
    if ratio_rows:
        st.subheader("구조적 비교지표")
        st.dataframe(pd.DataFrame(ratio_rows), hide_index=True, use_container_width=True)


def _render_product_tab(run: SingleTransactionPackageRun) -> None:
    selected = set(run.assessment_result.brief.product_candidate_ids)
    candidates = [
        item
        for item in run.updated_case.trade_finance.product_candidates
        if item.product_candidate_id in selected
    ]
    st.markdown(
        '<div class="tg-callout"><strong>상담 후보의 의미</strong><p>현재 입력된 거래 목적과 필요를 기준으로 상담할 가치가 있는 공개 상품·서비스 후보입니다. 적격성, 승인, 금리, 한도 또는 보험 인수 확정이 아닙니다.</p></div>',
        unsafe_allow_html=True,
    )
    if candidates:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "기관": item.provider,
                        "상품·서비스": item.product_or_service_name,
                        "상태": item.candidate_status,
                        "연결된 필요": item.matched_need,
                        "미확인 조건": "; ".join(item.unresolved_eligibility_conditions),
                        "다음 행동": item.next_action,
                        "후보 ID": item.product_candidate_id,
                    }
                    for item in candidates
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("이번 Brief에 선택된 상담 후보가 없습니다.")


def _render_action_tab(run: SingleTransactionPackageRun) -> None:
    actions = sorted(run.assessment_result.brief.action_plan, key=lambda item: item.sequence)
    if not actions:
        st.info("생성된 실행계획이 없습니다.")
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "순서": item.sequence,
                    "작업": item.title,
                    "담당": item.responsible_party,
                    "상태": item.status,
                    "선행 Action": ", ".join(item.dependency_action_ids),
                    "필요서류": "; ".join(item.required_documents),
                    "근거 RiskSignal": ", ".join(item.supporting_risk_signal_ids),
                }
                for item in actions
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.subheader("의존관계와 실행 이유")
    for item in actions:
        with st.container(border=True):
            dependencies = ", ".join(item.dependency_action_ids) or "없음"
            st.markdown(f"**{item.sequence}. {item.title}**")
            st.write(item.rationale)
            st.caption(
                f"담당 · {item.responsible_party} · 선행 Action · {dependencies} · Action ID · {item.action_id}"
            )


def _render_audit_tab(
    run: SingleTransactionPackageRun,
    package: SingleTransactionAssessmentPackage,
    source_key: str | None,
) -> None:
    st.markdown(
        '<div class="tg-callout"><strong>재현성 핵심</strong><p>입력 Package hash, 입력 Case hash와 출력 Case hash를 함께 보존해 동일 입력과 산출물의 변경 여부를 확인합니다.</p></div>',
        unsafe_allow_html=True,
    )
    st.code(
        f"Input package  {run.input_package_hash}\n"
        f"Input case     {run.input_case_hash}\n"
        f"Output case    {run.output_case_hash}",
        language="text",
    )
    report = render_single_transaction_assessment_markdown(
        run.updated_case, run.assessment_result
    )
    bundle = build_audit_bundle_bytes(run, package=package)
    snapshot = build_presentation_snapshot(run, scenario_id=source_key)
    col1, col2, col3, col4 = st.columns(4)
    col1.download_button(
        "Markdown 보고서",
        data=report.encode("utf-8"),
        file_name="decision_brief.md",
        mime="text/markdown",
        use_container_width=True,
    )
    col2.download_button(
        "Decision Brief JSON",
        data=_json_text(run.assessment_result.brief.model_dump(mode="json")).encode("utf-8"),
        file_name="decision_brief.json",
        mime="application/json",
        use_container_width=True,
    )
    col3.download_button(
        "감사 패키지 ZIP",
        data=bundle,
        file_name="kb-tradeguard-audit-package.zip",
        mime="application/zip",
        use_container_width=True,
    )
    col4.download_button(
        "발표 Snapshot",
        data=_json_text(snapshot).encode("utf-8"),
        file_name="competition-presentation-snapshot.json",
        mime="application/json",
        use_container_width=True,
    )
    with st.expander("Audit summary"):
        st.json(run.audit_summary)
    with st.expander("결정론적 Markdown 미리보기"):
        st.markdown(report)


def _render_results(
    run: SingleTransactionPackageRun,
    package: SingleTransactionAssessmentPackage,
    source_key: str | None,
) -> None:
    _render_metrics(run)
    tabs = st.tabs(
        [
            "① 요약",
            "② 위험·근거",
            "③ 문서",
            "④ 재무",
            "⑤ 상담 후보",
            "⑥ 실행계획",
            "⑦ 감사·다운로드",
            "⑧ 선택형 Live AI",
        ]
    )
    with tabs[0]:
        _render_summary_tab(run)
    with tabs[1]:
        _render_risk_tab(run)
    with tabs[2]:
        _render_document_tab(run)
    with tabs[3]:
        _render_financial_tab(run)
    with tabs[4]:
        _render_product_tab(run)
    with tabs[5]:
        _render_action_tab(run)
    with tabs[6]:
        _render_audit_tab(run, package, source_key)
    with tabs[7]:
        render_grounded_live_ai_panel(run)


def _render_landing(source_key: str | None) -> None:
    metadata = next(
        (
            item
            for item in list_demo_scenarios()
            if item.scenario_id == source_key
        ),
        None,
    )
    if metadata is not None:
        _render_scenario_card(metadata)

    st.markdown("### 3분 시연 흐름")
    columns = st.columns(3)
    with columns[0]:
        with st.container(border=True):
            st.markdown("#### 1 · 거래 입력")
            st.write("대표 합성 시나리오 또는 검토된 단일 거래 JSON Package를 선택합니다.")
    with columns[1]:
        with st.container(border=True):
            st.markdown("#### 2 · 5단계 진단")
            st.write("문서 → 정합성 → 재무감내 → 상담 후보 → 통합 Brief를 결정론적으로 실행합니다.")
    with columns[2]:
        with st.container(border=True):
            st.markdown("#### 3 · 행동과 감사")
            st.write("담당·선행조건이 있는 Action Plan과 hash 기반 Markdown·JSON·ZIP을 확인합니다.")

    st.info(
        "사이드바의 ‘5단계 거래 사전진단 실행’을 누르면 결과 화면으로 전환됩니다. "
        "메인 발표에는 O/A 90일 고위험 수출 시나리오가 선택되어 있습니다."
    )


def main() -> None:
    st.set_page_config(
        page_title="KB TradeGuard Assessment",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _render_header()
    package, source_key = _select_package()
    _run_controls(package, source_key)

    run = st.session_state.get("assessment_run")
    executed_package = st.session_state.get("assessment_package")
    executed_source_key = st.session_state.get("assessment_source_key")
    if run is None or executed_package is None:
        _render_landing(source_key)
        return
    _render_results(run, executed_package, executed_source_key)


if __name__ == "__main__":
    main()
