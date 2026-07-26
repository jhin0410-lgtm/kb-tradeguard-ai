# Competition Hardening and Optional Live AI

## Delivery decision

KB TradeGuard now separates three product layers:

1. **deterministic authority** — calculations, rules, reconciliation, product-candidate status, and the final transaction brief;
2. **human review** — approval of evidence and append-only confirmation, dismissal, or information-request decisions over findings;
3. **optional live AI** — cited explanation and consultation preparation over the already-completed deterministic result.

Live AI is included as an optional presentation and interaction layer. It is not required for the deterministic pipeline to run and is never the source of a financial calculation, Rule ID, Finding ID, compliance clearance, approval, or product eligibility result.

## Payment-term normalization

`src/intelligence/payment_terms.py` normalizes one human-reviewed wording fragment into:

- payment instrument: advance, O/A, D/P, D/A, L/C, standby L/C, or other;
- availability: sight, usance, deferred payment, acceptance, negotiation, or unknown;
- tenor day count;
- tenor start event such as B/L date, shipment, invoice, presentation, sight, or acceptance;
- draft requirement and reviewed draft-tenor wording;
- accepting party;
- explicit unresolved fields.

The normalizer does not read an entire document autonomously. Its result can be converted into the existing `PaymentStructure` and merged into reviewed L/C fields.

D/A is normalized as an acceptance structure even when the wording also contains a day count. D/P is not automatically converted to sight unless sight wording is explicit.

## Expanded documentary-credit rules

The governed trade-document registry now contains 22 rules. New L/C checks cover:

- missing availability type;
- missing day count for usance, deferred-payment, or acceptance structures;
- missing tenor start event;
- missing accepting party;
- required draft without reviewed tenor wording.

The rules remain project-authored screening triggers. They do not reproduce UCP 600 text or determine documentary compliance.

## Finding review ledger

`FindingReviewDecision` records:

- review ID and Finding ID;
- confirmed, dismissed, or needs-more-information status;
- reviewer role and reviewer identifier;
- timezone-aware review timestamp;
- review note;
- supporting Evidence IDs;
- the previous review explicitly superseded by a later decision.

Review decisions are append-only. The original finding, signal, Rule ID, evidence, and calculation remain in the case for audit. A later review must explicitly supersede the latest decision so that the effective review status is unambiguous.

An empty review ledger is omitted from the canonical case snapshot to preserve compatibility with existing package hashes. Once a review exists, it becomes part of the case hash.

## Gold dataset strategy

`data/gold/trade_document_gold_v1.json` is the first versioned answer dataset. It contains eight synthetic-gold reviewed-field cases covering:

- complete sight L/C;
- incomplete usance L/C;
- complete acceptance L/C;
- missing accepting party;
- missing availability;
- zero presentation period and applicant-controlled document;
- missing Incoterms named place and unilateral set-off;
- expiry before latest shipment.

Each case includes expected and forbidden Rule IDs. The tests validate identifiers rather than snapshotting full narrative text, which prevents harmless wording changes from invalidating the dataset.

The target dataset structure is:

```text
4–6 showcase scenarios for the Streamlit demo
30–50 curated gold cases for regression testing
100+ mutation cases generated from the curated cases
```

Official data such as OpenDART, World Bank, FATF, ECOS, and institution product disclosures should remain real and hashed. Contract, invoice, and L/C cases should be synthetic-gold or de-identified because publicly available linked transaction-document sets rarely include reliable answer labels.

## Evidence anchors in reports

The Markdown renderer now uses `[REF:<id>]` anchors for:

- concern source IDs;
- clause Finding IDs;
- supporting Evidence IDs;
- product candidate and consultation IDs;
- Action IDs and supporting RiskSignal IDs;
- stage-generated record IDs;
- country, compliance, and calculation IDs.

The report also includes a Finding-review table. These anchors are intended to become clickable evidence drawers in the Streamlit app.

## Optional live AI contract

`src/intelligence/live_ai_contract.py` defines a provider-neutral boundary.

A live-AI request contains only:

- the completed output Case hash;
- Brief ID;
- an interaction mode;
- the user's question;
- a bounded set of allowed reference IDs;
- deterministic context copied from the completed brief and stage traces;
- an explicit authority boundary.

Accepted model output must:

- use `decision_status=explanation_only`;
- include inline `[REF:<id>]` citations;
- declare the same citation IDs in structured output;
- cite only IDs included in the grounding packet;
- preserve limitations;
- use a timezone-aware generation timestamp.

The validator rejects unknown, missing, undeclared, or out-of-packet references. No provider API call is implemented in this unit. Provider integration belongs in the Streamlit sprint behind an environment-variable feature flag and must have a deterministic fallback.

## Recommended Streamlit behavior

```text
Live AI OFF (default)
→ deterministic pipeline, report, Action Plan, and downloads work fully

Live AI ON
→ user asks a question about the completed result
→ bounded grounding packet is sent to the configured provider
→ response is validated
→ accepted explanation is displayed with evidence anchors
→ rejected provider output is hidden and a deterministic fallback is shown
```

The UI must never describe live AI as the scoring or decision engine.

## Validation

```powershell
py -3.13 -m pytest -q `
  tests/test_payment_terms.py `
  tests/test_trade_document_rules.py `
  tests/test_trade_document_gold_dataset.py `
  tests/test_finding_review.py `
  tests/test_live_ai_contract.py `
  tests/test_decision_brief_report.py

py -3.13 -m pytest -q
py -3.13 -m compileall -q app.py copilot_app.py src tests scripts
py -3.13 -c "import app; import copilot_app; import src"
```

## Next implementation unit

After this backend hardening passes locally:

1. expand the gold set from 8 to at least 30 curated cases;
2. add deterministic mutation generation;
3. build `assessment_app.py` with showcase selection and JSON upload;
4. add clickable evidence anchors and Finding-review controls;
5. connect one optional live-AI provider behind a feature flag;
6. keep deterministic report and ZIP export available when the provider is unavailable.
