# KB TradeGuard

KB TradeGuard is a Python 3.11+ competition prototype for Korean SME exporters
and importers. It combines human-reviewed trade-document registration,
deterministic FX and liquidity analysis, and a read-only explainable advisory
layer.

The deterministic engine is the sole authority for exposure, cash-flow,
forward-rate, natural-offset, cash-allocation, and hedge calculations. The
advisor can select those read-only tools and explain their structured outputs;
it does not do financial arithmetic or modify the portfolio.

## What the application provides

The primary Copilot entrypoint composes the reviewed case into one auditable
workspace containing the objective, dependency-aware plan, data readiness,
scenario candidates, grounded risk chains, consultation questions, execution
trace, citations, and audit export. It does not execute scenarios or approve
financial decisions.

The supporting Streamlit application retains seven detailed tabs:

1. multi-row document review and explicit approval;
2. portfolio;
3. exposure and maturity;
4. liquidity and foreign-cash allocation;
5. deterministic hedge comparisons;
6. considerations and audit export;
7. read-only grounded financial advisory.

CSV extraction returns every non-empty transaction row. XLSX extraction
inspects every sheet, detects likely header rows, and preserves sheet and row
provenance. Extraction never registers a transaction. Each candidate must be
approved. Canonical duplicate warnings consider document reference, direction,
currency, amount, date, and counterparty independently of the source filename.
File identity is tracked separately using content SHA-256, filename, and size.

Document confidence is deliberately split:

- `parsing_confidence`: technical certainty that a source value was read;
- `semantic_mapping_confidence`: confidence that the source field has the
  intended business meaning;
- `validation_status`: `valid`, `review_required`, or `invalid`.

An exact cell read can therefore have parsing confidence 1.0 without semantic
confidence 1.0.

## Advisory and grounding

Without external configuration, the app uses the clearly labeled
`Deterministic fallback — not live AI.` It applies intent rules and templates
but calls the same deterministic financial tools.

If both the optional OpenAI Python package and `OPENAI_API_KEY` are available,
the configured structured provider may classify intent using JSON-schema
output. It still cannot calculate financial values or write to the portfolio.
If provider classification fails, the orchestrator falls back safely.

Every financial tool returns a calculation name, assumptions, result, unit,
as-of date, source, limitations, deterministic calculation ID, engine version,
normalized input hash, timestamp, source identifiers, and analysis basis.
Calculation IDs are traceability identifiers, not proof of correctness.
Numerical claims must cite the relevant ID. Policy statements cite a reviewed local
excerpt as `[Document ID, title, excerpt ID]`. A validator rejects uncited
numbers, uncited policy claims, affirmative eligibility/approval/guarantee
claims, and claims that a theoretical forward is an executable KB quote.

The local corpus in `data/policy_docs/` contains short
`project_authored_summary` files based on linked public official guidance.
They are not official source documents or copied commercial material. Only
manifest entries marked `approved_reference` are searchable. Publication,
retrieval, missing-effective-date, and staleness information is surfaced.
Availability and customer eligibility always require current verification.

## Run

Primary Global Trade Copilot workspace:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run copilot_app.py
```

Supporting detailed seven-tab dashboard:

```powershell
python -m streamlit run app.py
```

The policy-independent one-command Windows launcher is `run.cmd`.
`.\run.ps1` is also provided where PowerShell script execution is enabled.

Optional structured advisory classification:

```powershell
python -m pip install openai
$env:OPENAI_API_KEY = "<your key>"
$env:OPENAI_ADVISOR_MODEL = "<structured-output-capable model>"
python -m streamlit run app.py
```

When configured mode is used, the advisory question and structured
deterministic tool outputs are transmitted to the configured provider.
Uploaded document bytes are not sent by the advisory path. Optional document
LLM extraction is a separate choice and does transmit the document content
required by that provider.

## Verify

```powershell
python -m pytest -q
python -m compileall -q app.py copilot_app.py src tests
python -c "import app; import copilot_app; import src"
```

The equivalent one-command check is `test.cmd`; `.\test.ps1` is also provided.
CI runs pytest, compilation, and imports on Python 3.11.

## Demo, evidence, and notices

Bundled demo mode is enabled by default. It loads only synthetic sample data,
disables uploads and portfolio mutation, supports the five official demo
questions, and can restore the initial state. See `docs/sample-data-notice.md`,
`docs/privacy.md`, and `docs/troubleshooting.md`.

`python scripts/provider_smoke_test.py` is the manual configured-provider
check. It writes no transcript when configuration is unavailable. A successful
run uses synthetic data and writes redacted evidence without credentials or
uploaded documents.

This prototype has no real-time rates, OCR, transaction execution, actual KB
system/product/pricing integration, official credit rating, credit limit, loan approval, eligibility or suitability decision, guaranteed result, or
personalized financial advice. All outputs are simulations or general
considerations requiring professional review.
