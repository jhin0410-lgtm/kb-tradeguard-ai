from datetime import date
from decimal import Decimal

import pytest

from src.intelligence.trade_document_rules import (
    build_document_risk_signals,
    evaluate_trade_document,
    load_trade_document_rule_registry,
    reviewed_terms_from_document,
)
from src.trade_finance_domain import (
    PaymentStructure,
    SourceReference,
    TradeDocumentProfile,
)


def _document_source(source_id="SRC-DOC"):
    return SourceReference(
        source_id=source_id,
        source_name="Reviewed synthetic trade document",
        source_tier="user_provided",
        source_kind="user_document",
        source_locator="fixture://trade-document",
        as_of_date=date(2026, 7, 26),
        effective_date_verified=True,
    )


def _contract(**updates):
    payload = {
        "document_id": "DOC-CONTRACT-001",
        "evidence_id": "EVID-CONTRACT-001",
        "document_type": "contract",
        "incoterms_rule": "FCA",
        "incoterms_year": 2020,
        "named_place": "Busan New Port, Republic of Korea",
        "payment_structure_id": "PAY-CONTRACT-001",
        "linked_transaction_ids": ["EXP-001"],
        "reviewed_fields": {
            "governing_law": "Republic of Korea",
            "dispute_resolution": "KCAB International arbitration in Seoul",
            "acceptance_period_days": 10,
            "buyer_unilateral_setoff_right": False,
            "buyer_unilateral_amendment_right": False,
        },
        "source": _document_source(),
        "record_status": "verified",
    }
    payload.update(updates)
    return TradeDocumentProfile(**payload)


def _contract_payment(payment_trigger="30 days after shipment"):
    return PaymentStructure(
        payment_structure_id="PAY-CONTRACT-001",
        transaction_id="EXP-001",
        method="open_account",
        tenor_days=30,
        deferred_payment_percent=Decimal("100"),
        payment_trigger=payment_trigger,
        source=_document_source("SRC-PAY"),
        record_status="verified",
    )


def _lc(**updates):
    payload = {
        "document_id": "DOC-LC-001",
        "evidence_id": "EVID-LC-001",
        "document_type": "letter_of_credit",
        "expiry_date": date(2026, 10, 31),
        "payment_structure_id": "PAY-LC-001",
        "linked_transaction_ids": ["EXP-001"],
        "reviewed_fields": {
            "latest_shipment_date": date(2026, 10, 1),
            "presentation_period_days": 21,
            "buyer_controlled_document_requirements": [],
            "expiry_place": "Seoul, Republic of Korea",
        },
        "source": _document_source("SRC-LC"),
        "record_status": "verified",
    }
    payload.update(updates)
    return TradeDocumentProfile(**payload)


def _lc_payment(governing_rules=None):
    return PaymentStructure(
        payment_structure_id="PAY-LC-001",
        transaction_id="EXP-001",
        method="letter_of_credit",
        issuing_bank="Example International Bank",
        irrevocable=True,
        governing_rules=governing_rules or ["UCP 600"],
        source=_document_source("SRC-LC-PAY"),
        record_status="verified",
    )


def test_rule_registry_has_unique_rules_and_valid_source_links():
    registry = load_trade_document_rule_registry()

    assert registry.registry_version == "trade-document-rules/1.0"
    assert len(registry.rules) >= 10
    assert len({rule.rule_id for rule in registry.rules}) == len(registry.rules)
    assert "legal advice" in registry.authority_boundary


def test_complete_contract_does_not_create_missing_core_term_findings():
    findings = evaluate_trade_document(_contract(), _contract_payment())
    ids = {finding.clause_finding_id for finding in findings}

    assert not any("INCOTERMS-RULE-MISSING" in item for item in ids)
    assert not any("INCOTERMS-YEAR-MISSING" in item for item in ids)
    assert not any("INCOTERMS-PLACE-MISSING" in item for item in ids)
    assert not any("GOVERNING-LAW-MISSING" in item for item in ids)
    assert not any("DISPUTE-ROUTE-MISSING" in item for item in ids)


def test_missing_contract_terms_are_grounded_and_actionable():
    contract = _contract(
        incoterms_year=None,
        named_place=None,
        reviewed_fields={
            "governing_law": None,
            "dispute_resolution": None,
            "acceptance_period_days": None,
            "buyer_unilateral_setoff_right": True,
            "buyer_unilateral_amendment_right": True,
        },
    )
    findings = evaluate_trade_document(contract, _contract_payment())
    by_locator = {finding.clause_locator: finding for finding in findings}

    assert by_locator["Delivery terms / Incoterms edition"].severity == "medium"
    assert by_locator["Delivery terms / named place or port"].severity == "high"
    assert by_locator["Set-off and deduction rights"].issue_type == "unilateral_right"
    assert by_locator["Contract amendment"].specialist_review == ["legal"]
    assert all(finding.evidence_ids == [contract.evidence_id] for finding in findings)
    assert all("legal advice" in finding.limitations[0] for finding in findings)


def test_unbounded_buyer_acceptance_payment_trigger_is_flagged():
    contract = _contract(
        reviewed_fields={
            "governing_law": "Republic of Korea",
            "dispute_resolution": "KCAB International arbitration",
            "acceptance_period_days": None,
            "buyer_unilateral_setoff_right": False,
            "buyer_unilateral_amendment_right": False,
        }
    )
    findings = evaluate_trade_document(
        contract,
        _contract_payment("Payment 30 days after buyer acceptance"),
    )

    finding = next(
        item for item in findings if item.issue_type == "buyer_controlled_condition"
    )
    assert finding.severity == "high"
    assert "indefinite" in finding.suggested_clarification_or_revision


def test_lc_expiry_before_latest_shipment_is_critical():
    lc = _lc(
        expiry_date=date(2026, 9, 15),
        reviewed_fields={
            "latest_shipment_date": date(2026, 10, 1),
            "presentation_period_days": 21,
            "buyer_controlled_document_requirements": [],
            "expiry_place": "Seoul, Republic of Korea",
        },
    )
    findings = evaluate_trade_document(lc, _lc_payment())

    timing = next(item for item in findings if "EXPIRY-BEFORE-SHIPMENT" in item.clause_finding_id)
    assert timing.severity == "critical"
    assert timing.issue_type == "timing_conflict"
    assert "expiry_date=2026-09-15" in timing.clause_excerpt


def test_lc_buyer_controlled_document_and_missing_ucp_are_separate_findings():
    lc = _lc(
        reviewed_fields={
            "latest_shipment_date": date(2026, 10, 1),
            "presentation_period_days": 21,
            "buyer_controlled_document_requirements": [
                "Certificate of acceptance issued and signed only by applicant"
            ],
            "expiry_place": "Seoul, Republic of Korea",
        }
    )
    findings = evaluate_trade_document(lc, _lc_payment(governing_rules=["Local law only"]))
    ids = {finding.clause_finding_id for finding in findings}

    assert any("LC-BUYER-CONTROLLED-DOCUMENT" in item for item in ids)
    assert any("LC-GOVERNING-RULES-UNRESOLVED" in item for item in ids)


def test_lc_with_ucp_600_does_not_trigger_governing_rule_finding():
    findings = evaluate_trade_document(_lc(), _lc_payment(["ICC UCP 600"] ))

    assert not any(
        "LC-GOVERNING-RULES-UNRESOLVED" in item.clause_finding_id
        for item in findings
    )


def test_payment_structure_must_match_document_and_transaction():
    payment = _contract_payment().model_copy(
        update={"payment_structure_id": "PAY-OTHER"}
    )
    with pytest.raises(ValueError, match="does not match"):
        reviewed_terms_from_document(_contract(), payment)


def test_document_risk_signals_reference_clause_and_evidence_ids():
    contract = _contract(named_place=None)
    findings = evaluate_trade_document(contract, _contract_payment())
    signals = build_document_risk_signals(contract, findings)

    assert signals
    assert all(signal.evidence_ids == [contract.evidence_id] for signal in signals)
    assert all(signal.clause_finding_ids for signal in signals)
    assert all(signal.category == "contract_document" for signal in signals)
    assert all(signal.authority_type == "screening_flag" for signal in signals)
