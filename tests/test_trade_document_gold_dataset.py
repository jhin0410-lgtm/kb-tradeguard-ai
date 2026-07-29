from src.intelligence.trade_document_gold import (
    iter_semantic_preserving_gold_mutations,
    list_trade_document_gold_cases,
    load_trade_document_gold_dataset,
)
from src.intelligence.trade_document_rules import (
    evaluate_trade_document,
    load_trade_document_rule_registry,
)


GOLD_CASES = list_trade_document_gold_cases()
MUTATIONS = list(iter_semantic_preserving_gold_mutations(GOLD_CASES))


def _rule_ids(findings):
    identifiers = set()
    for finding in findings:
        prefix = "CLAUSE-"
        suffix = f"-{finding.document_id}"
        assert finding.clause_finding_id.startswith(prefix)
        assert finding.clause_finding_id.endswith(suffix)
        identifiers.add(finding.clause_finding_id[len(prefix) : -len(suffix)])
    return identifiers


def _evaluate(document, payment):
    return _rule_ids(evaluate_trade_document(document, payment))


def test_gold_dataset_metadata_and_case_ids_are_governed():
    dataset = load_trade_document_gold_dataset()

    assert dataset["dataset_version"] == "trade-document-gold/1.1"
    assert dataset["source_mode"] == "synthetic_gold"
    assert "not legal opinions" in dataset["authority_boundary"]
    assert len(GOLD_CASES) == 30
    case_ids = [item.case_id for item in GOLD_CASES]
    assert len(case_ids) == len(set(case_ids))
    assert all(item.tags for item in GOLD_CASES)


def test_gold_cases_match_the_exact_expected_rule_set():
    for case in GOLD_CASES:
        actual = _evaluate(case.document, case.payment_structure)
        assert actual == set(case.expected_rule_ids), case.case_id


def test_gold_dataset_covers_every_governed_trade_document_rule():
    governed_rule_ids = {
        item.rule_id for item in load_trade_document_rule_registry().rules
    }
    covered_rule_ids = {
        rule_id for case in GOLD_CASES for rule_id in case.expected_rule_ids
    }

    assert covered_rule_ids == governed_rule_ids


def test_gold_dataset_contains_clean_negative_controls_for_both_document_kinds():
    clean_cases = [item for item in GOLD_CASES if "negative_control" in item.tags]

    assert len(clean_cases) >= 5
    assert all(not item.expected_rule_ids for item in clean_cases)
    assert {item.document.document_type for item in clean_cases} >= {
        "contract",
        "letter_of_credit",
    }


def test_gold_cases_keep_documents_and_payments_transaction_linked():
    for case in GOLD_CASES:
        assert case.payment_structure.transaction_id in case.document.linked_transaction_ids
        assert (
            case.payment_structure.payment_structure_id
            == case.document.payment_structure_id
        )
        assert case.document.record_status in {"verified", "partial"}
        assert case.payment_structure.record_status in {"verified", "partial"}


def test_semantic_preserving_mutation_suite_is_large_unique_and_rule_invariant():
    assert len(MUTATIONS) == 150
    mutation_ids = [item.mutation_id for item in MUTATIONS]
    assert len(mutation_ids) == len(set(mutation_ids))
    assert {item.mutation_kind for item in MUTATIONS} == {
        "source_metadata",
        "identifier_relabel",
        "transaction_relink",
        "partial_status",
        "irrelevant_reviewed_field",
    }

    for mutation in MUTATIONS:
        actual = _evaluate(mutation.document, mutation.payment_structure)
        assert actual == set(mutation.expected_rule_ids), mutation.mutation_id
        assert (
            mutation.payment_structure.transaction_id
            in mutation.document.linked_transaction_ids
        )
        assert (
            mutation.payment_structure.payment_structure_id
            == mutation.document.payment_structure_id
        )
