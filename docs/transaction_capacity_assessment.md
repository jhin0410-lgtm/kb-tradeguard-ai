# Transaction-to-Financial-Capacity Assessment

## Purpose

This unit links one approved trade transaction to one reviewed financial-statement snapshot and measures whether the transaction is large relative to the company's disclosed financial buffers.

It does not:

- estimate default probability or expected loss;
- assign an internal or external credit rating;
- predict bank approval, insurance acceptance, guarantee issuance, pricing, or limits;
- infer unreported facilities, pledged cash, restricted deposits, other cash flows, or collateral;
- treat gross transaction value as a loss amount.

## OpenDART normalization

`build_financial_statement_snapshot` converts a governed `OpenDARTProvider.get_financial_statements` payload into `FinancialStatementSnapshot`.

The normalizer uses exact account IDs first and exact normalized Korean account names second. It currently maps:

- cash and cash equivalents;
- short-term financial assets;
- trade receivables;
- inventories;
- current assets and current liabilities;
- short-term borrowings and current maturities;
- explicitly reported total borrowings;
- total liabilities, total assets, and equity;
- revenue, operating profit, operating cash flow, and interest expense.

Missing values remain missing. The normalizer does not aggregate issuer-specific subaccounts or impute a total.

Statement dates may be supplied explicitly. When omitted, dates are inferred from the OpenDART business year and report code and the limitation is recorded, because non-calendar fiscal periods require confirmation.

## Reviewed assessment inputs

`TransactionCapacityRequest` requires:

- approved transaction ID;
- financial-statement snapshot ID;
- assessment ID.

Optional reviewed inputs are:

- payment-structure ID;
- explicit effective protection percentage;
- explicit pre-shipment or transaction-preparation funding need in KRW;
- an explicit FX-rate override and its source.

An FX override without a source is rejected. Insurance, guarantee, advance-payment, or other protection is never inferred.

## Deterministic metrics

The assessment calculates available metrics including:

- gross transaction value in KRW;
- identified liquid assets;
- deferred trade amount;
- residual unprotected exposure after the explicit protection percentage;
- explicit funding need;
- simple post-funding liquidity;
- transaction value relative to cash, identified liquid assets, current assets, equity, and annual revenue;
- deferred trade amount relative to cash;
- residual unprotected exposure relative to cash and equity;
- funding need relative to identified liquid assets.

Revenue concentration is calculated only from an annual snapshot. A quarterly or semiannual revenue amount is not silently annualized.

## Governed review triggers

Rules are stored at:

```text
data/reference/transaction_capacity_rules_v1.json
```

The first rules use only structural 100% comparisons:

- explicit funding need exceeds identified liquid assets;
- residual unprotected exposure exceeds cash;
- residual unprotected exposure exceeds equity;
- gross transaction value exceeds current assets;
- gross transaction value exceeds annual revenue.

These are project-authored review triggers, not bank underwriting standards. A triggered ratio creates a grounded `TradeRiskSignal` referencing the deterministic calculation ID and records unresolved facts that still require review.

## Case integration

`apply_transaction_capacity_assessment`:

- verifies the approved transaction;
- verifies the selected financial statement and company linkage;
- verifies the selected payment structure;
- stores the deterministic `CalculationResult` in `UnifiedCopilotCase.calculations`;
- replaces stale transaction-capacity signals for the same transaction;
- preserves older calculations as audit records;
- preserves the original case and returns a new case snapshot.

Identical reassessment inputs reuse the existing calculation object so repeated execution is idempotent despite calculation timestamps.

## Validation

```powershell
py -3.13 -m pytest -q tests/test_product_matching.py tests/test_product_matching_case_contract.py
py -3.13 -m pytest -q tests/test_financial_snapshot.py tests/test_transaction_capacity.py
py -3.13 -m pytest -q
py -3.13 -m compileall -q app.py copilot_app.py src tests scripts
py -3.13 -c "import app; import copilot_app; import src"
py -3.13 scripts/transaction_capacity_smoke_test.py
```

## Next integration unit

The next unit should combine the currently separate evidence layers into one transaction decision brief:

- counterparty and country facts;
- contract and L/C findings;
- cross-document discrepancies;
- transaction-capacity calculations;
- product consultation candidates;
- missing information and action sequence.

The brief should rank actions using explicit dependency rules, not an opaque AI score.
