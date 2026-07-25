# National Tax Service API integration

## Scope

The National Tax Service business-registration API is used only for Korean
counterparty identity and operating-status checks.

Supported use cases:

- normalize and validate Korean business registration numbers;
- query continuing, suspended, or closed business status;
- retrieve tax-type and closure-date fields returned by the official API;
- optionally compare authorized registration details for authenticity;
- process up to 100 registrations per provider request;
- preserve retrieval timestamp, provider name, source, response checksum, and
  explicit limitations.

Out of scope:

- official credit ratings or probability of default;
- financial statements or tax-return data;
- customs or bilateral trade statistics;
- AML, sanctions, legal, lending, approval, or product-suitability decisions.

## Configuration

Set one of the following in the local `.env` file:

```text
NTS_BUSINESS_API_KEY=<local secret>
```

The adapter can also use `DATA_GO_KR_SERVICE_KEY` as a fallback. Never commit
actual credentials.

## Proposed workflow

```text
Uploaded domestic counterparty
  -> normalize business number
  -> NTS status check
  -> explicit status/provenance card
  -> sanctions/name review through a separate provider
  -> country/trade/financial-health analysis
  -> human-reviewed consultation candidate
```

A continuing-business result is one input only. It must never be interpreted as
proof of creditworthiness, payment ability, legal eligibility, or transaction
safety.

## Trade-statistics distinction

The National Tax Service API does not replace Korea Customs Service data. Trade
concentration and HS-code analysis still require the separate Customs country-
and item-trade APIs.
