# Transaction Decision Brief

## Purpose

This unit combines the separate trade-finance evidence layers into one transaction-specific pre-screening brief.

It synthesizes:

- transaction-linked `TradeRiskSignal` records;
- selected counterparty due-diligence status;
- selected country facts;
- related compliance screenings;
- transaction financial-capacity calculations;
- explicitly selected product candidates and consultation requirements;
- minimum evidence gaps;
- a dependency-based action plan.

It does not:

- approve or reject the transaction;
- clear sanctions, AML, export-control, or restricted-party obligations;
- provide legal advice or certify contract and L/C compliance;
- determine insurance, guarantee, loan, pricing, limit, or suitability outcomes;
- create a composite or opaque risk score.

## Explicit request boundary

`TransactionDecisionBriefRequest` identifies:

- the approved transaction;
- the selected counterparty;
- the selected transaction country;
- product-candidate IDs to include;
- consultation-requirement IDs to include;
- the maximum number of displayed concerns.

Product records are selected explicitly because the current `ProductCandidate` model is a consultation object and does not itself contain a transaction ID. The brief rejects unknown IDs rather than silently mixing candidates from another transaction.

The selected country must match the selected counterparty country.

## Minimum evidence coverage

The brief checks for:

- counterparty identity and registration information;
- country-context facts;
- country or counterparty compliance screening;
- reviewed payment structure;
- reviewed core trade document;
- transaction financial-capacity calculation.

Missing evidence is not converted into a low-risk result. It is recorded in `missing_information` and can result in `additional_information_required`.

## Deterministic concern ordering

Rules are stored at:

```text
data/reference/transaction_decision_brief_rules_v1.json
```

Concerns are ordered without a score:

1. severity order;
2. category order;
3. deterministic concern ID.

The default category order starts with compliance, counterparty, payment instrument, contract/document, liquidity, company capacity, and concentration.

The display limit affects only the number of concerns shown. It does not change the disposition calculation, which evaluates all related concerns.

## Pre-screening dispositions

The brief uses deliberately narrow labels:

- `specialist_clearance_required`;
- `conditions_required_before_commitment`;
- `additional_information_required`;
- `review_required`;
- `no_material_screening_flags`.

None of these is an approval or rejection.

Precedence is:

1. critical concern;
2. high-severity concern;
3. incomplete minimum coverage;
4. medium or low concern;
5. no material screening flag in the attached reviewed evidence.

A potential sanctions or restricted-party match is treated as critical for specialist escalation. A FATF increased-monitoring country fact is treated as review context, not a transaction prohibition or buyer rating.

## Action-plan dependencies

The brief creates typed `ActionPlanItem` records for applicable workstreams:

- compliance review;
- counterparty identification and credit investigation;
- missing information collection;
- contract and L/C correction;
- financial-capacity and funding-structure review;
- country and K-SURE country-policy refresh;
- selected KB, K-SURE, trade-finance, foreign-exchange, legal, or logistics consultation routes;
- final reassessment.

Actions are ordered by governed priorities rather than model-generated prose ranking.

Consultation actions depend on the immediate evidence-remediation actions and, where present, document and capacity review. Final reassessment depends on all preceding actions.

## Case integration

`apply_transaction_decision_brief`:

- builds the current brief;
- preserves the original case;
- replaces prior brief-derived action items for the same transaction;
- preserves action plans from other transactions or sources;
- attaches the current action plan to `TradeFinanceDomainState.action_plan`;
- returns the brief and a hash-aware outcome.

Identical case evidence and request inputs produce identical brief content and case state.

## Validation

```powershell
py -3.13 -m pytest -q tests/test_transaction_decision_brief.py
py -3.13 -m pytest -q
py -3.13 -m compileall -q app.py copilot_app.py src tests scripts
py -3.13 -c "import app; import copilot_app; import src"
py -3.13 scripts/transaction_decision_brief_smoke_test.py
```

## Next delivery unit

The next unit should turn the typed brief into a user-facing transaction diagnosis view without weakening the evidence boundaries.

The first UI should show:

- pre-screening disposition and authority limitation;
- top concerns with exact source IDs;
- transaction-capacity materiality;
- contract and L/C correction requirements;
- consultation candidates separated from eligibility decisions;
- missing information;
- dependency-ordered actions.

The view should hide internal routing and hashes by default while keeping them available in an audit panel.
