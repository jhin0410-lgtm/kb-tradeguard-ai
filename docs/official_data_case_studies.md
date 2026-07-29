# Official public-data case studies

The competition application includes three pinned public-context cases:

1. Vietnam / HS 85 / Korean exports
2. United States / HS 33 / Korean exports
3. Japan / HS 84 / Korean imports

The decision questions and companies are synthetic. The World Bank macro observations and UN Comtrade aggregate trade values were retrieved from the public APIs on 2026-07-29 and stored in `data/case_studies/official_context_snapshots_v1.json` with retrieval timestamps and response hashes.

## Interpretation boundary

- The cases do not represent a real customer, buyer, supplier, shipment, declaration, credit decision, product approval, or executable FX quote.
- World Bank indicators have different observation years and publication lags.
- UN Comtrade Preview is aggregate, rate-limited, and not a complete extraction.
- Pinned values can differ from later API responses because official statistics may be revised.
- The data provides context only; it does not determine transaction approval, credit quality, compliance clearance, hedge suitability, insurance acceptance, or financing eligibility.

## Re-running the smoke test

Use the manual GitHub Actions workflow `official-data-live-smoke`, or run locally:

```powershell
py -3.11 scripts/official_data_smoke_test.py `
  --output-report artifacts/official-data-live-smoke.json `
  --output-snapshots artifacts/official-context-snapshots.json
```

World Bank and UN Comtrade require no key. Secret-dependent paths are attempted only when their deployment credentials are present. OpenDART and NTS also require explicit reviewed lookup identifiers through environment variables; the script does not guess or embed a company identifier.

To require all secret-dependent paths:

```powershell
py -3.11 scripts/official_data_smoke_test.py `
  --output-report artifacts/official-data-live-smoke.json `
  --output-snapshots artifacts/official-context-snapshots.json `
  --require-configured
```

The smoke report never prints credential values or credential-bearing request URLs.
