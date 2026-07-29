from datetime import date

import pandas as pd
import pytest

from src.advisor_tools import ReadOnlyAdvisorTools
from src.copilot_case import CaseDataAsset, CaseIdentity, UnifiedCopilotCase
from src.copilot_execution import GovernedScenarioExecutor
from src.copilot_import_cost_execution import build_import_cost_execution_contract
from src.copilot_scenarios import build_execution_request, propose_scenarios


def _transactions():
    return pd.DataFrame(
        [
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "probability": 1.0,
                "status": "expected",
                "expected_date": "2026-09-30",
            },
            {
                "transaction_id": "IMP-001",
                "transaction_type": "import",
                "currency": "USD",
                "amount_fc": 200000,
                "probability": 1.0,
                "status": "confirmed",
                "expected_date": "2026-09-15",
            },
        ]
    )


def _fx_rates():
    return pd.DataFrame(
        [
            {
                "currency": "USD",
                "spot_rate_krw": 1350.0,
                "krw_interest_rate": 0.03,
                "foreign_interest_rate": 0.04,
            }
        ]
    )


def _company():
    return {
        "as_of_date": "2026-08-01",
        "foreign_cash": {"USD": 40000},
        "monthly_fixed_cost_krw": 50000000,
        "current_cash_krw": 100000000,
    }


def _case():
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-IMPORT-COST",
            analysis_as_of_date=date(2026, 8, 1),
        ),
        approved_transactions=_transactions().to_dict("records"),
        monthly_cost_assumptions={
            "monthly_fixed_cost_krw": 50000000,
            "current_cash_krw": 100000000,
        },
        official_fx_reference=CaseDataAsset(
            asset_name="public FX reference",
            status="available",
            source="test fixture",
            as_of_date=date(2026, 8, 1),
            payload=_fx_rates().to_dict("records"),
        ),
    )


def _candidate(case):
    return next(
        item
        for item in propose_scenarios(case).candidates
        if item.scenario_type == "import_cost_increase"
    )


def _executor():
    return GovernedScenarioExecutor(
        ReadOnlyAdvisorTools(_transactions(), _fx_rates(), _company())
    )


def test_import_cost_contract_converts_percentage_to_multiplier():
    case = _case()
    request = build_execution_request(case, _candidate(case), human_approved=True)
    contract = build_import_cost_execution_contract(request)
    assert contract.increase_percent == 10
    assert contract.increase_multiplier == pytest.approx(1.10)
    assert contract.target_transaction_ids == ["IMP-001"]


def test_import_cost_scenario_executes_and_attaches_calculation():
    case = _case()
    candidate = _candidate(case)
    updated, outcome = _executor().execute(case, candidate, human_approved=True)
    assert outcome.status == "executed"
    assert len(outcome.calculation_ids) == 1
    result = updated.calculations[outcome.calculation_ids[0]]
    assert result.calculation_name == "Import payment amount increase scenario"
    scenario = next(item for item in updated.scenarios if item.scenario_id == candidate.scenario_id)
    assert scenario.status == "executed"
    assert scenario.calculation_ids == outcome.calculation_ids


def test_only_targeted_import_amount_changes():
    case = _case()
    updated, outcome = _executor().execute(case, _candidate(case), human_approved=True)
    result = updated.calculations[outcome.calculation_ids[0]]
    assert len(result.result["changed_months"]) == 1
    changed = result.result["changed_months"][0]
    assert changed["incremental_import_outflow_krw"] == pytest.approx(27000000.0)
    assert result.input_assumptions["import_amount_increase_percent"] == 10


def test_import_cost_execution_preserves_original_case():
    case = _case()
    before = case.case_hash
    updated, outcome = _executor().execute(case, _candidate(case), human_approved=True)
    assert case.calculations == {}
    assert case.scenarios == []
    assert case.case_hash == before
    assert outcome.case_before_hash == before
    assert outcome.case_after_hash == updated.case_hash


def test_non_import_target_is_rejected():
    case = _case()
    candidate = _candidate(case).model_copy(update={"target_transaction_ids": ["EXP-001"]})
    with pytest.raises(ValueError, match="only approved import"):
        _executor().execute(case, candidate, human_approved=True)


def test_import_cost_result_discloses_stress_and_quote_limitations():
    case = _case()
    updated, outcome = _executor().execute(case, _candidate(case), human_approved=True)
    limitations = updated.calculations[outcome.calculation_ids[0]].limitations
    assert any("stress assumption" in item for item in limitations)
    assert any("not executable KB quotes" in item for item in limitations)
