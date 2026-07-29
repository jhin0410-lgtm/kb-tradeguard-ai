# Trade-document Gold Dataset

## Purpose

`data/gold/trade_document_gold_v1.json` validates the deterministic contract and documentary-credit screening registry. The dataset is intentionally `synthetic_gold`: it contains reviewed structured fields and project-authored expected Rule IDs, not real customer conclusions, legal opinions, ICC rulebook text, or bank documentary-compliance decisions.

## Version 1.1 coverage

- 30 explicit Gold cases
- 10 contract cases
- 20 letter-of-credit cases
- Exact expected Rule-ID assertion for every case
- Coverage of every Rule ID in `trade-document-rules/1.1`
- Clean negative controls for contract, Sight L/C, Usance L/C, deferred-payment L/C, acceptance L/C, and negotiation L/C
- Combined toxic-contract and complex L/C attack cases
- 150 deterministic semantic-preserving mutations

The explicit cases include:

- Incoterms rule, edition, and named-place gaps
- Buyer-controlled acceptance trigger
- Missing governing law and dispute route
- Unilateral set-off and amendment
- Missing issuing bank, expiry, shipment date, presentation period, expiry place, and availability type
- Expiry before latest shipment
- Zero-day presentation period
- Unresolved governing-rule reference
- Buyer-controlled L/C documents
- Usance/deferred tenor and start-event gaps
- Missing accepting party and draft tenor text

## Compact governed format

The JSON stores two complete base templates—contract and letter of credit—and 30 explicit semantic case specifications. `src/intelligence/trade_document_gold.py` performs a deterministic deep merge, injects unique Document ID, Evidence ID, Payment ID, transaction link, and synthetic source provenance, then validates the result through the production Pydantic domain models.

This format avoids copying the same safe baseline fields 30 times while keeping every risk-inducing override and expected Rule ID reviewable in one file.

## Mutation suite

Five rule-invariant mutations are generated for every Gold case:

1. Source metadata change
2. Document, Evidence, and Payment identifier relabel
3. Consistent transaction relink
4. `verified` to `partial` record-status change
5. Irrelevant reviewed-field injection

These changes must not alter the exact Rule-ID set. The suite therefore checks that rule behavior is determined by governed commercial fields rather than incidental identifiers, provenance labels, status presentation, or unrelated metadata.

The mutation suite is deterministic and contains 150 cases. It complements the 30 explicit trigger and clean-control cases; it does not replace future real, de-identified, or public-document validation.

## Validation

```powershell
py -3.13 -m pytest -q tests/test_trade_document_gold_dataset.py
py -3.13 scripts/trade_document_gold_summary.py
```

Expected summary:

```text
gold_case_count: 30
mutation_case_count: 150
governed_rule_count: 22
covered_rule_count: 22
status: ok
```

## Trust boundary

A passing Gold case means the implementation produced the expected project Rule IDs for the supplied reviewed fields. It does not establish legal enforceability, documentary compliance, bank acceptance, insurance coverage, financing eligibility, or transaction approval.
