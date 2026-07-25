"""Seven-tab reviewed trade workflow with read-only grounded advisory."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.advisor_orchestrator import AdvisorOrchestrator
from src.advisor_tools import ReadOnlyAdvisorTools
from src.cash_allocation import REQUIRED_ALLOCATION_COLUMNS, allocate_foreign_cash
from src.cashflow import CASH_FLOW_VIEWS, calculate_monthly_cashflow
from src.document_extraction import (
    OptionalStructuredLLMExtractor,
    select_deterministic_extractor,
)
from src.document_models import (
    ExtractedTradeDocument,
    ReviewQueueItem,
    UploadedDocument,
)
from src.document_validation import (
    HIGH_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    approve_extracted_transaction,
    batch_approve_extracted_transactions,
    create_review_queue,
    validate_extracted_candidate,
)
from src.exposure import calculate_exposure
from src.hedging import (
    DEFAULT_HEDGE_ANALYSIS_BASIS,
    HEDGE_ANALYSIS_BASES,
    calculate_natural_hedge,
)
from src.maturity_buckets import build_maturity_bucket_exposure
from src.policy_retrieval import BundledPolicyRetriever
from src.portfolio_hedging import (
    calculate_maturity_bucket_portfolio_hedge,
    calculate_transaction_level_portfolio_hedge,
)
from src.provenance import AuditTrail
from src.recommendations import generate_recommendations
from src.validators import validate_fx_rates, validate_transactions

ROOT = Path(__file__).parent
SAMPLE_TRANSACTIONS = ROOT / "data" / "sample_transactions.csv"
SAMPLE_COMPANY = ROOT / "data" / "sample_company.json"
SAMPLE_FX_RATES = ROOT / "data" / "sample_fx_rates.csv"
POLICY_DIR = ROOT / "data" / "policy_docs"
PORTFOLIO_COLUMNS = [
    "transaction_id",
    "transaction_type",
    "currency",
    "amount_fc",
    "probability",
    "status",
    "expected_date",
    "invoice_date",
    "document_reference",
    "counterparty_name",
    "source_filename",
    "source_type",
    "canonical_transaction_fingerprint",
    "upload_file_fingerprint",
    "upload_content_sha256",
    "upload_file_size",
    "near_duplicate_key",
]
EXAMPLE_QUESTIONS = [
    "현재 USD 환노출이 얼마나 되나요?",
    "총액 상계가 50%인데 자연헤지가 왜 0%인가요?",
    "환율이 10% 하락하면 50% 헤지가 얼마나 방어하나요?",
    "EXP-001 입금이 30일 늦으면 어떻게 되나요?",
    "이 선물환 가격은 실제 KB 견적인가요?",
]


@st.cache_data
def load_company() -> dict:
    return json.loads(SAMPLE_COMPANY.read_text(encoding="utf-8"))


@st.cache_data
def load_transactions() -> pd.DataFrame:
    frame = pd.read_csv(SAMPLE_TRANSACTIONS)
    frame["source_type"] = "bundled"
    return frame


@st.cache_data
def load_fx_rates() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_FX_RATES)


def initialize_session() -> None:
    defaults = {
        "approved_transactions": [],
        "manual_transactions": [],
        "review_queue": [],
        "audit_events": [],
        "cash_allocations": [],
        "advisor_question": EXAMPLE_QUESTIONS[0],
        "advisor_run": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def records_frame(records: list[dict]) -> pd.DataFrame:
    return (
        pd.DataFrame(records).reindex(columns=PORTFOLIO_COLUMNS)
        if records
        else pd.DataFrame(columns=PORTFOLIO_COLUMNS)
    )


def combined_portfolio() -> pd.DataFrame:
    if st.session_state.get("demo_mode", True):
        return load_transactions()
    combined = pd.concat(
        [
            load_transactions(),
            records_frame(st.session_state.approved_transactions),
            records_frame(st.session_state.manual_transactions),
        ],
        ignore_index=True,
        sort=False,
    )
    return combined[
        combined["transaction_id"].notna()
        & combined["transaction_id"].astype(str).str.strip().ne("")
    ]


def confidence_label(value: float) -> str:
    if value >= HIGH_CONFIDENCE_THRESHOLD:
        return "High"
    if value >= LOW_CONFIDENCE_THRESHOLD:
        return "Review required"
    return "Low"


def queue_to_session(queue: list[ReviewQueueItem]) -> None:
    st.session_state.review_queue = [
        item.model_dump(mode="json") for item in queue
    ]


def render_document_review(
    company: dict, audit: AuditTrail, demo_mode: bool
) -> None:
    st.subheader("Upload → extract candidates → review queue → explicit approval")
    if demo_mode:
        st.info(
            "Bundled demo mode is active. Upload and registration are disabled; "
            "only synthetic bundled data is loaded."
        )
        return
    uploaded = st.file_uploader(
        "Trade document", type=["pdf", "xlsx", "csv", "txt"]
    )
    llm_extractor = OptionalStructuredLLMExtractor()
    provider_options = ["Deterministic / text-only provider"]
    if llm_extractor.is_available:
        provider_options.append("Optional structured LLM")
    provider_choice = st.selectbox("Extraction provider", provider_options)
    st.info(
        "Provider: "
        + (
            "configured structured AI"
            if provider_choice == "Optional structured LLM"
            else "deterministic parser/text display — not live AI"
        )
    )
    if uploaded is not None and st.button("Extract review candidates"):
        document = UploadedDocument(
            filename=uploaded.name,
            content=uploaded.getvalue(),
            media_type=uploaded.type,
        )
        audit.record(
            "upload",
            source_filename=uploaded.name,
            media_type=uploaded.type,
            document_bytes_persisted=False,
        )
        try:
            extractor = (
                llm_extractor
                if provider_choice == "Optional structured LLM"
                else select_deterministic_extractor(uploaded.name)
            )
            candidates = extractor.extract(document)
            existing_fingerprints = {
                row["canonical_transaction_fingerprint"]: row["transaction_id"]
                for row in st.session_state.approved_transactions
                if row.get("canonical_transaction_fingerprint")
            }
            existing_upload_fingerprints = {
                row["upload_file_fingerprint"]: row["transaction_id"]
                for row in st.session_state.approved_transactions
                if row.get("upload_file_fingerprint")
            }
            existing_content_hashes = {
                row["upload_content_sha256"]: row["transaction_id"]
                for row in st.session_state.approved_transactions
                if row.get("upload_content_sha256")
            }
            existing_near_keys = {
                row["near_duplicate_key"]: row["transaction_id"]
                for row in st.session_state.approved_transactions
                if row.get("near_duplicate_key")
            }
            queue = create_review_queue(
                candidates,
                set(load_fx_rates()["currency"]),
                existing_fingerprints,
                existing_upload_fingerprints,
                existing_content_hashes,
                existing_near_keys,
            )
            queue_to_session(queue)
            audit.record(
                "extraction",
                provider=(
                    candidates[0].extraction_method
                    if candidates
                    else "no_candidates"
                ),
                source_filename=uploaded.name,
                candidate_count=len(candidates),
                extracted_values=[
                    candidate.model_dump(
                        mode="json", exclude={"document_text"}
                    )
                    for candidate in candidates
                ],
            )
            st.success(f"Created {len(candidates)} review candidates.")
        except Exception as exc:
            st.error(f"Extraction failed: {exc}")

    if not st.session_state.review_queue:
        return
    queue = [
        ReviewQueueItem.model_validate(item)
        for item in st.session_state.review_queue
    ]
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "candidate_id": item.candidate_id,
                    "queue_status": item.status,
                    "transaction_id": item.candidate.transaction_id,
                    "type": item.candidate.transaction_type,
                    "currency": item.candidate.currency,
                    "amount": item.candidate.amount_fc,
                    "date": item.candidate.expected_date,
                    "source": item.candidate.source_page,
                    "parsing_confidence": item.candidate.parsing_confidence,
                    "semantic_mapping_confidence": (
                        item.candidate.semantic_mapping_confidence
                    ),
                    "validation_status": item.candidate.validation_status,
                    "duplicate_of": item.duplicate_of,
                    "duplicate_category": item.duplicate_category,
                    "canonical_fingerprint": (
                        item.canonical_transaction_fingerprint[:16]
                    ),
                    "upload_fingerprint": item.upload_file_fingerprint[:16],
                }
                for item in queue
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    selectable = [
        item.candidate_id
        for item in queue
        if item.status not in {"approved", "rejected"}
    ]
    if not selectable:
        st.success("Every queue item has a final decision.")
        return
    selected_id = st.selectbox("Candidate to review", selectable)
    index = next(
        index
        for index, item in enumerate(queue)
        if item.candidate_id == selected_id
    )
    item = queue[index]
    candidate = item.candidate
    supported = set(load_fx_rates()["currency"])
    existing_refs = {
        str(row["document_reference"])
        for row in st.session_state.approved_transactions
        if row.get("document_reference")
    }
    validation = validate_extracted_candidate(candidate, supported, existing_refs)
    left, middle, right = st.columns(3)
    left.metric(
        "Parsing confidence",
        f"{candidate.parsing_confidence:.0%}",
        confidence_label(candidate.parsing_confidence),
    )
    middle.metric(
        "Semantic mapping confidence",
        f"{candidate.semantic_mapping_confidence:.0%}",
        confidence_label(candidate.semantic_mapping_confidence),
    )
    right.metric("Validation status", candidate.validation_status)
    st.caption(
        "Parsing certainty and semantic mapping confidence are independent review aids."
    )
    if item.status == "possible_duplicate":
        st.warning(
            f"{item.duplicate_category}: possible duplicate of "
            f"{item.duplicate_of}. Canonical fields: "
            + ", ".join(item.canonical_fingerprint_fields)
            + ". Upload fields: "
            + ", ".join(item.upload_fingerprint_fields)
        )
    for warning in candidate.warnings:
        st.warning(warning)
    for error in validation.errors:
        st.error(error)
    with st.expander("Field provenance and source excerpts", expanded=True):
        st.dataframe(
            pd.DataFrame(
                [
                    {"field": field, **evidence.model_dump()}
                    for field, evidence in candidate.provenance.items()
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        if candidate.document_text:
            st.text_area(
                "Extracted text — no OCR",
                candidate.document_text,
                height=180,
                disabled=True,
            )

    with st.form(f"candidate_review_{index}"):
        transaction_id = st.text_input(
            "Transaction ID", value=candidate.transaction_id or ""
        )
        transaction_type = st.selectbox(
            "Transaction type",
            ["export", "import"],
            index=0 if candidate.transaction_type != "import" else 1,
        )
        currency = st.selectbox(
            "Currency",
            sorted(supported),
            index=(
                sorted(supported).index(candidate.currency)
                if candidate.currency in supported
                else 0
            ),
        )
        amount_fc = st.number_input(
            "Amount", min_value=0.0, value=float(candidate.amount_fc or 0)
        )
        expected_date = st.date_input(
            "Expected date",
            value=candidate.expected_date
            or pd.Timestamp(company["as_of_date"]).date(),
        )
        probability = st.number_input(
            "Probability",
            0.0,
            1.0,
            float(candidate.probability or 1.0),
        )
        status = st.selectbox(
            "Status",
            ["expected", "confirmed"],
            index=0 if candidate.status != "confirmed" else 1,
        )
        document_reference = st.text_input(
            "Document reference", value=candidate.document_reference or ""
        )
        counterparty_name = st.text_input(
            "Counterparty", value=candidate.counterparty_name or ""
        )
        reviewed_low = st.checkbox(
            "I reviewed low-confidence required fields against the source"
        )
        approve_checked = st.checkbox(
            "I explicitly approve this candidate for registration"
        )
        approve_clicked = st.form_submit_button("Approve selected candidate")

    if st.button("Reject selected candidate"):
        item.status = "rejected"
        queue[index] = item
        queue_to_session(queue)
        audit.record(
            "extraction_rejected",
            candidate_id=item.candidate_id,
            canonical_transaction_fingerprint=(
                item.canonical_transaction_fingerprint
            ),
            upload_file_fingerprint=item.upload_file_fingerprint,
        )
        st.rerun()
    if approve_clicked:
        edited = {
            "transaction_id": transaction_id,
            "transaction_type": transaction_type,
            "currency": currency,
            "amount_fc": amount_fc,
            "expected_date": expected_date,
            "probability": probability,
            "status": status,
            "document_reference": document_reference or None,
            "counterparty_name": counterparty_name or None,
            "validation_status": "review_required",
        }
        try:
            approval = approve_extracted_transaction(
                candidate,
                edited,
                supported,
                set(combined_portfolio()["transaction_id"].astype(str)),
                existing_refs,
                (
                    set(validation.low_confidence_required_fields)
                    if reviewed_low
                    else set()
                ),
                approve_checked,
            )
            if approval.registered_transaction is None:
                st.error("Explicit approval is required.")
            else:
                st.session_state.approved_transactions.append(
                    approval.registered_transaction
                )
                st.session_state.audit_events.append(approval.approval_event)
                item.status = "approved"
                queue[index] = item
                queue_to_session(queue)
                st.rerun()
        except Exception as exc:
            st.error(f"Approval failed: {exc}")

    eligible = [
        item
        for item in queue
        if item.status == "pending" and item.candidate.transaction_id
    ]
    if eligible:
        batch_confirm = st.checkbox(
            "I explicitly approve every eligible pending candidate as extracted"
        )
        if st.button("Batch approve eligible candidates"):
            if not batch_confirm:
                st.error("Explicit batch confirmation is required.")
            else:
                requests = [
                    {
                        "candidate": queue_item.candidate,
                        "edited_values": {
                            "validation_status": "review_required"
                        },
                        "reviewed_fields": (
                            "transaction_type",
                            "currency",
                            "amount_fc",
                            "expected_date",
                        ),
                        "decision": "approved",
                    }
                    for queue_item in eligible
                ]
                try:
                    results = batch_approve_extracted_transactions(
                        requests,
                        supported,
                        set(combined_portfolio()["transaction_id"].astype(str)),
                        existing_refs,
                    )
                    approved_ids = set()
                    for result in results:
                        if result.registered_transaction:
                            st.session_state.approved_transactions.append(
                                result.registered_transaction
                            )
                            st.session_state.audit_events.append(
                                result.approval_event
                            )
                            approved_ids.add(
                                result.registered_transaction["transaction_id"]
                            )
                    for queue_item in queue:
                        if queue_item.candidate.transaction_id in approved_ids:
                            queue_item.status = "approved"
                    queue_to_session(queue)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Batch approval failed: {exc}")


def main() -> None:
    st.set_page_config(page_title="KB TradeGuard", page_icon="🛡️", layout="wide")
    initialize_session()
    demo_mode = st.sidebar.toggle("Bundled demo mode", value=True)
    st.session_state.demo_mode = demo_mode
    if demo_mode:
        st.sidebar.success(
            "Synthetic bundled data only. No credentials or private documents."
        )
        if st.sidebar.button("Restore bundled sample state"):
            for key in (
                "approved_transactions",
                "manual_transactions",
                "review_queue",
                "audit_events",
                "cash_allocations",
                "advisor_run",
            ):
                st.session_state[key] = [] if key != "advisor_run" else None
            for widget_key in (
                "fx_editor",
                "approved_editor",
                "manual_editor",
            ):
                st.session_state.pop(widget_key, None)
            st.session_state.advisor_question = EXAMPLE_QUESTIONS[0]
            st.rerun()
    company = load_company()
    audit = AuditTrail(st.session_state.audit_events)
    st.title("KB TradeGuard")
    st.caption(
        "Human-reviewed registration, deterministic FX calculations, and grounded advisory"
    )
    tabs = st.tabs(
        [
            "1. 문서 자동등록",
            "2. 거래 포트폴리오",
            "3. 통화·만기별 환노출",
            "4. 현금흐름 및 유동성",
            "5. 선물환·헤지 계획",
            "6. 대응 검토사항",
            "7. AI 금융 상담",
        ]
    )
    with tabs[0]:
        render_document_review(company, audit, demo_mode)

    with tabs[1]:
        st.subheader("Portfolio sources")
        st.markdown("**Bundled**")
        st.dataframe(load_transactions(), width="stretch", hide_index=True)
        if demo_mode:
            st.info("Portfolio mutation is disabled in bundled demo mode.")
        else:
            st.markdown("**Approved document transactions**")
            approved_before = records_frame(st.session_state.approved_transactions)
            approved = st.data_editor(
                approved_before,
                width="stretch",
                hide_index=True,
                num_rows="dynamic",
                key="approved_editor",
            )
            if approved.to_json(date_format="iso") != approved_before.to_json(
                date_format="iso"
            ):
                audit.record(
                    "portfolio_modification",
                    portfolio_source="approved_document",
                    before=approved_before.to_dict("records"),
                    after=approved.to_dict("records"),
                )
            st.session_state.approved_transactions = approved.to_dict("records")
            st.markdown("**Manual transactions**")
            manual_before = records_frame(st.session_state.manual_transactions)
            manual = st.data_editor(
                manual_before,
                width="stretch",
                hide_index=True,
                num_rows="dynamic",
                key="manual_editor",
            )
            if manual.to_json(date_format="iso") != manual_before.to_json(
                date_format="iso"
            ):
                audit.record(
                    "portfolio_modification",
                    portfolio_source="manual",
                    before=manual_before.to_dict("records"),
                    after=manual.to_dict("records"),
                )
            st.session_state.manual_transactions = manual.to_dict("records")
        fx_rates = validate_fx_rates(
            st.data_editor(
                load_fx_rates(),
                width="stretch",
                hide_index=True,
                key="fx_editor",
            )
        )
        try:
            portfolio = validate_transactions(combined_portfolio(), fx_rates)
            st.success(f"Validated {len(portfolio)} portfolio transactions.")
        except Exception as exc:
            st.error(f"Portfolio invalid: {exc}")
            st.stop()

    rate_map = dict(zip(fx_rates.currency, fx_rates.spot_rate_krw, strict=True))
    exposure = calculate_exposure(portfolio, company["foreign_cash"], fx_rates)
    as_of = pd.Timestamp(company["as_of_date"]).date()

    with tabs[2]:
        st.subheader("Currency and maturity exposure")
        analysis_as_of = st.date_input("As-of date", value=as_of)
        matching_window = int(
            st.number_input("Matching window days", 0, 365, 30)
        )
        maturity = build_maturity_bucket_exposure(
            portfolio, fx_rates, analysis_as_of, matching_window
        )
        st.dataframe(exposure.by_currency, width="stretch", hide_index=True)
        st.dataframe(maturity.summary, width="stretch", hide_index=True)
        st.dataframe(
            maturity.transaction_tenors, width="stretch", hide_index=True
        )
        natural = calculate_natural_hedge(
            portfolio, company["foreign_cash"], matching_window
        )
        st.dataframe(natural.summary, width="stretch", hide_index=True)
        st.dataframe(natural.matches, width="stretch", hide_index=True)
        if (
            natural.summary.gross_currency_offset
            > natural.summary.maturity_matched_offset
        ).any():
            st.warning(
                "Gross amount offset exceeds maturity-matched offset; liquidity timing risk remains."
            )

    with tabs[3]:
        st.subheader("Cash allocation and liquidity")
        allocation_seed = pd.DataFrame(st.session_state.cash_allocations)
        if allocation_seed.empty:
            allocation_seed = pd.DataFrame(
                columns=sorted(REQUIRED_ALLOCATION_COLUMNS)
            )
        allocation_editor = st.data_editor(
            allocation_seed,
            width="stretch",
            hide_index=True,
            num_rows="dynamic",
            key="allocation_editor",
        )
        st.session_state.cash_allocations = allocation_editor.to_dict("records")
        try:
            allocation = allocate_foreign_cash(
                portfolio, company["foreign_cash"], allocation_editor
            )
        except Exception as exc:
            st.error(f"Allocation invalid: {exc}")
            allocation = allocate_foreign_cash(
                portfolio, company["foreign_cash"]
            )
        st.dataframe(
            allocation.unallocated_foreign_cash,
            width="stretch",
            hide_index=True,
        )
        st.dataframe(
            allocation.import_funding_gap_by_transaction,
            width="stretch",
            hide_index=True,
        )
        selected_view = st.selectbox(
            "Cash-flow view", list(CASH_FLOW_VIEWS), index=1
        )
        cashflow = calculate_monthly_cashflow(
            portfolio,
            rate_map,
            company["monthly_fixed_cost_krw"],
            company["current_cash_krw"],
            cash_flow_view=selected_view,
        )
        st.dataframe(cashflow, width="stretch", hide_index=True)
        st.plotly_chart(
            px.line(
                cashflow,
                x="year_month",
                y="ending_cash_krw",
                markers=True,
            ),
            width="stretch",
        )

    with tabs[4]:
        st.subheader("Maturity-aware hedge plan")
        hedge_as_of = st.date_input("Hedge as-of date", value=as_of)
        mode = st.radio(
            "Mode", ["Transaction-level", "Maturity-bucket"], horizontal=True
        )
        basis = st.selectbox(
            "Analysis basis",
            list(HEDGE_ANALYSIS_BASES),
            index=list(HEDGE_ANALYSIS_BASES).index(
                DEFAULT_HEDGE_ANALYSIS_BASIS
            ),
        )
        exposure_measure = "nominal" if basis.startswith("Nominal") else "expected"
        ratios = {
            currency: st.slider(
                f"{currency} hedge ratio", 0, 100, 50
            )
            / 100
            for currency in sorted(portfolio.currency.unique())
        }
        if mode == "Transaction-level":
            hedge_plan = calculate_transaction_level_portfolio_hedge(
                portfolio,
                fx_rates,
                hedge_as_of,
                ratios,
                exposure_measure=exposure_measure,
            )
        else:
            bucket_data = build_maturity_bucket_exposure(
                portfolio, fx_rates, hedge_as_of, matching_window
            )
            bucket_ratios = {
                (row.currency, row.maturity_bucket): ratios[row.currency]
                for row in bucket_data.summary.itertuples(index=False)
            }
            hedge_plan = calculate_maturity_bucket_portfolio_hedge(
                portfolio,
                fx_rates,
                hedge_as_of,
                bucket_ratios,
                exposure_measure=exposure_measure,
                matching_window_days=matching_window,
            )
            st.dataframe(
                hedge_plan.bucket_summary, width="stretch", hide_index=True
            )
        st.dataframe(
            hedge_plan.transaction_results, width="stretch", hide_index=True
        )
        st.dataframe(
            hedge_plan.currency_scenario_totals,
            width="stretch",
            hide_index=True,
        )
        st.dataframe(
            hedge_plan.portfolio_scenario_totals,
            width="stretch",
            hide_index=True,
        )

    with tabs[5]:
        st.subheader("Considerations and audit")
        recommendations = generate_recommendations(
            exposure,
            cashflow,
            portfolio,
            natural,
            hedge_analysis_basis=basis,
        )
        for recommendation in recommendations:
            with st.container(border=True):
                st.markdown(f"**{recommendation['title']}**")
                st.write(recommendation["suggested_consideration"])
                st.caption(recommendation["limitation"])
        st.dataframe(
            pd.DataFrame(st.session_state.audit_events),
            width="stretch",
            hide_index=True,
        )
        audit_json = audit.export_json(
            {
                "as_of_date": str(hedge_as_of),
                "fx_rates": fx_rates.to_dict("records"),
                "hedge_basis": basis,
                "hedge_ratios": ratios,
                "cash_allocations": st.session_state.cash_allocations,
            }
        )
        st.download_button(
            "Export JSON audit",
            audit_json,
            "kb_tradeguard_audit.json",
            "application/json",
        )

    with tabs[6]:
        st.subheader("Read-only grounded financial advisory")
        example = st.selectbox("Example question", EXAMPLE_QUESTIONS)
        if st.button("Use selected example"):
            st.session_state.advisor_question = example
        question = st.text_area(
            "Question", key="advisor_question", height=90
        )
        retriever = BundledPolicyRetriever(POLICY_DIR)
        advisor_tools = ReadOnlyAdvisorTools(
            portfolio,
            fx_rates,
            company,
            allocation_editor,
            st.session_state.audit_events,
            retriever,
        )
        orchestrator = AdvisorOrchestrator(advisor_tools)
        st.info(f"Provider: {orchestrator.provider.provider_mode}")
        if st.button("Ask read-only advisor"):
            run = orchestrator.ask(question)
            st.session_state.advisor_run = {
                "answer": run.answer.model_dump(mode="json"),
                "validation": run.validation.model_dump(mode="json"),
                "tools": {
                    name: (
                        value.model_dump(mode="json")
                        if hasattr(value, "model_dump")
                        else str(value)
                    )
                    for name, value in run.tool_results.items()
                },
            }
        if st.session_state.advisor_run:
            raw = st.session_state.advisor_run
            answer = raw["answer"]
            validation = raw["validation"]
            st.markdown(f"**Detected intent:** `{answer['intent']['primary_intent']}`")
            st.write(
                "Selected tools: "
                + ", ".join(answer["intent"]["required_tools"])
            )
            if answer["intent"]["clarification_required"]:
                st.warning(
                    "Clarification required: "
                    + ", ".join(answer["intent"]["missing_parameters"])
                )
            st.markdown("### Direct answer")
            st.write(answer["direct_answer"])
            st.markdown("### Key findings")
            for finding in answer["key_findings"]:
                st.write("- " + finding)
            st.markdown("### Calculation citations")
            for citation in answer["calculations_used"]:
                st.code(
                    f"[{citation['calculation_id']}, "
                    f"{citation['calculation_name']}]"
                )
            st.markdown("### Document citations")
            for citation in answer["documents_used"]:
                st.write(
                    f"[{citation['document_id']}, {citation['title']}, "
                    f"{citation['excerpt_id']}]"
                )
                st.caption(
                    f"Local content: {citation['content_origin']} · "
                    f"Official issuer: {citation['official_issuer']} · "
                    f"Published: {citation['publication_date'] or 'not stated'} · "
                    f"Source retrieved: {citation['retrieval_date']} · "
                    f"Summary reviewed: "
                    f"{citation['summary_last_reviewed'] or 'not stated'}"
                )
                st.markdown(
                    f"[Official source]({citation['official_source_url']})"
                )
                st.warning(
                    citation["stale_warning"]
                    or "No freshness warning for this local summary."
                )
            with st.expander("Assumptions, limitations, and risk notice"):
                st.write(answer["assumptions"])
                st.write(answer["considerations"])
                st.write(answer["limitations"])
                st.warning(answer["risk_notice"])
            st.success("Answer validation passed") if validation[
                "validation_result"
            ] else st.error("Answer validation failed")
            st.json(validation)
            with st.expander("Raw structured answer"):
                st.json(raw)
        st.warning(
            "The advisor is read-only and cannot register, approve, edit, or delete portfolio transactions."
        )


if __name__ == "__main__":
    main()
