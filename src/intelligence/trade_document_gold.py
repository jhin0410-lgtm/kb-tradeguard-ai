"""Governed loader and mutation generator for trade-document gold cases.

The dataset contains synthetic, human-reviewed field fixtures.  It validates the
project-authored deterministic screening rules; it is not a legal opinion, an ICC
rulebook reproduction, or a bank documentary-compliance decision.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterator

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..trade_finance_domain import PaymentStructure, TradeDocumentProfile


class TradeDocumentGoldCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: str
    description: str
    tags: list[str] = Field(default_factory=list)
    document: TradeDocumentProfile
    payment_structure: PaymentStructure
    expected_rule_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def links_and_expectations_are_governed(self):
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("Gold-case tags must be unique")
        if len(self.expected_rule_ids) != len(set(self.expected_rule_ids)):
            raise ValueError("Gold-case expected Rule IDs must be unique")
        if self.document.payment_structure_id != self.payment_structure.payment_structure_id:
            raise ValueError("Gold-case document and payment IDs must match")
        if self.payment_structure.transaction_id not in self.document.linked_transaction_ids:
            raise ValueError("Gold-case payment transaction must be linked to the document")
        return self


class TradeDocumentGoldMutation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mutation_id: str
    base_case_id: str
    mutation_kind: str
    document: TradeDocumentProfile
    payment_structure: PaymentStructure
    expected_rule_ids: list[str]


def default_trade_document_gold_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "gold"
        / "trade_document_gold_v1.json"
    )


def load_trade_document_gold_dataset(path: str | Path | None = None) -> dict[str, Any]:
    dataset_path = Path(path) if path is not None else default_trade_document_gold_path()
    try:
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load trade-document gold dataset: {dataset_path}") from exc

    required = {
        "dataset_name",
        "dataset_version",
        "created_date",
        "source_mode",
        "authority_boundary",
        "base_templates",
        "cases",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError("Gold dataset is missing keys: " + ", ".join(missing))
    if payload["source_mode"] != "synthetic_gold":
        raise ValueError("Trade-document gold dataset must remain synthetic_gold")
    if not isinstance(payload["cases"], list) or not payload["cases"]:
        raise ValueError("Trade-document gold dataset must contain cases")
    return payload


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _source(case_id: str, record_type: str, created_date: str) -> dict[str, Any]:
    return {
        "source_id": f"SRC-GOLD-{record_type.upper()}-{case_id}",
        "source_name": f"Synthetic gold {record_type} fixture",
        "source_tier": "user_provided",
        "source_kind": "user_document",
        "source_locator": f"gold://{case_id}/{record_type}",
        "as_of_date": created_date,
        "effective_date_verified": True,
    }


def _build_case(dataset: dict[str, Any], spec: dict[str, Any]) -> TradeDocumentGoldCase:
    kind = spec.get("document_kind")
    templates = dataset["base_templates"]
    if kind not in templates:
        raise ValueError(f"Unknown gold-case document_kind: {kind}")

    case_id = str(spec["case_id"])
    transaction_id = f"TX-{case_id}"
    payment_id = f"PAY-{case_id}"
    document_id = f"DOC-{case_id}"
    evidence_id = f"EVID-{case_id}"
    template = templates[kind]

    document_payload = _deep_merge(
        template["document"],
        spec.get("document_overrides", {}),
    )
    reviewed = _deep_merge(
        document_payload.get("reviewed_fields", {}),
        spec.get("reviewed_field_overrides", {}),
    )
    document_payload.update(
        {
            "document_id": document_id,
            "evidence_id": evidence_id,
            "payment_structure_id": payment_id,
            "linked_transaction_ids": [transaction_id],
            "reviewed_fields": reviewed,
            "source": _source(case_id, "document", dataset["created_date"]),
        }
    )

    payment_payload = _deep_merge(
        template["payment_structure"],
        spec.get("payment_overrides", {}),
    )
    payment_payload.update(
        {
            "payment_structure_id": payment_id,
            "transaction_id": transaction_id,
            "source": _source(case_id, "payment", dataset["created_date"]),
        }
    )

    return TradeDocumentGoldCase(
        case_id=case_id,
        description=spec["description"],
        tags=spec.get("tags", []),
        document=TradeDocumentProfile.model_validate(document_payload),
        payment_structure=PaymentStructure.model_validate(payment_payload),
        expected_rule_ids=spec.get("expected_rule_ids", []),
    )


def list_trade_document_gold_cases(
    path: str | Path | None = None,
) -> list[TradeDocumentGoldCase]:
    dataset = load_trade_document_gold_dataset(path)
    cases = [_build_case(dataset, item) for item in dataset["cases"]]
    identifiers = [item.case_id for item in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Trade-document gold case IDs must be unique")
    return cases


def iter_semantic_preserving_gold_mutations(
    cases: list[TradeDocumentGoldCase] | None = None,
) -> Iterator[TradeDocumentGoldMutation]:
    """Yield five rule-invariant mutations per gold case.

    These mutations alter identifiers, source metadata, record status, transaction
    linkage, or an irrelevant reviewed field while preserving the screened semantics.
    The expected Rule-ID set must therefore remain exactly unchanged.
    """

    selected = cases if cases is not None else list_trade_document_gold_cases()
    for case in selected:
        base_document = case.document
        base_payment = case.payment_structure

        document = base_document.model_copy(
            update={
                "source": base_document.source.model_copy(
                    update={"source_name": base_document.source.source_name + " · metadata mutation"}
                )
            }
        )
        payment = base_payment.model_copy(
            update={
                "source": base_payment.source.model_copy(
                    update={"source_name": base_payment.source.source_name + " · metadata mutation"}
                )
            }
        )
        yield TradeDocumentGoldMutation(
            mutation_id=f"{case.case_id}::source_metadata",
            base_case_id=case.case_id,
            mutation_kind="source_metadata",
            document=document,
            payment_structure=payment,
            expected_rule_ids=case.expected_rule_ids,
        )

        new_payment_id = f"{base_payment.payment_structure_id}-RELABEL"
        yield TradeDocumentGoldMutation(
            mutation_id=f"{case.case_id}::identifier_relabel",
            base_case_id=case.case_id,
            mutation_kind="identifier_relabel",
            document=base_document.model_copy(
                update={
                    "document_id": f"{base_document.document_id}-RELABEL",
                    "evidence_id": f"{base_document.evidence_id}-RELABEL",
                    "payment_structure_id": new_payment_id,
                }
            ),
            payment_structure=base_payment.model_copy(
                update={"payment_structure_id": new_payment_id}
            ),
            expected_rule_ids=case.expected_rule_ids,
        )

        new_transaction_id = f"{base_payment.transaction_id}-RELINK"
        yield TradeDocumentGoldMutation(
            mutation_id=f"{case.case_id}::transaction_relink",
            base_case_id=case.case_id,
            mutation_kind="transaction_relink",
            document=base_document.model_copy(
                update={"linked_transaction_ids": [new_transaction_id]}
            ),
            payment_structure=base_payment.model_copy(
                update={"transaction_id": new_transaction_id}
            ),
            expected_rule_ids=case.expected_rule_ids,
        )

        yield TradeDocumentGoldMutation(
            mutation_id=f"{case.case_id}::partial_status",
            base_case_id=case.case_id,
            mutation_kind="partial_status",
            document=base_document.model_copy(update={"record_status": "partial"}),
            payment_structure=base_payment.model_copy(update={"record_status": "partial"}),
            expected_rule_ids=case.expected_rule_ids,
        )

        reviewed = dict(base_document.reviewed_fields)
        reviewed["gold_mutation_note"] = "Irrelevant reviewed metadata must not create a Rule ID."
        yield TradeDocumentGoldMutation(
            mutation_id=f"{case.case_id}::irrelevant_reviewed_field",
            base_case_id=case.case_id,
            mutation_kind="irrelevant_reviewed_field",
            document=base_document.model_copy(update={"reviewed_fields": reviewed}),
            payment_structure=base_payment,
            expected_rule_ids=case.expected_rule_ids,
        )
