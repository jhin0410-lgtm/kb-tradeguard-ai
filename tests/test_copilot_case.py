from datetime import date

import pytest

from src.advisor_models import CalculationResult
from src.copilot_case import (
    CaseDataAsset,
    CaseEvidenceItem,
    CaseFinding,
    CaseIdentity,
    CaseScenario,
    MissingInput,
    UnifiedCopilotCase,
)


def _calculation(calculation_id: str = "CALC-TEST-001") -> CalculationResult:
    return CalculationResult(
        calculation_name="Test calculation",
        input_assumptions={"basis": "expected"},
        result={"value": 10},
        unit="KRW",
        as_of_date="2026-07-26",
        data_source="synthetic test fixture",
        limitations=[],
        calculation_id=calculation_id,
        calculation_engine_version="test/1.0",
        normalized_input_hash="abc",
        calculation_timestamp="2026-07-26T00:00:00+00:00",
        source_data_identifiers=["fixture:test"],
        selected_analysis_basis="expected",
    )


def _case() -> UnifiedCopilotCase:
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-001",
            company_name="한빛테크",
            analysis_as_of_date=date(2026, 7, 26),
        ),
        evidence=[
            CaseEvidenceItem(
                evidence_id="EVID-001",
                evidence_type="commercial_invoice",
                source_name="invoice.pdf",
                status="approved",
                linked_transaction_ids=["EXP-001"],
            ),
            CaseEvidenceItem(
                evidence_id="EVID-002",
                evidence_type="purchase_order",
                source_name="po.pdf",
                status="review_required",
            ),
        ],
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "expected_date": "2026-11-30",
            }
        ],
        foreign_cash_positions=[{"currency": "USD", "amount_fc": 40000}],
        monthly_cost_assumptions={"fixed_cost_krw": 50000000},
        official_fx_reference=CaseDataAsset(
            asset_name="USD/KRW reference",
            status="available",
            source="KEXIM",
            as_of_date=date(2026, 7, 25),
            payload={"USD": 1330.0},
        ),
        financial_context=CaseDataAsset(
            asset_name="financial screening context",
            status="partial",
            source="OpenDART",
            payload={"screening_only": True},
            limitations=["재무건전성 사전 스크리닝이며 공식 신용등급이 아닙니다."],
        ),
        policy_context=CaseDataAsset(
            asset_name="reviewed policy corpus",
            status="available",
            source="bundled approved references",
        ),
        missing_inputs=[
            MissingInput(
                input_name="existing hedge contracts",
                reason="Not present in reviewed evidence",
                blocks=["net post-hedge position"],
                requested_from="customer",
            )
        ],
    )


def test_capabilities_are_derived_from_case_state():
    capabilities = _case().capabilities

    assert capabilities.approved_transactions is True
    assert capabilities.document_evidence is True
    assert capabilities.foreign_cash_positions is True
    assert capabilities.monthly_cost_assumptions is True
    assert capabilities.official_fx_reference is True
    assert capabilities.financial_context is True
    assert capabilities.policy_corpus is True


def test_unresolved_evidence_and_audit_summary_are_explicit():
    case = _case()
    summary = case.audit_summary()

    assert case.unresolved_evidence_ids == ["EVID-002"]
    assert summary["approved_transaction_count"] == 1
    assert summary["approved_evidence_count"] == 1
    assert summary["missing_inputs"] == ["existing hedge contracts"]
    assert summary["calculation_ids"] == []
    assert len(summary["case_hash"]) == 64


def test_case_hash_is_stable_across_creation_timestamp_changes():
    first = _case()
    second = _case()

    assert first.case_hash == second.case_hash


def test_add_calculation_returns_copy_and_preserves_original():
    case = _case()
    updated = case.add_calculation(_calculation())

    assert case.calculations == {}
    assert list(updated.calculations) == ["CALC-TEST-001"]
    assert updated.audit_summary()["calculation_ids"] == ["CALC-TEST-001"]


def test_calculation_dictionary_key_must_match_result_id():
    with pytest.raises(ValueError, match="keys must equal"):
        UnifiedCopilotCase(
            identity=CaseIdentity(case_id="CASE-BAD"),
            calculations={"WRONG-ID": _calculation()},
        )


def test_executed_scenario_requires_deterministic_result_reference():
    with pytest.raises(ValueError, match="Executed scenarios"):
        CaseScenario(
            scenario_id="SCN-001",
            name="30-day collection delay",
            rationale="Material receivable timing stress",
            status="executed",
            parameter_changes={"delay_days": 30},
        )


def test_noninformational_finding_requires_grounding():
    with pytest.raises(ValueError, match="must reference"):
        CaseFinding(
            finding_id="FIND-001",
            title="Liquidity risk",
            summary="A shortfall may occur.",
            priority="high",
            category="liquidity",
        )


def test_grounded_finding_accepts_calculation_reference():
    finding = CaseFinding(
        finding_id="FIND-002",
        title="Liquidity risk",
        summary="A deterministic shortfall result was produced.",
        priority="high",
        category="liquidity",
        calculation_ids=["CALC-TEST-001"],
    )

    assert finding.calculation_ids == ["CALC-TEST-001"]


def test_missing_assets_do_not_create_false_capabilities():
    case = UnifiedCopilotCase(identity=CaseIdentity(case_id="CASE-EMPTY"))

    assert case.executable_case is False
    assert case.capabilities.model_dump() == {
        "approved_transactions": False,
        "document_evidence": False,
        "foreign_cash_positions": False,
        "monthly_cost_assumptions": False,
        "official_fx_reference": False,
        "financial_context": False,
        "policy_corpus": False,
    }
