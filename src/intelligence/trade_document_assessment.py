"""Attach deterministic trade-document screening results to the unified case."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ..copilot_case import UnifiedCopilotCase
from ..trade_finance_domain import ContractClauseFinding, TradeRiskSignal
from .trade_document_rules import build_document_risk_signals, evaluate_trade_document


class TradeDocumentScreeningOutcome(BaseModel):
    case_before_hash: str
    case_after_hash: str
    evaluated_document_ids: list[str] = Field(default_factory=list)
    clause_finding_ids: list[str] = Field(default_factory=list)
    risk_signal_ids: list[str] = Field(default_factory=list)


def apply_trade_document_screening(
    case: UnifiedCopilotCase,
    *,
    registry_path: str | Path | None = None,
) -> tuple[UnifiedCopilotCase, TradeDocumentScreeningOutcome]:
    """Evaluate approved reviewed documents and attach grounded results immutably."""

    approved_evidence_ids = {
        item.evidence_id for item in case.evidence if item.status == "approved"
    }
    payment_by_id = {
        item.payment_structure_id: item for item in case.trade_finance.payment_structures
    }

    generated_findings: list[ContractClauseFinding] = []
    generated_signals: list[TradeRiskSignal] = []
    evaluated_document_ids: list[str] = []

    for document in case.trade_finance.trade_documents:
        if document.document_type not in {"contract", "purchase_order", "letter_of_credit"}:
            continue
        if document.evidence_id not in approved_evidence_ids:
            raise ValueError(
                f"Trade document {document.document_id} must reference approved case evidence"
            )
        payment = None
        if document.payment_structure_id:
            payment = payment_by_id.get(document.payment_structure_id)
            if payment is None:
                raise ValueError(
                    f"Trade document {document.document_id} references a missing payment structure"
                )
        findings = evaluate_trade_document(
            document,
            payment,
            registry_path=registry_path,
        )
        signals = build_document_risk_signals(
            document,
            findings,
            registry_path=registry_path,
        )
        evaluated_document_ids.append(document.document_id)
        generated_findings.extend(findings)
        generated_signals.extend(signals)

    existing_findings = {
        item.clause_finding_id: item for item in case.trade_finance.clause_findings
    }
    existing_findings.update(
        {item.clause_finding_id: item for item in generated_findings}
    )
    existing_signals = {item.signal_id: item for item in case.trade_finance.risk_signals}
    existing_signals.update({item.signal_id: item for item in generated_signals})

    updated_domain = case.trade_finance.model_copy(
        update={
            "clause_findings": list(existing_findings.values()),
            "risk_signals": list(existing_signals.values()),
        }
    )
    updated_case = case.model_copy(update={"trade_finance": updated_domain})
    outcome = TradeDocumentScreeningOutcome(
        case_before_hash=case.case_hash,
        case_after_hash=updated_case.case_hash,
        evaluated_document_ids=evaluated_document_ids,
        clause_finding_ids=[item.clause_finding_id for item in generated_findings],
        risk_signal_ids=[item.signal_id for item in generated_signals],
    )
    return updated_case, outcome
