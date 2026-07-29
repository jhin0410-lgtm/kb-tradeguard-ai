# Cross-Document Reconciliation

## Purpose

This layer reconciles human-reviewed fields across documents linked to the same trade transaction. It addresses a different problem from single-document clause screening:

- clause screening asks whether one reviewed document contains risky or incomplete terms;
- reconciliation asks whether multiple reviewed documents describe the same transaction consistently.

A mismatch is a review flag. It is not proof of fraud, legal invalidity, documentary non-compliance, or bank refusal.

## Supported document pairs

The first governed registry compares:

- contract versus commercial invoice;
- contract versus letter of credit;
- commercial invoice versus letter of credit.

The initial comparison fields are:

- currency;
- amount;
- Incoterms rule, edition, and named place;
- seller versus invoice seller or L/C beneficiary;
- buyer versus invoice buyer or L/C applicant;
- contract shipment date versus the L/C latest shipment date.

Documents are compared only when their `linked_transaction_ids` overlap.

## Rule registry

Rules are stored at:

```text
data/reference/trade_document_reconciliation_rules_v1.json
```

Each rule records:

- the left and right document types;
- the reviewed field path on each document;
- exact, normalized-text, amount-tolerance, or date-order comparison;
- severity and failure path;
- proposed resolution;
- specialist-review route;
- the authority boundary.

## No silent assumptions

The default amount tolerance is zero.

A non-zero tolerance must be supplied through `ReconciliationPolicy` with:

- the exact rule ID;
- the reviewed tolerance percentage;
- the documentary or contractual basis;
- whether the reference amount is the left value, right value, or larger value.

Party-name and named-place aliases are also explicit case inputs. The engine does not silently strip legal-entity suffixes or assume that similar names represent the same party.

Missing values are marked `skipped`; they are not converted into mismatches.

## Amendments and superseded documents

A document can be excluded only when both are supplied:

- its document ID;
- a reason describing the amendment or supersession basis.

This prevents an older invoice, contract, or credit from being silently ignored.

## Outputs

`reconcile_trade_documents` produces:

- `DocumentComparisonResult` for every applicable pair and rule;
- `ContractClauseFinding` for each actual mismatch;
- `TradeRiskSignal` grounded in both document and evidence IDs.

Comparison states are:

```text
match
within_tolerance
mismatch
skipped
```

`apply_document_reconciliation` verifies approved case evidence, attaches current mismatch findings and signals to `UnifiedCopilotCase`, and removes stale findings from prior reconciliation runs when a reviewed inconsistency is corrected.

The single-document screening layer was also corrected so that resolved contract or L/C findings are removed on reassessment instead of remaining in the case indefinitely.

## Validation

```powershell
py -3.13 -m pytest -q tests/test_document_reconciliation.py tests/test_trade_document_assessment.py
py -3.13 -m pytest -q
py -3.13 -m compileall -q app.py copilot_app.py src tests scripts
py -3.13 -c "import app; import copilot_app; import src"
py -3.13 scripts/document_reconciliation_smoke_test.py
```

## Next delivery unit

The next unit should connect transaction, country, buyer, company, and document facts into governed risk prioritization. It should rank causal risk paths without inventing a probability of default or an opaque composite score.

The first reference case should answer:

1. Is buyer-payment risk more material than foreign-exchange risk?
2. Does the transaction exceed the company's liquidity absorption capacity?
3. Which contract or L/C issue can directly block collection?
4. Which country or compliance fact changes the required due-diligence route?
5. Which mitigation action must happen first?
