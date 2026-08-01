# Final Human Validation and Release Gate

The software-side competition hardening is merged into `main`. The remaining items require human participants or repository/deployment operations and must not be represented as completed before evidence exists.

## 1. Five-person usability study

- Recruit at least five anonymous participants according to `docs/USABILITY_TEST_PROTOCOL.md`.
- Use the deployed public demo and the default `oa_high_risk` scenario.
- Record no names, contact details, customer documents, or credentials.
- Copy `data/usability_test_results_template.csv` to a non-template results file and enter only actual observations.
- Run:

```powershell
py -3.13 scripts/summarize_usability_results.py data/usability_test_results.csv --output outputs/usability_test_summary.json
```

- Preserve the anonymous raw CSV, generated JSON, participant profiles, test dates, and devices.
- Report unsuccessful criteria and negative feedback without alteration.

## 2. Deployment and presentation evidence

- Confirm the merged `main` revision is deployed through `streamlit_app.py`.
- Test desktop and mobile layouts.
- Verify the four-stage navigation: `판정 | 시나리오 | 금융지원 | 근거`.
- Verify scenario changes update the governed charts and product candidates.
- Confirm missing inputs hide unavailable charts instead of showing illustrative values.
- Save the offline presentation HTML and audit JSON.
- Capture only synthetic cases and remove browser/account chrome from submission images.

## 3. Final repository release

- Create the final competition release tag only after deployment and human-test evidence are fixed.
- Suggested tag: `v1.3.0-competition-final`.
- Delete merged and obsolete automation branches after confirming no evidence depends on them.
- Keep `main`, the release tag, merged PR history, and final validation artifacts.

## Completion boundary

A green CI run proves deterministic repository consistency, not real-user usability, legal correctness, live API availability, bank approval, product eligibility, or production readiness.
