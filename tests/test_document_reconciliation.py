from datetime import date
from decimal import Decimal

import pytest

from src.copilot_case import CaseEvidenceItem, CaseIdentity, UnifiedCopilotCase
from src.intelligence.document_reconciliation import (
    ReconciliationPolicy,
    apply_document_reconciliation,
    load_reconciliation_registry,
    reconcile_trade_documents,
)
from src.trade_finance_domain import (
    SourceReference,
    TradeDocumentProfile,
    TradeFinanceDomainState,
)


def _source(source_id):
    return SourceReference(
        source_id=source_id,
        source_name="Reviewed synthetic document",
        source_tier="user_provided",
        source_kind="user_document",
        source_locator=f"fixture://{source_id}",
        as_of_date=date(2026, 7, 26),
        effective_date_verified=True,
    )


def _contract(**updates):
    payload = {
        "document_id": "DOC-CONTRACT",
        "evidence_id": "EVID-CONTRACT",
        "document_type": "contract",
        "currency": "USD",
        "amount": Decimal("100000"),
        "shipment_date": date(2026, 10, 1),
        "incoterms_rule": "FCA",
        "incoterms_year": 2020,
        "named_place": "Busan New Port",
        "linked_transaction_ids": ["EXP-001"],
        "reviewed_fields": {
            "seller_name": "Acme Export Co., Ltd.",
            "buyer_name": "Vietnam Buyer JSC",
        },
        "source": _source("SRC-CONTRACT"),
        "record_status": "verified",
    }
    payload.update(updates)
    return TradeDocumentProfile(**payload)


def _invoice(**updates):
    payload = {
        "document_id": "DOC-INVOICE",
        "evidence_id": "EVID-INVOICE",
        "document_type": "commercial_invoice",
        "currency": "USD",
        "amount": Decimal("100000"),
        "incoterms_rule": "FCA",
        "incoterms_year": 2020,
        "named_place": "Busan New Port",
        "linked_transaction_ids": ["EXP-001"],
        "reviewed_fields": {
            "seller_name": "Acme Export Co., Ltd.",
            "buyer_name": "Vietnam Buyer JSC",
        },
        "source": _source("SRC-INVOICE"),
        "record_status": "verified",
    }
    payload.update(updates)
    return TradeDocumentProfile(**payload)


def _lc(**updates):
    payload = {
        "document_id": "DOC-LC",
        "evidence_id": "EVID-LC",
        "document_type": "letter_of_credit",
        "currency": "USD",
        "amount": Decimal("100000"),
        "expiry_date": date(2026, 11, 15),
        "linked_transaction_ids": ["EXP-001"],
        "reviewed_fields": {
            "beneficiary_name": "Acme Export Co., Ltd.",
            "applicant_name": "Vietnam Buyer JSC",
            "latest_shipment_date": date(2026, 10, 15),
        },
        "source": _source("SRC-LC"),
        "record_status": "verified",
    }
    payload.update(updates)
    return TradeDocumentProfile(**payload)


def _case(documents, evidence_status="approved"):
    evidence = [
        CaseEvidenceItem(
            evidence_id=document.evidence_id,
            evidence_type=document.document_type,
            source_name=f"{document.document_id}.pdf",
            status=evidence_status,
            linked_transaction_ids=list(document.linked_transaction_ids),
        )
        for document in documents
    ]
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-RECONCILIATION",
            analysis_as_of_date=date(2026, 7, 26),
        ),
        evidence=evidence,
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 100000,
                "expected_date": "2026-11-15",
            }
        ],
        trade_finance=TradeFinanceDomainState(trade_documents=documents),
    )


def test_registry_rules_are_unique():
    registry = load_reconciliation_registry()

    assert registry.registry_version == "trade-document-reconciliation/1.0"
    assert len(registry.rules) >= 12
    assert len({rule.rule_id for rule in registry.rules}) == len(registry.rules)
    assert "Amendments" in registry.authority_boundary


def test_consistent_contract_invoice_and_lc_have_no_mismatch_findings():
    result = reconcile_trade_documents([_contract(), _invoice(), _lc()])

    assert result.comparisons
    assert result.findings == []
    assert result.risk_signals == []
    assert {item.status for item in result.comparisons} <= {"match", "skipped"}


def test_currency_and_amount_mismatches_create_separate_grounded_findings():
    invoice = _invoice(currency="EUR", amount=Decimal("95000"))
    result = reconcile_trade_documents([_contract(), invoice])
    by_rule = {item.rule_id: item for item in result.comparisons}

    assert by_rule["CONTRACT-INVOICE-CURRENCY"].status == "mismatch"
    assert by_rule["CONTRACT-INVOICE-AMOUNT"].status == "mismatch"
    assert len(result.findings) == 2
    assert all(item.evidence_ids == ["EVID-CONTRACT", "EVID-INVOICE"] for item in result.findings)
    assert all(item.issue_type == "document_discrepancy_risk" for item in result.findings)
    assert all(item.source.source_kind == "project_rule" for item in result.findings)


def test_nonzero_amount_tolerance_requires_basis_and_reference():
    with pytest.raises(ValueError, match="reviewed basis"):
        ReconciliationPolicy(
            amount_tolerance_percent_by_rule={"CONTRACT-INVOICE-AMOUNT": Decimal("2")}
        )

    with pytest.raises(ValueError, match="reference side"):
        ReconciliationPolicy(
            amount_tolerance_percent_by_rule={"CONTRACT-INVOICE-AMOUNT": Decimal("2")},
            tolerance_basis_by_rule={
                "CONTRACT-INVOICE-AMOUNT": "Signed contract quantity tolerance"
            },
        )


def test_explicit_amount_tolerance_prevents_false_mismatch():
    policy = ReconciliationPolicy(
        amount_tolerance_percent_by_rule={"CONTRACT-INVOICE-AMOUNT": Decimal("2")},
        tolerance_basis_by_rule={
            "CONTRACT-INVOICE-AMOUNT": "Reviewed signed contract tolerance"
        },
        tolerance_reference_by_rule={"CONTRACT-INVOICE-AMOUNT": "left"},
    )
    result = reconcile_trade_documents(
        [_contract(), _invoice(amount=Decimal("102000"))], policy
    )
    comparison = next(
        item for item in result.comparisons if item.rule_id == "CONTRACT-INVOICE-AMOUNT"
    )

    assert comparison.status == "within_tolerance"
    assert comparison.absolute_difference == Decimal("2000")
    assert comparison.allowed_difference == Decimal("2000")
    assert comparison.tolerance_basis == "Reviewed signed contract tolerance"
    assert not any("CONTRACT-INVOICE-AMOUNT" in item.clause_finding_id for item in result.findings)


def test_party_alias_must_be_explicit_to_avoid_name_mismatch():
    invoice = _invoice(
        reviewed_fields={
            "seller_name": "ACME EXPORT",
            "buyer_name": "Vietnam Buyer JSC",
        }
    )
    unaliased = reconcile_trade_documents([_contract(), invoice])
    aliased = reconcile_trade_documents(
        [_contract(), invoice],
        ReconciliationPolicy(
            party_aliases={"Acme Export Co., Ltd.": "ACME EXPORT"}
        ),
    )

    assert any(
        item.rule_id == "CONTRACT-INVOICE-SELLER" and item.status == "mismatch"
        for item in unaliased.comparisons
    )
    assert any(
        item.rule_id == "CONTRACT-INVOICE-SELLER" and item.status == "match"
        for item in aliased.comparisons
    )


def test_missing_reviewed_field_is_skipped_not_called_a_mismatch():
    invoice = _invoice(
        reviewed_fields={"seller_name": None, "buyer_name": "Vietnam Buyer JSC"}
    )
    result = reconcile_trade_documents([_contract(), invoice])
    seller = next(
        item for item in result.comparisons if item.rule_id == "CONTRACT-INVOICE-SELLER"
    )

    assert seller.status == "skipped"
    assert "no mismatch is inferred" in seller.rationale
    assert not any("CONTRACT-INVOICE-SELLER" in item.clause_finding_id for item in result.findings)


def test_contract_shipment_after_lc_deadline_is_critical():
    lc = _lc(
        reviewed_fields={
            "beneficiary_name": "Acme Export Co., Ltd.",
            "applicant_name": "Vietnam Buyer JSC",
            "latest_shipment_date": date(2026, 9, 15),
        }
    )
    result = reconcile_trade_documents([_contract(), lc])
    finding = next(
        item for item in result.findings if "CONTRACT-LC-SHIPMENT-DEADLINE" in item.clause_finding_id
    )

    assert finding.severity == "critical"
    assert "2026-10-01" in finding.clause_excerpt
    assert result.risk_signals[0].category == "payment_instrument"


def test_excluded_superseded_document_requires_reason_and_is_not_compared():
    with pytest.raises(ValueError, match="supersession reason"):
        ReconciliationPolicy(excluded_document_ids=["DOC-INVOICE"])

    policy = ReconciliationPolicy(
        excluded_document_ids=["DOC-INVOICE"],
        exclusion_reasons={"DOC-INVOICE": "Superseded by signed amended invoice DOC-INVOICE-2"},
    )
    result = reconcile_trade_documents([_contract(), _invoice(currency="EUR")], policy)

    assert result.comparisons == []
    assert result.findings == []


def test_case_application_requires_approved_evidence():
    with pytest.raises(ValueError, match="approved case evidence"):
        apply_document_reconciliation(
            _case([_contract(), _invoice()], evidence_status="review_required")
        )


def test_case_application_is_immutable_and_idempotent():
    case = _case([_contract(), _invoice(currency="EUR")])
    before = case.case_hash
    first, first_outcome = apply_document_reconciliation(case)
    second, second_outcome = apply_document_reconciliation(first)

    assert case.trade_finance.clause_findings == []
    assert case.case_hash == before
    assert first_outcome.finding_ids
    assert first.case_hash != before
    assert second.case_hash == first.case_hash
    assert second_outcome.finding_ids == first_outcome.finding_ids
    assert len(second.trade_finance.clause_findings) == len(first.trade_finance.clause_findings)


def test_resolved_mismatch_removes_stale_prior_reconciliation_finding():
    first, _ = apply_document_reconciliation(
        _case([_contract(), _invoice(currency="EUR")])
    )
    fixed_invoice = _invoice(currency="USD")
    fixed_domain = first.trade_finance.model_copy(
        update={"trade_documents": [_contract(), fixed_invoice]}
    )
    fixed_case = first.model_copy(update={"trade_finance": fixed_domain})

    updated, outcome = apply_document_reconciliation(fixed_case)

    assert outcome.finding_ids == []
    assert not any(
        item.source.source_id.startswith("DOCUMENT-RECONCILIATION-")
        for item in updated.trade_finance.clause_findings
    )
    assert not any(
        item.source.source_id.startswith("DOCUMENT-RECONCILIATION-")
        for item in updated.trade_finance.risk_signals
    )
