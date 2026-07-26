# Contract and Documentary-Credit Screening

## Scope

This delivery unit adds deterministic pre-screening for reviewed contract, purchase-order, and letter-of-credit fields.

It does not:

- interpret an unreviewed full document autonomously;
- provide legal advice or determine enforceability;
- certify a documentary presentation as compliant;
- bind an issuing, advising, confirming, nominated, or negotiating bank;
- reproduce the text of ICC rulebooks;
- determine insurance eligibility or claim acceptance.

## Governed rule registry

Rules are stored at:

```text
data/reference/trade_document_rules_v1.json
```

Every rule records:

- rule ID and document kind;
- deterministic operator and reviewed input field;
- severity and issue type;
- failure path;
- suggested clarification or revision;
- specialist-review route;
- official reference identifiers where applicable;
- an explicit authority boundary.

The registry cites official ICC public materials but contains project-authored screening logic rather than copied ICC rule text.

## Contract checks

The first registry checks:

- missing Incoterms rule;
- missing Incoterms edition year;
- missing named place or port;
- payment dependent on buyer acceptance without a reviewed acceptance period;
- missing governing law;
- missing dispute-resolution route;
- broad buyer unilateral set-off;
- buyer unilateral amendment rights.

A finding states the failure path and proposed clarification. It does not state that a clause is legally invalid.

## Letter-of-credit checks

The first registry checks:

- missing issuing bank;
- missing credit expiry date;
- missing latest shipment date;
- expiry before latest shipment date;
- missing or zero document-presentation period;
- unresolved governing rule set;
- applicant- or buyer-controlled required documents;
- missing place of expiry or presentation.

The applicable-rules check does not presume that every credit is automatically governed by UCP 600. It flags the governing basis as unresolved when the reviewed terms do not identify UCP 600.

## Grounding and case integration

`evaluate_trade_document` converts one reviewed document into `ContractClauseFinding` records. Each finding references:

- the reviewed document ID;
- approved case evidence ID;
- deterministic rule ID;
- rule-registry hash;
- limitations and specialist-review requirements.

`build_document_risk_signals` converts findings into grounded `TradeRiskSignal` records.

`apply_trade_document_screening` evaluates supported documents in `UnifiedCopilotCase.trade_finance`, verifies that each document references approved case evidence and an existing payment structure, and immutably attaches findings and risk signals to the case snapshot.

Repeated evaluation of the same reviewed snapshot is idempotent by deterministic finding and signal IDs.

## Validation

```powershell
py -3.13 -m pytest -q tests/test_trade_document_rules.py tests/test_trade_document_assessment.py
py -3.13 -m pytest -q
py -3.13 -m compileall -q app.py copilot_app.py src tests scripts
py -3.13 -c "import app; import copilot_app; import src"
```

## Next document-intelligence unit

The next unit should reconcile facts across multiple reviewed documents rather than add more isolated rules. Initial deterministic comparisons should cover:

- legal party names;
- currency and amount;
- Incoterms rule, edition, and named place;
- shipment and expiry dates;
- contract payment terms versus L/C terms;
- invoice, packing-list, and transport-document references.

Tolerance, optionality, and amendment terms must be represented explicitly before an amount or date difference is called a discrepancy.
