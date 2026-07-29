# UN Comtrade public-preview integration

## Role in the competition prototype

The public Streamlit app needs at least one real trade-statistics path that works without deployment secrets. `src/data_providers/un_comtrade.py` connects to the official UN Comtrade public preview API for a bounded reporter-partner-product query.

Current competition query:

```text
reporter: Republic of Korea
partner: selected transaction country
frequency: annual
flow: export or import
product: TOTAL or HS 2/4/6 digit
period: one year
maximum records: 100 in the UI
```

## Why preview mode

The official preview endpoint does not require an account or subscription key. It is suitable for a quick public demonstration but has record and rate limits. A complete research or production extraction should use an appropriately authorized free or premium API tier and preserve the subscription key outside the repository.

## Returned evidence

The adapter normalizes:

- period;
- reporter and partner codes and names;
- flow;
- HS code and product description;
- primary trade value in USD;
- FOB and CIF values when supplied;
- net weight and quantity;
- reported and aggregate flags;
- retrieval time and response hash.

## Trust boundary

UN Comtrade provides official aggregate trade statistics reported by countries and areas. It does not expose buyer, supplier, customer, or company-level trade records.

The data can be revised, annual and monthly totals can differ, and mirror statistics between partners can be asymmetric. The preview result is therefore country-product context only. It cannot prove a specific company's exports, determine buyer credit, predict an exchange rate, select a hedge ratio, approve financing, or establish insurance or guarantee eligibility.
