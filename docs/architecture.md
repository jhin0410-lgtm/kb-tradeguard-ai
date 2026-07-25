# Architecture

```text
uploaded CSV/XLSX/PDF/TXT (memory only)
               |
     deterministic/optional extraction
               |
 candidates + field provenance + split confidence
               |
 review queue -> edit/reject/explicit approval -> session portfolio
                                               |
            deterministic calculation modules |
 exposure / cash flow / forwards / offsets / allocation / hedging
                         |
              read-only advisor tools
                         |
 intent provider -> controlled tool calls -> answer synthesis
      |                                      |
 deterministic fallback             calculation citations
 or configured structured AI        + local policy citations
                         |
                 answer validator
```

## Authority and boundaries

`advisor_tools.py` is a read-only façade over the existing deterministic
modules. Inputs are copied and there are no registration, edit, approval, or
deletion methods. Each financial result has a reproducible `CALC-*` identifier,
the exact assumptions, analysis basis, source identifiers, normalized input
hash, engine version, timestamp, as-of date, unit, and limitations. The ID
traces an output; it does not certify correctness.

`advisor_orchestrator.py` separates classification, tool execution, synthesis,
and validation. `ConfiguredStructuredAdvisor` may classify intent only when
valid optional configuration exists. `DeterministicOfflineAdvisor` supports
the same tool route without network access. Neither is a calculation engine.

`policy_retrieval.py` performs deterministic BM25-style search over only
`approved_reference` entries in `data/policy_docs/manifest.json`. Returned
project-authored excerpts retain the official issuer/link separately from
local-summary provenance, checksum, review dates, freshness warnings, and the
general-information boundary.

`answer_validation.py` fails closed on ungrounded numerical and policy claims
and prohibited advisory wording. `citation_models.py` defines calculation and
document citation records.

## Document workflow

`document_extraction.py` emits a list of candidates. It scans every workbook
sheet and preserves the source sheet and row for each mapped field.
`document_models.py` separates parsing certainty, semantic mapping certainty,
and validation status. `document_validation.py` creates the review queue,
computes filename-independent canonical transaction fingerprints plus separate
upload-file identities, detects duplicate categories, and registers
only explicitly approved candidates. Batch approval invokes and records the
same per-candidate approval path.

Session state and `provenance.py` provide an exportable audit trail; they are
not a durable production system of record.
