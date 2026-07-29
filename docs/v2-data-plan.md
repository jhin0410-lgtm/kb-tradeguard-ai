# KB TradeGuard AI v2 Data and Risk Plan

## Goal

Extend the existing deterministic trade-risk engine into a global trade-finance copilot while preserving the current trust boundary: external models may extract, classify, and explain, but deterministic services remain authoritative for financial calculations and no output is represented as an executable KB quote, official credit rating, approval, or suitability decision.

## Existing assets to integrate first

- Bank of Korea ECOS API: Korean macroeconomic series, policy and market rates.
- Korea Eximbank exchange-rate API: official reference-rate snapshot.
- OpenDART API: financial statements and corporate disclosures.
- World Bank Indicators API: country macro and development indicators.
- IMF DataMapper / IMF SDMX: country forecasts and external-sector indicators.
- Hugging Face datasets: document-AI training and evaluation datasets, subject to each dataset card and license.

## Additional data sources

### Priority 1

1. Korea Customs Service country and HS-code trade APIs
   - country concentration, HS-code market exposure, import/export trend.
2. OECD country-risk classifications
   - export-credit country-risk reference input; never presented as a KB rating.
3. World Bank Worldwide Governance Indicators
   - political stability, government effectiveness, regulatory quality, rule of law, and control of corruption.
4. Official sanctions lists
   - OFAC and UN list snapshots for counterparty-name screening; results require human review and do not constitute legal clearance.
5. Official benchmark rates
   - KRW from ECOS; USD SOFR; EUR euro short-term rate; later JPY/GBP benchmarks.
6. KB and K-SURE public product catalogue
   - versioned product facts, target customer, currency, purpose, tenor, collateral/guarantee notes, effective date, source URL, and mandatory verification flags.

### Priority 2

1. UN Comtrade
   - global reporter-partner-HS trade structure and market concentration.
2. IMF PortWatch
   - experimental shipping-disruption indicator, clearly labelled experimental.
3. KRX and DART event labels
   - delisting, rehabilitation, qualified/adverse audit opinion, default and other distress proxies for model research only.
4. DocILE
   - primary business-document extraction benchmark; use annotated, synthetic, and unlabeled partitions according to its licence.

## Target architecture

```text
src/
  data_providers/
    base.py
    cache.py
    bok_ecos.py
    kexim_fx.py
    opendart.py
    world_bank.py
    imf.py
    customs_trade.py
    oecd_country_risk.py
    wgi.py
    sanctions.py
    benchmark_rates.py
    product_catalog.py
  intelligence/
    market_snapshot.py
    country_risk.py
    trade_concentration.py
    financial_health.py
    distress_research.py
    hedge_strategy.py
    product_match.py
    document_benchmark.py
config/
  indicator_registry.yaml
  country_aliases.yaml
  currency_conventions.yaml
  risk_weights.yaml
  product_catalog.yaml
  data_source_policies.yaml
```

## Canonical metadata contract

Every external observation must preserve:

- provider and source series identifier;
- observation date and retrieval timestamp;
- frequency and unit;
- quote convention and base/term currency where applicable;
- raw value and normalized value;
- stale-after policy and current staleness state;
- licence/reference URL;
- transformation and interpolation notes;
- content checksum for downloaded files.

No model or screen may silently mix daily, monthly, quarterly, and annual observations.

## Engines

### Market and forward engine

Upgrade the existing single-rate input to a tenor-aware market snapshot:

- official reference spot rate;
- KRW and foreign benchmark curves;
- tenor interpolation;
- source timestamp and stale-data warning;
- theoretical forward curve and settlement-date theoretical forward;
- separate optional manual/bank quote input.

The output remains an indicative theoretical calculation, not an executable KB price.

### Country and trade-risk engine

Produce a transparent 0-100 internal screening score with separate pillars:

- macro stability;
- external vulnerability;
- governance and institutional risk;
- bilateral trade concentration and product concentration;
- logistics/disruption;
- sanctions and compliance flags.

Return every component, missing-data ratio, confidence band, data dates, and reasons. Never label the result an official sovereign or KB rating.

### Financial-health engine

Use OpenDART to calculate transparent ratios and event flags:

- liquidity and leverage;
- interest coverage;
- operating cash flow;
- profitability and growth;
- receivable days and working-capital pressure;
- foreign-currency debt and trade concentration where available;
- disclosure-based distress flags.

Initial production output is a financial-health screening, not an official credit grade. Machine-learning distress research must remain a separately labelled experimental module until validated on time-split Korean data.

### Hedge-strategy engine

Compare deterministic strategies:

- no hedge;
- partial and full forward hedges;
- maturity-split hedge;
- natural hedge and explicit foreign-cash allocation;
- settlement-date adjustment;
- working-capital financing combined with hedge;
- scenario and Monte Carlo loss distributions.

Optimization should minimize a weighted combination of cash shortfall, downside FX loss, hedge cost, over-hedge penalty, and concentration risk. All weights and constraints must be visible.

### Product-match engine

Use a versioned rules catalogue rather than free-form model generation. Return ranked consultation candidates with:

- matched need;
- satisfied and unsatisfied conditions;
- source and effective date;
- information still required from the customer;
- explicit verification and professional-review requirement.

## Document AI and scale

Use DocILE as the main large business-document benchmark and add a trade-document gold set. Evaluation must report:

- field exact match and normalized F1;
- line-item recognition;
- required-field complete extraction rate;
- false automatic-approval rate;
- review-queue precision;
- throughput and latency at 100, 1,000, and 10,000 documents;
- performance by layout, language, currency, and document type.

Large-scale capability should use batch manifests, streaming datasets, checkpointing, idempotent document hashes, and resumable jobs rather than loading all documents into Streamlit memory.

## Delivery order

1. Data-provider interfaces, cache, provenance, and fixtures.
2. ECOS, Eximbank FX, World Bank, IMF, and OpenDART adapters.
3. Customs trade, OECD country risk, WGI, and benchmark-rate adapters.
4. Executive dashboard with market, country, trade-concentration, and financial-health cards.
5. Product catalogue and deterministic product matching.
6. Document benchmark and batch-processing pipeline.
7. Optional experimental distress and FX-distribution models.
8. UI polish, tests, evidence export, and submission materials.

## Non-negotiable guardrails

- API keys only through environment variables; never commit credentials.
- Cached responses must be redacted where necessary and excluded from Git unless they are approved public fixtures.
- Live API failure must fall back to timestamped fixtures or a clearly labelled unavailable state, never fabricated values.
- No executable quote, official credit rating, eligibility, approval, guarantee, or suitability claim.
- Every recommendation must cite source observations, deterministic calculation IDs, assumptions, and limitations.
