import json
from pathlib import Path

import pytest

from src.intelligence.trade_document_rules import evaluate_trade_document
from src.trade_finance_domain import PaymentStructure, TradeDocumentProfile


DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "gold"
    / "trade_document_gold_v1.json"
)


def _dataset():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _rule_ids(findings):
    identifiers = set()
    for finding in findings:
        prefix = "CLAUSE-"
        suffix = f"-{finding.document_id}"
        assert finding.clause_finding_id.startswith(prefix)
        assert finding.clause_finding_id.endswith(suffix)
        identifiers.add(finding.clause_finding_id[len(prefix) : -len(suffix)])
    return identifiers


def test_gold_dataset_metadata_and_case_ids_are_governed():
    dataset = _dataset()

    assert dataset["dataset_version"] == "trade-document-gold/1.0"
    assert dataset["source_mode"] == "synthetic_gold"
    assert "not legal opinions" in dataset["authority_boundary"]
    assert len(dataset["cases"]) == 8
    case_ids = [item["case_id"] for item in dataset["cases"]]
    assert len(case_ids) == len(set(case_ids))


@pytest.mark.parametrize("case", _dataset()["cases"], ids=lambda item: item["case_id"])
def test_gold_case_expected_and_forbidden_rule_ids(case):
    document = TradeDocumentProfile.model_validate(case["document"])
    payment = PaymentStructure.model_validate(case["payment_structure"])

    actual = _rule_ids(evaluate_trade_document(document, payment))

    assert set(case["expected_rule_ids"]).issubset(actual)
    assert set(case["forbidden_rule_ids"]).isdisjoint(actual)


def test_gold_cases_keep_documents_and_payments_transaction_linked():
    for case in _dataset()["cases"]:
        document = TradeDocumentProfile.model_validate(case["document"])
        payment = PaymentStructure.model_validate(case["payment_structure"])

        assert payment.transaction_id in document.linked_transaction_ids
        assert payment.payment_structure_id == document.payment_structure_id
        assert document.record_status in {"verified", "partial"}
        assert payment.record_status in {"verified", "partial"}
