from datetime import date

import pandas as pd
import pytest

from src.advisor_tools import ReadOnlyAdvisorTools
from src.copilot_case import CaseDataAsset, CaseIdentity, UnifiedCopilotCase
from src.copilot_execution import GovernedScenarioExecutor
from src.copilot_fx_execution import build_fx_shock_execution_contract
from src.copilot_scenarios import build_execution_request, propose_scenarios


def _transactions():
    return pd.DataFrame(
        [
            {
                "transaction_id": "EXP-USD",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "probability": 1.0,
                "status": "expected",
                "expected_date": "2026-11-30",
            },
            {
                "transaction_id": "IMP-USD",
                "transaction_type": "import",
                "currency": "USD",
                "amount_fc": 200000,
                "probability": 1.0,
                "status": "confirmed",
                "expected_date": "2026-10-15",
            },
            {
                "transaction_id": "EXP-EUR",
                "transaction_type": "export",
                "currency": "EUR",
                "amount_fc": 120000,
                "probability": 1.0,
                "status": "expected",
                "expected_date": "2026-12-15",
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
            },
            {
                "currency": "EUR",
                "spot_rate_krw": 1500.0,
                "krw_interest_rate": 0.03,
                "foreign_interest_rate": 0.025,
            },
        ]
    )


def _company():
    return {
        "as_of_date": "2026-08-01",
        "foreign_cash": {"USD": 40000, "EUR": 10000},
        "monthly_fixed_cost_krw": 50000000,
        "current_cash_krw": 100000000,
    }


def _case():
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-FX-EXEC-001",
            analysis_as_of_date=date(2026, 8, 1),
        ),
        approved_transactions=_transactions().to_dict("records"),
        foreign_cash_positions=[
            {"currency": "USD", "amount_fc": 40000},
            {"currency": "EUR", "amount_fc": 10000},
        ],
        monthly_cost_assumptions={"monthly_fixed_cost_krw": 50000000},
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
        if item.scenario_type == "fx_shock"
    )


def _executor():
    return GovernedScenarioExecutor(
        ReadOnlyAdvisorTools(_transactions(), _fx_rates(), _company())
    )


def test_contract_converts_disclosed_percent_to_fraction():
    case = _case()
    request = build_execution_request(case, _candidate(case), human_approved=True)
    contract = build_fx_shock_execution_contract(request)
    assert contract.scenario_percentages == [-0.05]
    assert contract.analysis_basis == "Expected transaction exposure"
    assert contract.hedge_ratios == [0.0, 0.3, 0.5, 0.7, 1.0]
    assert contract.tenor_months == 3
    assert contract.spread == 0.0


def test_fx_shock_executes_once_per_active_currency():
    case = _case()
    updated, outcome = _executor().execute(
        case, _candidate(case), human_approved=True
    )
    assert outcome.status == "executed"
    assert len(outcome.calculation_ids) == 2
    assert set(outcome.calculation_ids) == set(updated.calculations)
    assert {
        result.input_assumptions["currency"]
        for result in updated.calculations.values()
    } == {"USD", "EUR"}


def test_fx_results_use_only_disclosed_minus_five_percent_shock():
    case = _case()
    updated, _ = _executor().execute(case, _candidate(case), human_approved=True)
    for result in updated.calculations.values():
        assert result.input_assumptions["scenarios"] == [-0.05]
        assert {row["scenario_pct"] for row in result.result} == {-0.05}


def test_executed_fx_scenario_references_all_calculation_ids():
    case = _case()
    candidate = _candidate(case)
    updated, outcome = _executor().execute(case, candidate, human_approved=True)
    scenario = next(item for item in updated.scenarios if item.scenario_id == candidate.scenario_id)
    assert scenario.status == "executed"
    assert scenario.calculation_ids == outcome.calculation_ids


def test_fx_execution_preserves_theoretical_quote_limitation():
    case = _case()
    updated, outcome = _executor().execute(case, _candidate(case), human_approved=True)
    assert any("실제 KB 실행 가능 견적이 아닙니다" in item for item in outcome.limitations)
    assert all(
        any("not an executable quote" in limitation for limitation in result.limitations)
        for result in updated.calculations.values()
    )


def test_fx_execution_still_requires_human_approval():
    case = _case()
    with pytest.raises(ValueError, match="explicit human approval"):
        _executor().execute(case, _candidate(case), human_approved=False)


def test_contract_rejects_missing_currency_scope():
    case = _case()
    candidate = _candidate(case).model_copy(
        update={"parameter_changes": {"fx_shock_percent": -5, "currencies": []}}
    )
    request = build_execution_request(case, candidate, human_approved=True)
    with pytest.raises(ValueError, match="at least one currency"):
        build_fx_shock_execution_contract(request)
