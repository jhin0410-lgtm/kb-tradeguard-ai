from datetime import date

import pytest

from src.advisor_models import CalculationResult
from src.copilot_case import (
    CaseEvidenceItem,
    CaseFinding,
    CaseIdentity,
    MissingInput,
    UnifiedCopilotCase,
)
from src.copilot_reasoning import RiskChainNode, build_integrated_risk_reasoning


def _calc(calc_id: str) -> CalculationResult:
    return CalculationResult(
        calculation_name="Cash-flow shortfall",
        input_assumptions={"cash_flow_view": "expected"},
        result={"shortfall": 1000000},
        unit="KRW",
        as_of_date="2026-07-26",
        data_source="deterministic test fixture",
        limitations=[],
        calculation_id=calc_id,
        calculation_engine_version="test/1.0",
        normalized_input_hash="a" * 64,
        calculation_timestamp="2026-07-26T00:00:00+00:00",
        source_data_identifiers=["fixture"],
        selected_analysis_basis="expected",
    )


def _case() -> UnifiedCopilotCase:
    calc_id = "CALC-CASH-001"
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-001",
            company_name="Example Exporter",
            analysis_as_of_date=date(2026, 7, 26),
        ),
        evidence=[
            CaseEvidenceItem(
                evidence_id="EVD-001",
                evidence_type="invoice",
                source_name="invoice.pdf",
                status="approved",
            )
        ],
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
            }
        ],
        calculations={calc_id: _calc(calc_id)},
        findings=[
            CaseFinding(
                finding_id="FND-001",
                title="Settlement delay may widen the liquidity gap",
                summary="The deterministic cash-flow result shows a shortfall under the reviewed basis.",
                priority="high",
                category="liquidity",
                calculation_ids=[calc_id],
                evidence_ids=["EVD-001"],
            )
        ],
        missing_inputs=[
            MissingInput(
                input_name="existing forward contracts",
                reason="Not supplied",
                blocks=["net hedge-position review"],
            )
        ],
    )


def test_builds_fact_inference_and_consultation_nodes():
    report = build_integrated_risk_reasoning(_case())
    assert len(report.chains) == 1
    kinds = [node.kind for node in report.chains[0].nodes]
    assert kinds == [
        "document_fact",
        "calculated_fact",
        "inference",
        "consultation_priority",
    ]


def test_calculated_fact_keeps_calculation_id():
    chain = build_integrated_risk_reasoning(_case()).chains[0]
    calculated = next(node for node in chain.nodes if node.kind == "calculated_fact")
    assert calculated.calculation_ids == ["CALC-CASH-001"]


def test_document_fact_keeps_evidence_id():
    chain = build_integrated_risk_reasoning(_case()).chains[0]
    document = next(node for node in chain.nodes if node.kind == "document_fact")
    assert document.evidence_ids == ["EVD-001"]


def test_inference_references_only_earlier_nodes():
    chain = build_integrated_risk_reasoning(_case()).chains[0]
    inference = next(node for node in chain.nodes if node.kind == "inference")
    prior_ids = {node.node_id for node in chain.nodes if node.sequence < inference.sequence}
    assert set(inference.derived_from_node_ids) <= prior_ids


def test_missing_inputs_are_disclosed_on_chain():
    chain = build_integrated_risk_reasoning(_case()).chains[0]
    assert "existing forward contracts" in chain.unresolved_gaps


def test_chain_id_is_stable_for_same_case_snapshot():
    first = build_integrated_risk_reasoning(_case()).chains[0].chain_id
    second = build_integrated_risk_reasoning(_case()).chains[0].chain_id
    assert first == second


def test_reasoning_does_not_mutate_case():
    case = _case()
    before = case.case_hash
    build_integrated_risk_reasoning(case)
    assert case.case_hash == before


def test_direct_fact_requires_reference():
    with pytest.raises(ValueError):
        RiskChainNode(
            node_id="NODE-X",
            sequence=1,
            kind="calculated_fact",
            statement="Unsupported fact",
            confidence="high",
        )


def test_report_contains_required_authority_limits():
    report = build_integrated_risk_reasoning(_case())
    text = " ".join(report.limitations)
    assert "No financial values" in text
    assert "공식 신용등급" in text
    assert "product suitability" in report.chains[0].nodes[-1].limitations[0]
