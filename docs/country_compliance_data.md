# Country and Compliance Data Layer

## Purpose

This layer supplies auditable country-context facts for the reference trade case. It does not produce a composite country score, buyer credit grade, transaction approval, or institution-specific AML decision.

## World Bank Indicators API

The provider uses the official World Bank Indicators API v2 and requires no API key.

The first governed indicator set is intentionally narrow:

- `NY.GDP.MKTP.KD.ZG`: real GDP growth;
- `FP.CPI.TOTL.ZG`: consumer-price inflation;
- `FI.RES.TOTL.MO`: reserves in months of imports;
- `BN.CAB.XOKA.GD.ZS`: current-account balance as a percentage of GDP.

Each non-null observation becomes a typed `CountryRiskFact` with:

- official source URL;
- observation year;
- retrieval timestamp;
- response hash;
- unit and risk direction;
- interpretation and limitations.

Missing observations remain missing. The provider does not impute values or apply project-defined cut-offs.

## FATF public-list snapshot

The reviewed snapshot is stored at:

```text
data/reference/fatf_jurisdictions_2026-06-19.json
```

It records the official FATF public statements published on 19 June 2026:

- high-risk jurisdictions subject to a call for action;
- jurisdictions under increased monitoring.

A listed country becomes a sourced screening flag requiring current compliance review. It is not automatically treated as a prohibited transaction. A country absent from the snapshot is described only as not listed in those two statements; absence does not establish low AML/CFT risk.

The default freshness limit is 150 days. Older snapshots are retained for audit but marked `stale`.

## Manual verification

```powershell
python scripts/country_context_smoke_test.py VN --country-name Vietnam
python scripts/country_context_smoke_test.py US --country-name "United States"
```

The script performs live World Bank calls and combines the results with the reviewed FATF snapshot. Output is JSON and retains the authority boundary.

## Not yet implemented

The following remain separate delivery units:

- UN Security Council consolidated-list entity and person screening;
- export-control and restricted-goods screening;
- OECD country-risk classifications;
- K-SURE country underwriting policy and country-information integration;
- country facts attached automatically to a complete transaction assessment;
- governed risk ranking across buyer, payment, document, company, and country evidence.
