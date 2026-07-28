from pathlib import Path


def append_once(path: str, marker: str, block: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return
    target.write_text(text.rstrip() + "\n\n\n" + block.strip() + "\n", encoding="utf-8")


append_once(
    "tests/test_copilot_execution.py",
    "def test_delay_execution_rejects_mismatched_fx_and_cash_inputs():",
    r'''
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
''',
)

append_once(
    "tests/test_copilot_scenarios.py",
    "def test_candidate_becomes_stale_when_nontransaction_execution_inputs_change():",
    r'''
def test_candidate_becomes_stale_when_nontransaction_execution_inputs_change():
    case = _case()
    candidate = next(
        item
        for item in propose_scenarios(case).ready_candidates
        if item.scenario_type == "settlement_delay"
    )

    changed_costs = case.model_copy(
        update={
            "monthly_cost_assumptions": {
                **case.monthly_cost_assumptions,
                "current_cash_krw": 125000000,
            }
        }
    )
    with pytest.raises(ValueError, match="different case snapshot"):
        build_execution_request(changed_costs, candidate, human_approved=True)

    changed_fx_asset = case.official_fx_reference.model_copy(
        update={"payload": {"USD": 1400.0}}
    )
    changed_fx = case.model_copy(update={"official_fx_reference": changed_fx_asset})
    with pytest.raises(ValueError, match="different case snapshot"):
        build_execution_request(changed_fx, candidate, human_approved=True)
''',
)

append_once(
    "tests/test_single_transaction_pipeline.py",
    "def test_capacity_cleanup_preserves_records_for_other_transactions():",
    r'''
def test_capacity_cleanup_preserves_records_for_other_transactions():
    first, _ = run_single_transaction_assessment(_full_case(), _request())
    capacity_calculation = next(
        calculation
        for calculation in first.calculations.values()
        if calculation.calculation_name == "Transaction financial capacity assessment"
    )
    capacity_signal = next(
        signal
        for signal in first.trade_finance.risk_signals
        if signal.source.source_id.startswith("TRANSACTION-CAPACITY-")
    )
    unrelated_calculation = capacity_calculation.model_copy(
        update={
            "calculation_id": "CALC-UNRELATED-CAPACITY",
            "input_assumptions": {
                **capacity_calculation.input_assumptions,
                "transaction_id": "EXP-OTHER",
            },
        }
    )
    unrelated_signal = capacity_signal.model_copy(
        update={
            "signal_id": "RISK-UNRELATED-CAPACITY",
            "affected_transaction_ids": ["EXP-OTHER"],
            "calculation_ids": [unrelated_calculation.calculation_id],
        }
    )
    augmented_domain = first.trade_finance.model_copy(
        update={
            "risk_signals": [
                *first.trade_finance.risk_signals,
                unrelated_signal,
            ]
        }
    )
    augmented = first.model_copy(
        update={
            "calculations": {
                **first.calculations,
                unrelated_calculation.calculation_id: unrelated_calculation,
            },
            "trade_finance": augmented_domain,
        }
    )

    updated, _ = run_single_transaction_assessment(
        augmented,
        _request(capacity_request=None),
    )

    assert unrelated_calculation.calculation_id in updated.calculations
    assert any(
        signal.signal_id == unrelated_signal.signal_id
        for signal in updated.trade_finance.risk_signals
    )
''',
)
