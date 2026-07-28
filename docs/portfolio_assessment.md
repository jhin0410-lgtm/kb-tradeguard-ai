# Multi-transaction portfolio assessment

KB TradeGuard AI keeps the governed single-transaction pipeline as the document and transaction decision engine, then adds a deterministic single-company portfolio layer above it.

## Scope

- validates unique, positive approved transactions
- aggregates export receivables, import payables and foreign cash by currency
- calculates same-currency natural offsets and net FX exposure
- normalizes official reference-rate units such as `JPY(100)`
- produces probability-weighted monthly liquidity buckets
- provides disclosed uniform FX sensitivities
- creates transaction-linked product consultation profiles

The company workspace is a public synthetic comparison surface. It is not authentication, tenant isolation, an entitlement system or production customer-data storage.
