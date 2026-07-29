# Trade-Finance Product Consultation Matching

## Purpose

This layer maps explicit customer needs and reviewed transaction context to public K-SURE and KB product information.

The output is a `ProductCandidate`, not a recommendation, eligibility decision, approval prediction, quotation, credit decision, insurance acceptance, guarantee issuance, or suitability determination.

## Governed product registry

The reviewed snapshot is stored at:

```text
data/reference/trade_finance_product_registry_v1.json
```

The first registry contains:

- K-SURE overseas-company credit investigation;
- K-SURE short-term export insurance after shipment;
- K-SURE export-credit guarantee before shipment;
- K-SURE direct export-credit guarantee before shipment;
- K-SURE export-credit guarantee after shipment;
- K-SURE export-credit guarantee for receivables purchase;
- K-SURE foreign-exchange fluctuation insurance;
- K-SURE global-supply-chain import insurance;
- K-SURE importer advance-payment insurance;
- KB export-enterprise preferential loan.

Each record retains public-purpose conditions, unresolved institutional conditions, required documents, next action, and official source IDs.

## Explicit need profile

`TradeFinanceNeedProfile` requires the user or an upstream reviewed workflow to declare:

- transaction ID and direction;
- transaction stage;
- financing or risk-management needs;
- company size;
- payment tenor when relevant;
- preferred bank when relevant;
- industry context for sector-specific products;
- documents already available.

The matcher does not infer hidden needs from an LLM narrative.

## Status model

### `consultation_candidate`

The declared need, direction, stage, and available public conditions are consistent enough to prepare a consultation. Institution-specific conditions remain unresolved.

### `insufficient_information`

A public condition cannot be checked because a material input is absent, such as company size, payment tenor, industry classification, or required bank-channel selection.

### `not_applicable`

A declared fact falls outside a public condition, such as payment tenor above the public maximum or an industry outside a restricted target group.

### `blocked`

An explicit channel conflict prevents the particular candidate from being presented as usable. For example, the K-SURE direct pre-shipment guarantee currently lists Shinhan Bank, Hana Bank, and Toss Bank; a profile requiring KB Kookmin Bank is marked blocked for that specific direct product. The general K-SURE pre-shipment guarantee and KB loan consultation candidates remain separate.

## Matching controls

The engine:

- returns only products whose need codes intersect the declared needs;
- does not mix import products into an export case;
- checks transaction stage and direction;
- checks public maximum tenor without inventing a tolerance;
- checks company-size and sector scope;
- normalizes only governed bank-name aliases;
- preserves unknown eligibility conditions;
- generates a separate `ConsultationRequirement` for usable or incomplete candidates;
- retains official source IDs and a registry content hash;
- replaces stale registry-derived candidates on reassessment;
- preserves product records created by other governed sources.

## KB product boundary

The public KB enterprise-loan disclosure confirms that `KB 수출기업 우대대출` is listed. The registry does not claim public knowledge of the current detailed target definition, credit standard, limit, pricing, collateral, guarantee linkage, or branch-level availability.

The output therefore instructs the user to prepare the export contract, financial statements, funding purpose, requested amount, repayment source, and existing debt information for a KB corporate-banking consultation.

## Validation

```powershell
py -3.13 -m pytest -q tests/test_product_matching.py
py -3.13 -m pytest -q
py -3.13 -m compileall -q app.py copilot_app.py src tests scripts
py -3.13 -c "import app; import copilot_app; import src"
py -3.13 scripts/product_matching_smoke_test.py
```

The smoke test represents a Korean SME exporting to a new buyer on 90-day open-account terms, requiring buyer investigation, non-payment protection, pre-shipment working capital, and FX cash-flow certainty while preferring KB Kookmin Bank.

Expected consultation candidates include buyer credit investigation, short-term export insurance, the general pre-shipment guarantee, FX insurance, and the KB export-enterprise loan. The K-SURE direct pre-shipment product is shown as blocked for the declared KB-only bank preference rather than incorrectly presented as a KB-linked product.

## Next integration unit

The next unit should derive a reviewed `TradeFinanceNeedProfile` from the unified case using explicit user declarations and grounded risk signals. It should then rank actions by dependency:

1. complete buyer identification and credit investigation;
2. correct contract and documentary conflicts;
3. confirm insurance or guarantee availability;
4. confirm bank funding structure;
5. hedge only the remaining verified FX exposure.

The ranking must not convert consultation candidates into approval claims.
