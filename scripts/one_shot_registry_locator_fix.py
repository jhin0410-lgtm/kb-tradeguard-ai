from pathlib import Path


SOURCE_PATH = Path("src/intelligence/transaction_decision_brief.py")
TEST_PATH = Path("tests/test_transaction_decision_brief.py")


source = SOURCE_PATH.read_text(encoding="utf-8")
helper_name = "def _stable_registry_locator("
if helper_name not in source:
    marker = "def _registry_source(\n"
    position = source.find(marker)
    if position < 0:
        raise SystemExit("registry source function marker was not found")
    helper = '''def _stable_registry_locator(path: Path) -> str:
    """Return a checkout-independent locator for an auditable project registry."""

    parts = path.resolve().parts
    for index in range(len(parts) - 1):
        if parts[index : index + 2] == ("data", "reference"):
            return Path(*parts[index:]).as_posix()
    return f"project-rule://transaction-decision-brief/{path.name}"


'''
    source = source[:position] + helper + source[position:]

old_locator = "        source_locator=path.as_posix(),\n"
new_locator = "        source_locator=_stable_registry_locator(path),\n"
if old_locator not in source:
    if new_locator not in source:
        raise SystemExit("registry source locator assignment was not found")
else:
    source = source.replace(old_locator, new_locator, 1)
SOURCE_PATH.write_text(source, encoding="utf-8")


tests = TEST_PATH.read_text(encoding="utf-8")
old_import = '''    TransactionDecisionBriefRequest,
    apply_transaction_decision_brief,
    build_transaction_decision_brief,
    load_transaction_decision_brief_registry,
)'''
new_import = '''    TransactionDecisionBriefRequest,
    apply_transaction_decision_brief,
    build_transaction_decision_brief,
    default_transaction_decision_brief_registry_path,
    load_transaction_decision_brief_registry,
)'''
if "default_transaction_decision_brief_registry_path" not in tests:
    if old_import not in tests:
        raise SystemExit("decision brief import block was not found")
    tests = tests.replace(old_import, new_import, 1)

test_name = "def test_registry_source_locator_is_checkout_independent(tmp_path):"
if test_name not in tests:
    marker = "def test_high_concerns_create_conditions_before_commitment_and_rank_deterministically():\n"
    position = tests.find(marker)
    if position < 0:
        raise SystemExit("registry test insertion marker was not found")
    regression = '''def test_registry_source_locator_is_checkout_independent(tmp_path):
    registry_bytes = default_transaction_decision_brief_registry_path().read_bytes()
    first_path = (
        tmp_path
        / "checkout-a"
        / "data"
        / "reference"
        / "transaction_decision_brief_rules_v1.json"
    )
    second_path = (
        tmp_path
        / "checkout-b"
        / "data"
        / "reference"
        / "transaction_decision_brief_rules_v1.json"
    )
    for path in (first_path, second_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(registry_bytes)

    case = _case()
    request = _request(case)
    first_case, first_brief, _ = apply_transaction_decision_brief(
        case,
        request,
        registry_path=first_path,
    )
    second_case, second_brief, _ = apply_transaction_decision_brief(
        case,
        request,
        registry_path=second_path,
    )

    assert first_brief.source.source_locator == (
        "data/reference/transaction_decision_brief_rules_v1.json"
    )
    assert first_brief.source == second_brief.source
    assert first_case.case_hash == second_case.case_hash


'''
    tests = tests[:position] + regression + tests[position:]
TEST_PATH.write_text(tests, encoding="utf-8")
