"""Streamlit demo for the governed single-transaction assessment pipeline."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st

from src.assessment_app_support import (
    assessment_summary,
    build_audit_bundle_bytes,
    concern_rows,
    disposition_label,
    package_json_bytes,
    parse_package_json_bytes,
    stage_rows,
)
from src.demo_scenarios import list_demo_scenarios, load_demo_scenario
from src.intelligence.decision_brief_report import (
    render_single_transaction_assessment_markdown,
)
from src.intelligence.finding_review import latest_finding_review_decisions
from src.intelligence.live_ai_contract import build_live_ai_grounding_packet
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


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _format_money(value: Any) -> str:
    if value is None:
        return "-"
    number = Decimal(str(value))
    return f"₩{number:,.0f}"


def _select_package() -> tuple[SingleTransactionAssessmentPackage | None, str | None]:
    scenarios = list_demo_scenarios()
    by_title = {item.title: item for item in scenarios}

    with st.sidebar:
        st.markdown("## 입력 방식")
        mode = st.radio(
            "분석 패키지",
            ["대표 시나리오", "JSON 패키지 업로드"],
            label_visibility="collapsed",
        )
        if mode == "대표 시나리오":
            title = st.selectbox("시나리오", list(by_title))
            metadata = by_title[title]
            st.markdown(f"**{metadata.highlight}**")
            st.caption(metadata.summary)
            st.caption("데이터 모드: " + ", ".join(metadata.source_modes))
            package = load_demo_scenario(metadata.scenario_id)
            with st.expander("시나리오 입력 메모"):
                for note in package.notes:
                    st.write(f"- {note}")
            return package, metadata.scenario_id

        uploaded = st.file_uploader("Assessment package JSON", type=["json"])
        st.caption("검토된 단일 거래 Package만 허용됩니다. 입력값은 자동 보정하거나 추정하지 않습니다.")
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
    st.title("KB TradeGuard AI · 거래 사전진단")
    st.caption(
        "기업 × 거래 × 바이어 × 국가 × 계약조건을 결합하는 근거 기반 무역금융 의사결정 코파일럿"
    )
    st.info(
        "결정론적 규칙·계산 결과가 기준입니다. 이 화면은 거래 승인·거절, 법률의견, "
        "제재·AML 해소, 은행 신용승인 또는 K-SURE 인수승인을 제공하지 않습니다."
    )


def _run_controls(package: SingleTransactionAssessmentPackage | None, source_key: str | None) -> None:
    with st.sidebar:
        st.markdown("## 실행")
        if package is not None:
            st.caption(f"Case hash: `{package.case.case_hash[:16]}…`")
            st.download_button(
                "입력 Package 다운로드",
                data=package_json_bytes(package),
                file_name=f"{source_key or 'assessment'}-input-package.json",
                mime="application/json",
                use_container_width=True,
            )
        run_clicked = st.button(
            "거래 사전진단 실행",
            type="primary",
            disabled=package is None,
            use_container_width=True,
        )

    if run_clicked and package is not None:
        try:
            with st.spinner("결정론적 5단계 파이프라인을 실행하고 있습니다."):
                run = run_single_transaction_package(package)
        except Exception as exc:
            st.session_state.pop("assessment_run", None)
            st.session_state.pop("assessment_package", None)
            st.error(f"평가 실행이 중단되었습니다: {exc}")
        else:
            st.session_state["assessment_run"] = run
            st.session_state["assessment_package"] = package
            st.session_state["assessment_source_key"] = source_key


def _render_metrics(run: SingleTransactionPackageRun) -> None:
    summary = assessment_summary(run)
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
        _DISPOSITION_HELP.get(
            summary["disposition"], summary["disposition"]
        )
    )


def _render_summary_tab(run: SingleTransactionPackageRun) -> None:
    case = run.updated_case
    result = run.assessment_result
    transaction = next(
        item
        for item in case.approved_transactions
        if str(item.get("transaction_id")) == result.transaction_id
    )
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
        st.subheader("판정 근거")
        for item in result.brief.disposition_rationale:
            st.write(f"- {item}")
        st.markdown("**부족한 정보**")
        if result.brief.missing_information:
            for item in result.brief.missing_information:
                st.write(f"- {item}")
        else:
            st.write("- 최소 Coverage 기준에서 별도 누락정보가 없습니다.")

    st.subheader("5단계 실행 Trace")
    stages = pd.DataFrame(stage_rows(run))
    stages["단계"] = stages["단계"].map(lambda value: _STAGE_LABELS.get(value, value))
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
                {"심각도": label, "건수": count}
                for label, count in assessment_summary(run)["severity_counts"].items()
                if count
            ]
        )
        if not severity.empty:
            st.bar_chart(severity.set_index("심각도"))
    else:
        st.success("현재 검토자료에서 표시할 우려사항이 없습니다.")

    st.subheader("문장별 근거 연결")
    st.caption("보고서와 Live AI grounding은 아래 Reference ID 범위만 사용합니다.")
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
    absolute_keys = [
        "gross_transaction_krw",
        "identified_liquid_assets_krw",
        "unprotected_exposure_krw",
        "pre_shipment_funding_need_krw",
        "post_funding_liquidity_krw",
    ]
    chart = pd.DataFrame(
        [
            {"항목": key, "금액": metrics.get(key)}
            for key in absolute_keys
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
    st.caption("상담 후보는 적격성·승인·금리·한도·보험 인수 확정이 아닙니다.")


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
    st.subheader("의존관계")
    for item in actions:
        dependencies = ", ".join(item.dependency_action_ids) or "없음"
        st.write(f"**{item.sequence}. {item.title}** · 선행: `{dependencies}`")
        st.caption(item.rationale)


def _render_audit_tab(
    run: SingleTransactionPackageRun,
    package: SingleTransactionAssessmentPackage,
) -> None:
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
    col1, col2, col3 = st.columns(3)
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
    with st.expander("Audit summary"):
        st.json(run.audit_summary)
    with st.expander("결정론적 Markdown 미리보기"):
        st.markdown(report)


def _render_live_ai_tab(run: SingleTransactionPackageRun) -> None:
    st.subheader("선택형 Grounded Live AI")
    st.caption(
        "현재 단계에서는 Provider 호출 전 Grounding Packet과 인용 검증 경계를 보여줍니다. "
        "Live AI가 꺼져도 전체 분석·보고서·다운로드는 정상 동작합니다."
    )
    enabled = st.toggle("Live AI 실험 모드", value=False)
    if not enabled:
        st.info("기본값은 OFF입니다. 결정론적 결과가 최종 기준으로 유지됩니다.")
        return

    mode = st.selectbox(
        "AI 역할",
        [
            "explain_brief",
            "prepare_consultation",
            "evidence_lookup",
            "compare_reviewed_options",
        ],
    )
    question = st.text_area(
        "질문",
        value="왜 이 사전진단 상태가 나왔고 은행 상담 전에 무엇을 준비해야 하나요?",
        height=100,
    )
    if st.button("Grounding Packet 생성"):
        try:
            packet = build_live_ai_grounding_packet(
                run.updated_case,
                run.assessment_result,
                request_id=f"LIVE-{run.assessment_result.pipeline_id}",
                mode=mode,
                user_question=question,
            )
        except Exception as exc:
            st.error(f"Grounding Packet 생성 실패: {exc}")
            return
        st.success("허용된 Reference ID와 결정론적 Context만 포함했습니다.")
        st.json(packet.model_dump(mode="json"))
        st.download_button(
            "Grounding Packet 다운로드",
            data=_json_text(packet.model_dump(mode="json")).encode("utf-8"),
            file_name="live_ai_grounding_packet.json",
            mime="application/json",
        )
        st.warning(
            "실제 모델 응답은 모든 문장에 [REF:ID] 인용을 포함하고 검증을 통과한 경우에만 표시해야 합니다."
        )


def _render_results(
    run: SingleTransactionPackageRun,
    package: SingleTransactionAssessmentPackage,
) -> None:
    _render_metrics(run)
    tabs = st.tabs(
        [
            "요약",
            "위험·근거",
            "문서",
            "재무",
            "상품",
            "실행계획",
            "감사·다운로드",
            "Live AI",
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
        _render_audit_tab(run, package)
    with tabs[7]:
        _render_live_ai_tab(run)


def main() -> None:
    st.set_page_config(
        page_title="KB TradeGuard Assessment",
        page_icon="🛡️",
        layout="wide",
    )
    _render_header()
    package, source_key = _select_package()
    _run_controls(package, source_key)

    run = st.session_state.get("assessment_run")
    executed_package = st.session_state.get("assessment_package")
    if run is None or executed_package is None:
        st.markdown("### 사용 흐름")
        st.write("대표 시나리오 또는 검토된 JSON Package를 선택한 뒤 거래 사전진단을 실행하세요.")
        st.write("실행 결과는 8개 탭과 Markdown·JSON·ZIP 산출물로 제공됩니다.")
        return
    _render_results(run, executed_package)


if __name__ == "__main__":
    main()
