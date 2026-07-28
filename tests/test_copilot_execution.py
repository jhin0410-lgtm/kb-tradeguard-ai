from datetime import date

import pandas as pd
import pytest

from src.advisor_tools import ReadOnlyAdvisorTools
from src.copilot_case import CaseDataAsset, CaseIdentity, UnifiedCopilotCase
from src.copilot_execution import GovernedScenarioExecutor
from src.copilot_scenarios import propose_scenarios


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
                "amount_fc": 220000,
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
            case_id="CASE-EXEC-001",
            analysis_as_of_date=date(2026, 8, 1),
        ),
        approved_transactions=_transactions().to_dict("records"),
        foreign_cash_positions=[{"currency": "USD", "amount_fc": 40000}],
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


def _executor():
    return GovernedScenarioExecutor(
        ReadOnlyAdvisorTools(_transactions(), _fx_rates(), _company())
    )


def _candidate(case, scenario_type):
    return next(
        item
        for item in propose_scenarios(case).candidates
        if item.scenario_type == scenario_type
    )


def _delay_candidate(case):
    return _candidate(case, "settlement_delay")


def test_delay_scenario_executes_through_deterministic_tool():
    case = _case()
    updated, outcome = _executor().execute(
        case, _delay_candidate(case), human_approved=True
    )
    assert outcome.status == "executed"
    assert len(outcome.calculation_ids) == 1
    assert outcome.calculation_ids[0] in updated.calculations
    assert updated.calculations[outcome.calculation_ids[0]].calculation_name == (
        "Cash-flow settlement delay scenario"
    )


def test_executed_scenario_references_calculation_id():
    case = _case()
    candidate = _delay_candidate(case)
    updated, outcome = _executor().execute(case, candidate, human_approved=True)
    scenario = next(item for item in updated.scenarios if item.scenario_id == candidate.scenario_id)
    assert scenario.status == "executed"
    assert scenario.calculation_ids == outcome.calculation_ids


def test_execution_requires_explicit_human_approval():
    case = _case()
    with pytest.raises(ValueError, match="explicit human approval"):
        _executor().execute(case, _delay_candidate(case), human_approved=False)


def test_unsupported_candidate_is_not_silently_executed():
    case = _case()
    candidate = next(
        item
        for item in propose_scenarios(case).candidates
        if item.scenario_type == "combined_stress"
    )
    with pytest.raises(NotImplementedError, match="No governed deterministic executor"):
        _executor().execute(case, candidate, human_approved=True)


def test_execution_preserves_original_case_and_records_snapshot_change():
    case = _case()
    before = case.case_hash
    updated, outcome = _executor().execute(
        case, _delay_candidate(case), human_approved=True
    )
    assert case.calculations == {}
    assert case.scenarios == []
    assert case.case_hash == before
    assert outcome.case_before_hash == before
    assert outcome.case_after_hash == updated.case_hash
    assert updated.case_hash != before


@pytest.mark.parametrize("scenario_type", ["settlement_delay", "fx_shock"])
def test_execution_rejects_advisor_tools_from_different_case_snapshot(scenario_type):
    case = _case()
    stale_transactions = _transactions()
    stale_transactions.loc[
        stale_transactions["transaction_id"] == "EXP-001", "amount_fc"
    ] = 750000
    executor = GovernedScenarioExecutor(
        ReadOnlyAdvisorTools(stale_transactions, _fx_rates(), _company())
    )

    with pytest.raises(ValueError, match="input snapshot does not match"):
        executor.execute(
            case,
            _candidate(case, scenario_type),
            human_approved=True,
        )


def test_delay_execution_rejects_mismatched_fx_and_cash_inputs():
    case = _case()
    candidate = _candidate(case, "settlement_delay")

    changed_fx = _fx_rates()
    changed_fx.loc[changed_fx["currency"] == "USD", "spot_rate_krw"] = 1400.0
    fx_executor = GovernedScenarioExecutor(
        ReadOnlyAdvisorTools(_transactions(), changed_fx, _company())
    )
    with pytest.raises(ValueError, match="input snapshot does not match"):
        fx_executor.execute(case, candidate, human_approved=True)

    changed_company = dict(_company())
    changed_company["current_cash_krw"] = 125000000
    cash_executor = GovernedScenarioExecutor(
        ReadOnlyAdvisorTools(_transactions(), _fx_rates(), changed_company)
    )
    with pytest.raises(ValueError, match="input snapshot does not match"):
        cash_executor.execute(case, candidate, human_approved=True)


def test_fx_execution_rejects_mismatched_rates_and_foreign_cash_inputs():
    case = _case()
    candidate = _candidate(case, "fx_shock")

    changed_fx = _fx_rates()
    changed_fx.loc[changed_fx["currency"] == "USD", "foreign_interest_rate"] = 0.06
    rate_executor = GovernedScenarioExecutor(
        ReadOnlyAdvisorTools(_transactions(), changed_fx, _company())
    )
    with pytest.raises(ValueError, match="input snapshot does not match"):
        rate_executor.execute(case, candidate, human_approved=True)

    changed_company = dict(_company())
    changed_company["foreign_cash"] = {"USD": 65000}
    cash_executor = GovernedScenarioExecutor(
        ReadOnlyAdvisorTools(_transactions(), _fx_rates(), changed_company)
    )
    with pytest.raises(ValueError, match="input snapshot does not match"):
        cash_executor.execute(case, candidate, human_approved=True)
