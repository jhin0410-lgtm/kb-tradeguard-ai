from pathlib import Path

scenario_path = Path("src/copilot_scenarios.py")
source = scenario_path.read_text(encoding="utf-8")

helper_marker = "def propose_scenarios(case: UnifiedCopilotCase) -> ScenarioProposalSet:\n"
helper = '''def _usable_fx_currencies(case: UnifiedCopilotCase) -> set[str]:
    """Return currencies with a disclosed positive KRW spot reference."""

    asset = case.official_fx_reference
    if (
        asset is None
        or asset.status not in {"available", "partial"}
        or asset.payload is None
    ):
        return set()
    payload = asset.payload
    if isinstance(payload, dict):
        if all(isinstance(value, (int, float)) for value in payload.values()):
            return {
                str(currency).upper()
                for currency, value in payload.items()
                if float(value) > 0
            }
        payload = [payload]
    currencies: set[str] = set()
    for row in payload:
        currency = str(row.get("currency") or "").upper()
        value = row.get("spot_rate_krw", row.get("rate"))
        try:
            usable = value is not None and float(value) > 0
        except (TypeError, ValueError):
            usable = False
        if currency and usable:
            currencies.add(currency)
    return currencies


'''
if "def _usable_fx_currencies(" not in source:
    position = source.find(helper_marker)
    if position < 0:
        raise SystemExit("propose_scenarios marker was not found")
    source = source[:position] + helper + source[position:]

old = '''    imports = [row for row in case.approved_transactions if _direction(row) == "import"]
    cost_missing = [] if imports else ["approved import transaction"]
    cost_payload = {
        "type": "import_cost_increase",
        "transaction_ids": [_transaction_id(row) for row in imports if _transaction_id(row)],
        "increase_percent": 10,
        "case_hash": source_case_hash,
    }
'''
new = '''    imports = [row for row in case.approved_transactions if _direction(row) == "import"]
    target_import_ids = [
        transaction_id
        for row in imports
        if (transaction_id := _transaction_id(row)) is not None
    ]
    cost_missing: list[str] = []
    if not imports:
        cost_missing.append("approved import transaction")
    elif len(target_import_ids) != len(imports):
        cost_missing.append("transaction_id for each approved import transaction")

    assumptions = case.monthly_cost_assumptions
    for input_name in ("monthly_fixed_cost_krw", "current_cash_krw"):
        if assumptions.get(input_name) in (None, ""):
            cost_missing.append(input_name)

    transaction_currencies = _active_currencies(case)
    if any(not row.get("currency") for row in case.approved_transactions):
        cost_missing.append("currency for each approved transaction")
    usable_fx_currencies = _usable_fx_currencies(case)
    if not usable_fx_currencies:
        cost_missing.append("official or disclosed FX reference")
    else:
        cost_missing.extend(
            f"FX reference for transaction currency: {currency}"
            for currency in transaction_currencies
            if currency not in usable_fx_currencies
        )

    cost_payload = {
        "type": "import_cost_increase",
        "transaction_ids": target_import_ids,
        "increase_percent": 10,
        "case_hash": source_case_hash,
    }
'''
if old not in source:
    raise SystemExit("import-cost readiness block was not found")
source = source.replace(old, new, 1)
source = source.replace(
    '''            target_transaction_ids=[
                _transaction_id(row) for row in imports if _transaction_id(row)
            ],
''',
    '''            target_transaction_ids=target_import_ids,
''',
    1,
)
source = source.replace(
    '''            required_inputs=["approved import transaction"],
''',
    '''            required_inputs=[
                "approved import transaction",
                "transaction_id for each approved import transaction",
                "monthly_fixed_cost_krw",
                "current_cash_krw",
                "official or disclosed FX reference for each transaction currency",
            ],
''',
    1,
)
scenario_path.write_text(source, encoding="utf-8")

test_path = Path("tests/test_copilot_scenarios.py")
tests = test_path.read_text(encoding="utf-8")
tests = tests.replace(
    '''                "amount_fc": 500000,
                "expected_date": "2026-11-30",
''',
    '''                "amount_fc": 500000,
                "probability": 1.0,
                "expected_date": "2026-11-30",
''',
    1,
)
tests = tests.replace(
    '''                "amount_fc": 220000,
                "expected_date": "2026-10-15",
''',
    '''                "amount_fc": 220000,
                "probability": 1.0,
                "expected_date": "2026-10-15",
''',
    1,
)
tests = tests.replace(
    '''        "monthly_cost_assumptions": {"monthly_fixed_cost_krw": 50000000},
''',
    '''        "monthly_cost_assumptions": {
            "monthly_fixed_cost_krw": 50000000,
            "current_cash_krw": 100000000,
        },
''',
    1,
)
tests = tests.replace(
    "def test_missing_cost_assumptions_block_delay_and_combined_only():\n",
    "def test_missing_cost_assumptions_block_cashflow_scenarios():\n",
    1,
)
tests = tests.replace(
    '''    assert statuses["combined_stress"] == "blocked"
    assert statuses["fx_shock"] == "ready"
    assert "monthly cost assumptions" in proposals.candidates[0].missing_inputs
''',
    '''    assert statuses["combined_stress"] == "blocked"
    assert statuses["import_cost_increase"] == "blocked"
    assert statuses["fx_shock"] == "ready"
    assert "monthly cost assumptions" in proposals.candidates[0].missing_inputs
    import_candidate = next(
        item
        for item in proposals.candidates
        if item.scenario_type == "import_cost_increase"
    )
    assert {"monthly_fixed_cost_krw", "current_cash_krw"}.issubset(
        import_candidate.missing_inputs
    )
''',
    1,
)
tests = tests.replace(
    '''    assert statuses["combined_stress"] == "blocked"
    assert statuses["settlement_delay"] == "ready"
''',
    '''    assert statuses["combined_stress"] == "blocked"
    assert statuses["import_cost_increase"] == "blocked"
    assert statuses["settlement_delay"] == "ready"
''',
    1,
)
insert_marker = "def test_no_import_blocks_import_cost_candidate():\n"
regressions = '''@pytest.mark.parametrize(
    ("monthly_cost_assumptions", "missing_input"),
    [
        ({"monthly_fixed_cost_krw": 50000000}, "current_cash_krw"),
        ({"current_cash_krw": 100000000}, "monthly_fixed_cost_krw"),
    ],
)
def test_import_cost_candidate_requires_each_cash_assumption(
    monthly_cost_assumptions,
    missing_input,
):
    candidate = next(
        item
        for item in propose_scenarios(
            _case(monthly_cost_assumptions=monthly_cost_assumptions)
        ).candidates
        if item.scenario_type == "import_cost_increase"
    )

    assert candidate.readiness == "blocked"
    assert missing_input in candidate.missing_inputs


def test_import_cost_candidate_requires_transaction_ids():
    transactions = [dict(item) for item in _case().approved_transactions]
    transactions[1].pop("transaction_id")
    candidate = next(
        item
        for item in propose_scenarios(
            _case(approved_transactions=transactions)
        ).candidates
        if item.scenario_type == "import_cost_increase"
    )

    assert candidate.readiness == "blocked"
    assert "transaction_id for each approved import transaction" in candidate.missing_inputs
    assert candidate.target_transaction_ids == []


def test_import_cost_candidate_requires_rate_for_every_transaction_currency():
    transactions = [dict(item) for item in _case().approved_transactions]
    transactions[1]["currency"] = "EUR"
    candidate = next(
        item
        for item in propose_scenarios(
            _case(approved_transactions=transactions)
        ).candidates
        if item.scenario_type == "import_cost_increase"
    )

    assert candidate.readiness == "blocked"
    assert "FX reference for transaction currency: EUR" in candidate.missing_inputs


'''
if "def test_import_cost_candidate_requires_each_cash_assumption(" not in tests:
    position = tests.find(insert_marker)
    if position < 0:
        raise SystemExit("import-cost test insertion marker was not found")
    tests = tests[:position] + regressions + tests[position:]
test_path.write_text(tests, encoding="utf-8")
