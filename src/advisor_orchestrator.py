"""Read-only advisory orchestration over deterministic tools and local guidance."""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .advisor_guardrails import SAFE_RISK_NOTICE, is_sensitive_request
from .advisor_models import (
    AdvisoryAnswer,
    CalculationResult,
    IntentClassification,
    NumericalClaim,
)
from .advisor_tools import ReadOnlyAdvisorTools
from .answer_validation import AnswerValidationReport, validate_advisory_answer
from .citation_models import CalculationCitation, DocumentCitation
from .policy_retrieval import PolicyExcerpt

DEFAULT_BASIS = "Expected transaction exposure"


def _calculation_citation(result: CalculationResult) -> str:
    return result.calculation_id


def _unique_calculation_citations(
    results: list[CalculationResult],
) -> list[CalculationCitation]:
    seen = set()
    citations = []
    for result in results:
        if result.calculation_id not in seen:
            citations.append(result.citation)
            seen.add(result.calculation_id)
    return citations


def _unique_document_citations(
    excerpts: list[PolicyExcerpt],
) -> list[DocumentCitation]:
    seen = set()
    citations = []
    for excerpt in excerpts:
        key = (
            excerpt.citation.document_id,
            excerpt.citation.excerpt_id,
        )
        if key not in seen:
            citations.append(excerpt.citation)
            seen.add(key)
    return citations


def _cite_each_sentence(text: str, citation: str) -> list[str]:
    """Attach the same document citation to every sentence in an excerpt."""
    cited = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        punctuation = sentence[-1] if sentence[-1] in ".!?" else ""
        body = sentence[:-1] if punctuation else sentence
        cited.append(f"{body} {citation}{punctuation}")
    return cited


class AdvisoryProvider(ABC):
    """Provider may classify/synthesize, but receives only controlled tool output."""

    provider_mode: str

    @abstractmethod
    def classify(
        self, question: str, tools: ReadOnlyAdvisorTools
    ) -> IntentClassification:
        ...

    @abstractmethod
    def synthesize(
        self,
        question: str,
        intent: IntentClassification,
        tool_results: dict[str, Any],
    ) -> AdvisoryAnswer:
        ...


class DeterministicOfflineAdvisor(AdvisoryProvider):
    """Keyword/template fallback using the exact same read-only financial tools."""

    provider_mode = "Deterministic fallback — not live AI."

    TOOL_MAP = {
        "portfolio_summary": ["get_portfolio_summary"],
        "fx_exposure": ["get_exposure_by_currency"],
        "cashflow_risk": ["get_cashflow_view", "get_liquidity_shortfalls"],
        "settlement_delay": ["run_cashflow_delay_scenario"],
        "natural_hedge": ["get_natural_offset_summary"],
        "maturity_mismatch": ["get_maturity_mismatch_summary"],
        "hedge_comparison": ["compare_hedge_ratios"],
        "forward_rate_explanation": ["calculate_transaction_forward_rates"],
        "import_funding": ["get_cash_allocation_summary"],
        "document_provenance": ["get_document_provenance"],
        "policy_information": ["search_trade_finance_guidance"],
        "bank_consultation_preparation": ["build_bank_consultation_checklist"],
        "unsupported_or_sensitive_request": [],
    }

    def classify(
        self, question: str, tools: ReadOnlyAdvisorTools
    ) -> IntentClassification:
        lower = question.lower()
        params: dict[str, Any] = {}
        sources: dict[str, str] = {}
        missing = []
        if is_sensitive_request(question):
            intent = "unsupported_or_sensitive_request"
        elif re.search(r"(늦|지연|delay)", lower):
            intent = "settlement_delay"
            transaction_match = re.search(r"\b([A-Z]{2,}-\d+)\b", question.upper())
            day_match = re.search(r"(\d+)\s*일", question)
            if transaction_match:
                params["transaction_id"] = transaction_match.group(1)
                sources["transaction_id"] = "question text"
            else:
                missing.append("transaction_id")
            if day_match:
                params["delay_days"] = int(day_match.group(1))
                sources["delay_days"] = "question text"
            else:
                missing.append("delay_days")
            params["cash_flow_view"] = "expected"
            sources["cash_flow_view"] = "configured default, disclosed"
        elif re.search(r"(총액\s*상계|자연헤지|natural\s*hedge)", lower):
            intent = "natural_hedge"
            params["matching_window_days"] = 30
            sources["matching_window_days"] = "configured default, disclosed"
        elif re.search(r"(만기.*(?:불일치|차이)|maturity\s*mismatch)", lower):
            intent = "maturity_mismatch"
            params["matching_window_days"] = 30
            sources["matching_window_days"] = "configured default, disclosed"
        elif re.search(r"(헤지|hedge)", lower):
            intent = "hedge_comparison"
            ratios = [
                int(value) / 100
                for value in re.findall(r"(\d+)\s*%", question)
                if int(value) <= 100
            ]
            params["hedge_ratios"] = sorted(set([0.0, *ratios] or [0.0, 0.5, 1.0]))
            sources["hedge_ratios"] = "question text"
            decline = re.search(r"(\d+)\s*%\s*(?:하락|내리)", question)
            rise = re.search(r"(\d+)\s*%\s*(?:상승|오르)", question)
            if decline:
                params["scenarios"] = [-int(decline.group(1)) / 100]
            elif rise:
                params["scenarios"] = [int(rise.group(1)) / 100]
            else:
                params["scenarios"] = [-0.10, -0.05, 0.0, 0.05, 0.10]
            sources["scenarios"] = "question text or disclosed defaults"
            currency = next(
                (
                    item
                    for item in tools.active_transaction_currencies
                    if item.lower() in lower
                ),
                None,
            )
            if currency:
                params["currency"] = currency
                sources["currency"] = "question text"
            elif len(tools.active_transaction_currencies) == 1:
                params["currency"] = tools.active_transaction_currencies[0]
                sources["currency"] = "unique transaction currency in portfolio"
            else:
                missing.append("currency")
            params["analysis_basis"] = DEFAULT_BASIS
            sources["analysis_basis"] = "configured default, disclosed"
        elif re.search(r"(선물환|forward).*(실제|견적|가격|quote)", lower):
            intent = "forward_rate_explanation"
            params["as_of_date"] = tools._as_of_date
            sources["as_of_date"] = "company analysis date"
        elif re.search(r"(현금.*(?:부족|위험)|cash.?flow|유동성)", lower):
            intent = "cashflow_risk"
            params["cash_flow_view"] = "expected"
            sources["cash_flow_view"] = "configured default, disclosed"
        elif re.search(r"(수입.*(?:자금|조달)|import\s*fund)", lower):
            intent = "import_funding"
        elif re.search(r"(출처|근거|provenance)", lower):
            intent = "document_provenance"
            transaction_match = re.search(r"\b([A-Z]{2,}-\d+)\b", question.upper())
            if transaction_match:
                params["transaction_id"] = transaction_match.group(1)
                sources["transaction_id"] = "question text"
            else:
                missing.append("transaction_id")
        elif re.search(r"(은행.*(?:상담|서류)|어떤\s*서류|consultation)", lower):
            intent = "bank_consultation_preparation"
        elif re.search(r"(보험|보증|정책|제도|가이드|financing|insurance)", lower):
            intent = "policy_information"
        elif re.search(r"(환노출|fx\s*exposure)", lower):
            intent = "fx_exposure"
            currency = next(
                (
                    item
                    for item in ["USD", "EUR"]
                    if item.lower() in lower
                ),
                None,
            )
            if currency:
                params["currency"] = currency
                sources["currency"] = "question text"
        elif re.search(r"(포트폴리오|portfolio|거래.*요약)", lower):
            intent = "portfolio_summary"
        else:
            intent = "unsupported_or_sensitive_request"
        return IntentClassification(
            primary_intent=intent,
            required_tools=self.TOOL_MAP[intent],
            extracted_parameters=params,
            parameter_sources=sources,
            missing_parameters=missing,
            confidence=0.95 if intent != "unsupported_or_sensitive_request" else 0.55,
            clarification_required=bool(missing),
        )

    def synthesize(
        self,
        question: str,
        intent: IntentClassification,
        tool_results: dict[str, Any],
    ) -> AdvisoryAnswer:
        if intent.clarification_required:
            missing = ", ".join(intent.missing_parameters)
            return AdvisoryAnswer(
                provider_mode=self.provider_mode,
                intent=intent,
                direct_answer=f"계산을 실행하려면 다음 정보가 필요합니다: {missing}.",
                assumptions=[],
                limitations=["누락된 값을 임의로 추정하지 않았습니다."],
                follow_up_question=f"{missing}을(를) 알려주시겠습니까?",
                risk_notice=SAFE_RISK_NOTICE,
            )
        if intent.primary_intent == "unsupported_or_sensitive_request":
            return AdvisoryAnswer(
                provider_mode=self.provider_mode,
                intent=intent,
                direct_answer=(
                    "요청하신 판단이나 행위는 지원할 수 없습니다. 거래 사실 확인, "
                    "결정론적 시뮬레이션 또는 공식 기관 상담 준비로 범위를 바꿔 "
                    "도와드릴 수 있습니다."
                ),
                limitations=[
                    "대출 승인, 공식 신용등급, 문서 조작, 제재 회피, 보장된 환율 예측, 확정적 법률·세무 결론은 제공하지 않습니다."
                ],
                follow_up_question="검토 가능한 정보 또는 시뮬레이션 질문으로 바꾸시겠습니까?",
                risk_notice=SAFE_RISK_NOTICE,
            )

        calculations = [
            value
            for value in tool_results.values()
            if isinstance(value, CalculationResult)
        ]
        excerpts = []
        for value in tool_results.values():
            if isinstance(value, list) and (
                not value or isinstance(value[0], PolicyExcerpt)
            ):
                excerpts.extend(value)
            elif isinstance(value, dict) and "documents" in value:
                excerpts.extend(value["documents"])
        calc_citations = _unique_calculation_citations(calculations)
        document_citations = _unique_document_citations(excerpts)
        claims: list[NumericalClaim] = []
        findings = []
        assumptions = []
        considerations = []
        limitations = []
        follow_up = None
        primary = intent.primary_intent

        if primary == "fx_exposure":
            calc = tool_results["get_exposure_by_currency"]
            currency = intent.extracted_parameters.get("currency", "USD")
            row = next(
                item
                for item in calc.result["by_currency"]
                if item["currency"] == currency
            )
            citation = _calculation_citation(calc)
            direct = (
                f"Expected {currency} transaction exposure is {currency} "
                f"{row['expected_transaction_exposure']:,.0f} ({citation}). "
                f"Foreign-currency cash is {currency} "
                f"{row['foreign_cash_position']:,.0f} ({citation}). "
                f"Expected total economic position is {currency} "
                f"{row['expected_total_economic_position']:,.0f} ({citation})."
            )
            for description, key in (
                ("Expected transaction exposure", "expected_transaction_exposure"),
                ("Foreign-currency cash", "foreign_cash_position"),
                ("Expected total economic position", "expected_total_economic_position"),
            ):
                claims.append(
                    NumericalClaim(
                        description=description,
                        value=row[key],
                        unit=currency,
                        calculation_id=citation,
                        analysis_basis=description,
                        as_of_date=calc.as_of_date,
                    )
                )
            findings.append(
                f"Cash is a positive balance-sheet asset and does not reduce transaction exposure ({citation})."
            )
        elif primary in {"natural_hedge", "maturity_mismatch"}:
            calc = next(iter(calculations))
            usd = next(
                row for row in calc.result["summary"] if row["currency"] == "USD"
            )
            gaps = sorted(
                row["timing_gap_days"]
                for row in calc.result["all_same_currency_timing_gaps"]
                if row["currency"] == "USD"
            )
            citation = _calculation_citation(calc)
            direct = (
                f"USD gross same-currency offset is USD "
                f"{usd['gross_currency_offset']:,.0f} ({citation}), but the "
                f"maturity-matched offset under the 30-day window is USD "
                f"{usd['maturity_matched_offset']:,.0f} ({citation})."
            )
            findings.append(
                f"The same-currency settlement gaps are {gaps[0]} days and "
                f"{gaps[1]} days ({citation}); both exceed the selected 30-day "
                f"window ({citation})."
            )
            considerations.append(
                "총액 상계 비율과 실제 유동성 헤지는 다르므로 결제시점 조정 또는 별도 유동성 검토가 필요합니다."
            )
            for description, value, unit in (
                ("Gross currency offset", usd["gross_currency_offset"], "USD"),
                (
                    "Maturity-matched offset",
                    usd["maturity_matched_offset"],
                    "USD",
                ),
                ("First timing gap", gaps[0], "days"),
                ("Second timing gap", gaps[1], "days"),
            ):
                claims.append(
                    NumericalClaim(
                        description=description,
                        value=value,
                        unit=unit,
                        calculation_id=citation,
                        analysis_basis="Nominal same-currency maturity matching",
                        as_of_date=calc.as_of_date,
                    )
                )
            assumptions.append(f"Matching window is 30 days ({citation}).")
        elif primary == "hedge_comparison":
            calc = tool_results["compare_hedge_ratios"]
            ratio = max(
                intent.extracted_parameters.get("hedge_ratios", [0.5])
            )
            if ratio == 0 and len(intent.extracted_parameters.get("hedge_ratios", [])) > 1:
                ratio = intent.extracted_parameters["hedge_ratios"][-1]
            scenario = intent.extracted_parameters["scenarios"][0]
            row = next(
                item
                for item in calc.result
                if item["hedge_ratio"] == ratio
                and item["scenario_pct"] == scenario
            )
            citation = _calculation_citation(calc)
            direct = (
                f"Under the selected {ratio:.0%} hedge and {scenario:.0%} spot "
                f"scenario, downside protection is KRW "
                f"{row['downside_protection_krw']:,.0f} ({citation})."
            )
            findings.append(
                f"Total simulated KRW value is KRW {row['total_krw_value']:,.0f} "
                f"on the {intent.extracted_parameters['analysis_basis']} basis "
                f"({citation})."
            )
            assumptions.append(
                f"The comparison uses a 3-month indicative theoretical forward "
                f"rate of {row['adjusted_forward_rate']:,.6f} KRW per foreign-currency "
                f"unit ({citation}); it is not an executable quote."
            )
            for description, value in (
                ("Downside protection", row["downside_protection_krw"]),
                ("Total simulated KRW value", row["total_krw_value"]),
                ("Indicative theoretical forward", row["adjusted_forward_rate"]),
            ):
                claims.append(
                    NumericalClaim(
                        description=description,
                        value=value,
                        unit="KRW" if "forward" not in description.lower() else "KRW/FC",
                        calculation_id=citation,
                        analysis_basis=intent.extracted_parameters["analysis_basis"],
                        as_of_date=calc.as_of_date,
                    )
                )
        elif primary == "settlement_delay":
            calc = tool_results["run_cashflow_delay_scenario"]
            citation = _calculation_citation(calc)
            months = [row["year_month"] for row in calc.result["changed_months"]]
            direct = (
                f"The {intent.extracted_parameters['delay_days']}-day delay changes "
                f"transaction cash flow in {', '.join(months)} ({citation}). "
                f"Maximum delayed shortfall is KRW "
                f"{calc.result['delayed_max_shortfall_krw']:,.0f} ({citation})."
            )
            findings.append(
                f"Baseline maximum shortfall is KRW "
                f"{calc.result['baseline_max_shortfall_krw']:,.0f} ({citation})."
            )
            claims.extend(
                [
                    NumericalClaim(
                        description="Delay days",
                        value=intent.extracted_parameters["delay_days"],
                        unit="days",
                        calculation_id=citation,
                        analysis_basis=intent.extracted_parameters["cash_flow_view"],
                        as_of_date=calc.as_of_date,
                    ),
                    NumericalClaim(
                        description="Delayed maximum shortfall",
                        value=calc.result["delayed_max_shortfall_krw"],
                        unit="KRW",
                        calculation_id=citation,
                        analysis_basis=intent.extracted_parameters["cash_flow_view"],
                        as_of_date=calc.as_of_date,
                    ),
                ]
            )
            assumptions.append(
                f"Cash-flow view is expected and probability-qualified ({citation})."
            )
        elif primary == "cashflow_risk":
            calc = tool_results["get_liquidity_shortfalls"]
            citation = _calculation_citation(calc)
            months = [
                row["year_month"] for row in calc.result["shortfall_months"]
            ]
            direct = (
                f"Expected-view shortfalls occur in {', '.join(months)} "
                f"({citation}). Maximum shortfall is KRW "
                f"{calc.result['maximum_shortfall_krw']:,.0f} ({citation})."
            )
            claims.append(
                NumericalClaim(
                    description="Maximum liquidity shortfall",
                    value=calc.result["maximum_shortfall_krw"],
                    unit="KRW",
                    calculation_id=citation,
                    analysis_basis="Expected cash-flow view",
                    as_of_date=calc.as_of_date,
                )
            )
        elif primary == "forward_rate_explanation":
            calc = tool_results["calculate_transaction_forward_rates"]
            citation = _calculation_citation(calc)
            direct = (
                f"No. This is an indicative theoretical forward rate calculated "
                f"under the configured assumptions and ACT/365 tenor ({citation}); "
                f"it is not an actual KB quote or executable price."
            )
            considerations.append(
                "Actual executable quotes require bank confirmation of tenor, timestamp, spread, credit conditions, and transaction terms."
            )
        elif primary == "import_funding":
            calc = tool_results["get_cash_allocation_summary"]
            citation = _calculation_citation(calc)
            rows = calc.result["funding_gap_by_currency"]
            direct = " ".join(
                f"{row['currency']} import funding gap is "
                f"{row['currency']} {row['import_funding_gap_fc']:,.0f} "
                f"({citation})."
                for row in rows
            )
            for row in rows:
                claims.append(
                    NumericalClaim(
                        description=f"{row['currency']} import funding gap",
                        value=row["import_funding_gap_fc"],
                        unit=row["currency"],
                        calculation_id=citation,
                        analysis_basis="Explicit cash allocation schedule",
                        as_of_date=calc.as_of_date,
                    )
                )
        elif primary == "portfolio_summary":
            calc = tool_results["get_portfolio_summary"]
            citation = _calculation_citation(calc)
            direct = (
                f"The session portfolio contains {calc.result['transaction_count']} "
                f"transactions ({citation})."
            )
            findings.append(
                f"Exports: {calc.result['exports']} ({citation}); imports: "
                f"{calc.result['imports']} ({citation})."
            )
            for description, key in (
                ("Transaction count", "transaction_count"),
                ("Export count", "exports"),
                ("Import count", "imports"),
            ):
                claims.append(
                    NumericalClaim(
                        description=description,
                        value=calc.result[key],
                        unit="transactions",
                        calculation_id=citation,
                        analysis_basis="Current session portfolio",
                        as_of_date=calc.as_of_date,
                    )
                )
        elif primary == "document_provenance":
            calc = tool_results["get_document_provenance"]
            citation = _calculation_citation(calc)
            direct = (
                f"Found {len(calc.result['events'])} session provenance events "
                f"for the requested transaction ({citation})."
            )
            claims.append(
                NumericalClaim(
                    description="Provenance event count",
                    value=len(calc.result["events"]),
                    unit="events",
                    calculation_id=citation,
                    analysis_basis="Session audit trail",
                    as_of_date=calc.as_of_date,
                )
            )
        elif primary == "policy_information":
            if excerpts:
                citations_text = " ".join(
                    excerpt.citation.format() for excerpt in excerpts
                )
                direct = (
                    "Bundled official-source summaries provide general information "
                    f"for review {citations_text}."
                )
                for excerpt in excerpts[:2]:
                    findings.extend(
                        _cite_each_sentence(
                            excerpt.excerpt, excerpt.citation.format()
                        )
                    )
                limitations.append(
                    "Current availability, eligibility, approval, pricing, and suitability must be verified with the issuing organization."
                )
            else:
                direct = "No approved bundled guidance excerpt matched the query."
        elif primary == "bank_consultation_preparation":
            checklist = tool_results["build_bank_consultation_checklist"]
            citations_text = " ".join(
                excerpt.citation.format() for excerpt in excerpts
            )
            direct = (
                "은행 상담 전에 거래계약·송장·결제일·결제조건·운송서류·"
                f"거래상대방 정보를 준비해 검토할 수 있습니다 {citations_text}."
            )
            findings.extend(
                f"{item} {citations_text}" for item in checklist["checklist"]
            )
            limitations.append(f"{checklist['limitation']} {citations_text}")
        else:
            direct = "지원 가능한 결정론적 정보 범위에서 질문을 다시 구체화해 주세요."

        limitations.extend(
            limitation
            for calculation in calculations
            for limitation in calculation.limitations
            if limitation not in limitations
        )
        return AdvisoryAnswer(
            provider_mode=self.provider_mode,
            intent=intent,
            direct_answer=direct,
            key_findings=findings,
            calculations_used=calc_citations,
            documents_used=document_citations,
            numerical_claims=claims,
            assumptions=assumptions,
            considerations=considerations,
            limitations=limitations,
            follow_up_question=follow_up,
            risk_notice=SAFE_RISK_NOTICE,
        )


class ConfiguredStructuredAdvisor(DeterministicOfflineAdvisor):
    """Optional structured intent classifier; financial values still come from tools."""

    provider_mode = "configured structured AI"

    def __init__(self, client=None, model: str | None = None):
        self.client = client
        self.model = model or os.getenv("OPENAI_ADVISOR_MODEL", "gpt-4.1-mini")
        if self.client is None and os.getenv("OPENAI_API_KEY"):
            try:
                from openai import OpenAI

                self.client = OpenAI()
            except ImportError:
                self.client = None

    @property
    def is_available(self) -> bool:
        return self.client is not None

    def classify(
        self, question: str, tools: ReadOnlyAdvisorTools
    ) -> IntentClassification:
        if not self.is_available:
            return super().classify(question, tools)
        if is_sensitive_request(question):
            return super().classify(question, tools)
        schema = IntentClassification.model_json_schema()
        response = self.client.responses.create(
            model=self.model,
            input=(
                "Classify the user question for a read-only financial advisory "
                "orchestrator. Do not calculate any financial values. Do not guess "
                "missing IDs, dates, currencies, ratios, or bases.\nQuestion: "
                + question
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "advisor_intent",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        classification = IntentClassification.model_validate_json(
            response.output_text
        )
        return classification.model_copy(
            update={
                "required_tools": self.TOOL_MAP[classification.primary_intent]
            }
        )

    def synthesize(
        self,
        question: str,
        intent: IntentClassification,
        tool_results: dict[str, Any],
    ) -> AdvisoryAnswer:
        if not self.is_available:
            return super().synthesize(question, intent, tool_results)
        payload = {
            name: (
                value.model_dump(mode="json")
                if hasattr(value, "model_dump")
                else [
                    item.__dict__ if hasattr(item, "__dict__") else item
                    for item in value
                ]
                if isinstance(value, list)
                else value
            )
            for name, value in tool_results.items()
        }
        response = self.client.responses.create(
            model=self.model,
            input=(
                "Create a concise read-only advisory answer using only the supplied "
                "deterministic tool outputs. Never calculate, infer, or invent a "
                "number. Preserve calculation IDs and document IDs exactly. Do not "
                "claim eligibility, approval, guarantees, executable pricing, or "
                "portfolio mutation. Every numerical sentence must contain its "
                "calculation ID and every policy statement its document citation. "
                "Return the supplied intent unchanged.\n"
                + json.dumps(
                    {
                        "question": question,
                        "intent": intent.model_dump(mode="json"),
                        "tool_outputs": payload,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "advisory_answer",
                    "schema": AdvisoryAnswer.model_json_schema(),
                    "strict": True,
                }
            },
        )
        answer = AdvisoryAnswer.model_validate_json(response.output_text)
        return answer.model_copy(
            update={"provider_mode": self.provider_mode, "intent": intent}
        )


@dataclass(frozen=True)
class AdvisoryRun:
    answer: AdvisoryAnswer
    validation: AnswerValidationReport
    tool_results: dict[str, Any]


class AdvisorOrchestrator:
    """Classify, call controlled tools, synthesize, then validate grounding."""

    def __init__(
        self,
        tools: ReadOnlyAdvisorTools,
        provider: AdvisoryProvider | None = None,
    ):
        self.tools = tools
        configured = ConfiguredStructuredAdvisor()
        self.provider = provider or (
            configured if configured.is_available else DeterministicOfflineAdvisor()
        )

    def _execute(
        self, question: str, intent: IntentClassification
    ) -> dict[str, Any]:
        if intent.clarification_required or intent.primary_intent == "unsupported_or_sensitive_request":
            return {}
        params = intent.extracted_parameters
        results: dict[str, Any] = {}
        for tool_name in intent.required_tools:
            if tool_name == "get_portfolio_summary":
                results[tool_name] = self.tools.get_portfolio_summary()
            elif tool_name == "get_exposure_by_currency":
                results[tool_name] = self.tools.get_exposure_by_currency()
            elif tool_name == "get_cashflow_view":
                results[tool_name] = self.tools.get_cashflow_view(
                    params["cash_flow_view"]
                )
            elif tool_name == "get_liquidity_shortfalls":
                results[tool_name] = self.tools.get_liquidity_shortfalls(
                    params["cash_flow_view"]
                )
            elif tool_name == "run_cashflow_delay_scenario":
                results[tool_name] = self.tools.run_cashflow_delay_scenario(
                    params["transaction_id"],
                    params["delay_days"],
                    params["cash_flow_view"],
                )
            elif tool_name in {
                "get_natural_offset_summary",
                "get_maturity_mismatch_summary",
            }:
                results[tool_name] = self.tools.get_natural_offset_summary(
                    params["matching_window_days"]
                )
            elif tool_name == "compare_hedge_ratios":
                results[tool_name] = self.tools.compare_hedge_ratios(
                    params["currency"],
                    params["analysis_basis"],
                    params["scenarios"],
                    params["hedge_ratios"],
                )
            elif tool_name == "calculate_transaction_forward_rates":
                results[tool_name] = self.tools.calculate_transaction_forward_rates(
                    params["as_of_date"]
                )
            elif tool_name == "get_cash_allocation_summary":
                results[tool_name] = self.tools.get_cash_allocation_summary()
            elif tool_name == "get_document_provenance":
                results[tool_name] = self.tools.get_document_provenance(
                    params["transaction_id"]
                )
            elif tool_name == "search_trade_finance_guidance":
                results[tool_name] = self.tools.search_trade_finance_guidance(
                    question
                )
            elif tool_name == "build_bank_consultation_checklist":
                results[tool_name] = self.tools.build_bank_consultation_checklist(
                    question
                )
        return results

    def ask(self, question: str) -> AdvisoryRun:
        try:
            intent = self.provider.classify(question, self.tools)
        except Exception:
            self.provider = DeterministicOfflineAdvisor()
            intent = self.provider.classify(question, self.tools)
        tool_results = self._execute(question, intent)
        try:
            answer = self.provider.synthesize(question, intent, tool_results)
        except Exception:
            self.provider = DeterministicOfflineAdvisor()
            answer = self.provider.synthesize(question, intent, tool_results)
        calculations = [
            result
            for result in tool_results.values()
            if isinstance(result, CalculationResult)
        ]
        validation = validate_advisory_answer(answer, calculations)
        return AdvisoryRun(answer, validation, tool_results)
