# Korea Customs Service trade-statistics integration

## Why this provider exists

The competition topic requires trade-statistics and country context, not only domestic business-registration checks. The National Tax Service business-registration API remains useful for Korean counterparty identity and operating-status checks, but it does not provide customs statistics.

`src/data_providers/korea_customs_trade.py` therefore adds a separate read-only adapter for the Korea Customs Service `품목별 국가별 수출입실적(GW)` API.

## Official endpoint

- Provider: Korea Customs Service via data.go.kr
- Dataset: `관세청_품목별 국가별 수출입실적(GW)`
- Dataset page: `https://www.data.go.kr/data/15100475/openapi.do`
- API operation: `https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList`
- Format: XML
- Required parameters: service key, start month, end month, two-letter country code
- Optional parameter: HS code with 2, 4, 6, or 10 digits
- Query period: at most one year per request

## Configuration

Set one of these values locally or in the deployment secret store:

```text
KCS_TRADE_API_KEY=<data.go.kr service key>
```

The provider can also use `DATA_GO_KR_SERVICE_KEY` as a fallback. Never commit a real key.

## Returned fields

The adapter normalizes each monthly aggregate row to:

```text
period
country_name_ko
country_code
product_name_ko
hs_code
export_weight_kg
export_value_usd
import_weight_kg
import_value_usd
trade_balance_usd
```

It also preserves the request parameters, retrieval timestamp, official source URL, API URL, response hash, and explicit limitations.

## Trust boundary

These are aggregate customs statistics. They are not company-level declarations and must not be presented as proof that a particular customer exported or imported a stated amount.

- Export values use the official FOB aggregation basis.
- Import values use the official CIF aggregation basis.
- Monthly figures can be revised after declaration corrections or withdrawals.
- Trade concentration is contextual evidence only.
- The provider does not determine buyer risk, credit approval, insurance acceptance, hedge suitability, or product eligibility.

## Intended use in TradeGuard

```text
reviewed transaction country + HS code
  -> official KCS monthly trade snapshot
  -> concentration, growth and balance calculations
  -> country/industry context evidence
  -> deterministic hedge and financing consultation questions
  -> human review
```

The first implementation deliberately stops at sourced retrieval. Concentration thresholds and product-routing rules must be versioned and tested separately before they can affect the Decision Brief.
