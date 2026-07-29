# Single-Transaction Assessment Package

## Purpose

The JSON package boundary makes the governed single-transaction pipeline usable without constructing Python domain objects inside application code.

A package contains:

```text
single reviewed UnifiedCopilotCase
+ SingleTransactionAssessmentRequest
+ optional expected input case hash
+ review notes
```

The package runner validates the cross-links, executes the deterministic pipeline, and exports machine-readable audit artifacts plus a human-readable Markdown report. It does not fetch missing data, approve evidence, interpret raw documents, or make a bank, insurer, legal, sanctions, or AML decision.

## Package model

```json
{
  "package_version": "single-transaction-package/1.0",
  "case": {
    "identity": {
      "case_id": "CASE-001",
      "company_name": "Example Exporter Co., Ltd.",
      "analysis_as_of_date": "2026-07-26"
    },
    "evidence": [],
    "approved_transactions": [
      {
        "transaction_id": "EXP-001",
        "transaction_type": "export",
        "currency": "USD",
        "amount_fc": 500000,
        "expected_date": "2026-10-31"
      }
    ],
    "trade_finance": {
      "counterparties": [],
      "country_risk_facts": [],
      "compliance_screenings": [],
      "payment_structures": [],
      "trade_documents": [],
      "financial_statements": []
    }
  },
  "request": {
    "pipeline_id": "PIPELINE-EXP-001",
    "brief_id": "BRIEF-EXP-001",
    "transaction_id": "EXP-001",
    "counterparty_id": null,
    "country_code": null,
    "reconciliation_policy": {},
    "capacity_request": null,
    "product_profiles": [],
    "max_ranked_concerns": 5
  },
  "expected_input_case_hash": null,
  "notes": []
}
```

All nested objects remain subject to their existing strict Pydantic contracts. Unknown fields are rejected where the domain model uses `extra="forbid"`.

## Package-level validation

The package rejects:

- an unsupported package version;
- more than one approved transaction;
- a request transaction that differs from the case transaction;
- an invalid SHA-256 value;
- an `expected_input_case_hash` that does not match the supplied case snapshot;
- nested capacity or product requests linked to another transaction;
- malformed JSON or invalid nested domain records.

The expected hash is optional. When present, it protects against running a package after the reviewed case content has changed.

## Canonical package hash

`package_hash` is computed over:

- the timestamp-stable case canonical snapshot;
- the pipeline request;
- the expected input case hash;
- package notes;
- the package version.

`CaseIdentity.created_at` and calculation timestamps do not affect the canonical case hash. Substantive changes to evidence, transactions, assumptions, documents, calculations, or domain records do affect it.

## CLI

```powershell
py -3.13 scripts/run_single_transaction_package.py `
  path\to\assessment_package.json `
  --output-dir outputs\CASE-001
```

When `--output-dir` is omitted, output is written below:

```text
outputs/<input-file-stem>/
```

A successful CLI response prints:

- package and case hashes;
- pipeline and transaction IDs;
- final disposition;
- completed or skipped stage statuses;
- missing information;
- artifact paths;
- the authority boundary.

A validation or pipeline failure returns exit code `1` and does not report a successful assessment.

## Exported artifacts

The package runner writes:

```text
updated_case.json
updated_case_canonical.json
assessment_result.json
decision_brief.json
decision_brief.md
stage_trace.json
audit_summary.json
artifact_manifest.json
```

`decision_brief.md` is a deterministic Korean review report containing:

- transaction summary and final pre-screening disposition;
- ranked concerns with factual bases and source IDs;
- missing information;
- selected KB and K-SURE consultation candidates;
- consultation conditions;
- dependency-aware action plan;
- pipeline stage trace and case hashes;
- evidence, calculation, product, consultation, and rule references;
- authority boundary and limitations.

The Markdown renderer uses only the completed case and assessment result. It adds no new risk conclusion or calculation. It rejects a case whose hash differs from the assessment result output hash.

`artifact_manifest.json` records:

- package version;
- input package hash;
- input and output case hashes;
- pipeline version;
- transaction ID;
- SHA-256 hash of every exported artifact, including the Markdown report;
- authority boundary and limitations.

Files are written atomically through a temporary file and replacement operation. The manifest is written after the other artifacts.

## Input preparation boundary

The JSON package accepts reviewed structured records. It is not a raw-document ingestion format.

Before a contract, invoice, L/C, financial statement, country fact, or screening result is placed in a package:

1. its source must be identified;
2. the relevant fields must be reviewed;
3. evidence status must reflect whether human approval has occurred;
4. document and payment records must be linked to the transaction;
5. explicit assumptions such as protection percentage and funding need must be disclosed;
6. missing information must remain missing rather than be inferred.

## Validation

```powershell
py -3.13 -m pytest -q tests/test_single_transaction_pipeline.py
py -3.13 -m pytest -q tests/test_single_transaction_package.py
py -3.13 -m pytest -q tests/test_decision_brief_report.py
py -3.13 -m pytest -q
py -3.13 -m compileall -q app.py copilot_app.py src tests scripts
py -3.13 -c "import app; import copilot_app; import src"
```

## Next delivery unit

The next delivery unit should build a controlled intake assembler that produces this package from:

- reviewed company and counterparty forms;
- OpenDART normalized financial snapshots;
- reviewed contract, invoice, and L/C fields;
- official country and compliance facts;
- explicit FX, funding, protection, and product-need inputs.

Raw document parsing must remain separated from human approval and package creation.
