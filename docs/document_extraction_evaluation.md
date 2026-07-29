# Independent document-extraction evaluation

## Purpose

The existing 30 Gold cases and 150 mutations test deterministic rules on already reviewed fields. They do not measure whether an AI or parser can correctly extract fields from original contracts, invoices, purchase orders, or letters of credit.

`src/intelligence/document_extraction_evaluation.py` provides a separate field-level holdout evaluation boundary. It compares human-reviewed annotations with parser or model predictions and reports errors without converting an internal synthetic regression result into an external accuracy claim.

## Supported document groups

- contract
- commercial invoice
- purchase order
- letter of credit
- packing list
- bill of lading
- other

The first independent dataset should include at least contracts, invoices, purchase orders, sight L/Cs, usance L/Cs, and acceptance L/Cs. Results must be reported separately by document type and language.

## Private-data layout

Do not commit raw customer documents or private annotations. Store them locally under an ignored path such as:

```text
data/private/document_extraction/
  original_documents/
  reviewed_holdout.json
```

Only a redacted aggregate report may be copied into a submission package after checking licensing, confidentiality, and re-identification risk.

## Dataset contract

Each case records:

- unique case ID;
- document type and language;
- `holdout` split;
- data origin: `public_licensed`, `private_authorized`, or `synthetic`;
- source locator and license or authorization note;
- reviewer count;
- expected and predicted values for each governed field;
- extraction status: `extracted`, `abstained`, or `missing`;
- comparison mode: exact, normalized text, number, or date.

A synthetic case automatically changes the report scope to `mixed_or_synthetic`. Such a report must not be described as real-document accuracy.

## Metrics

The evaluator reports:

- field exact-match rate;
- document exact-match rate;
- micro precision, recall, and F1;
- abstention rate;
- false positives;
- false negatives;
- value mismatches;
- results by document type;
- results by language;
- a complete error ledger.

A wrong extracted value counts as both a false positive and a false negative because the system emitted an unsupported value and failed to return the correct one.

## Run the example

```powershell
python scripts/evaluate_document_extraction.py `
  examples/document_extraction_evaluation_example.json `
  --output outputs/document_extraction_evaluation_example_report.json
```

The example is synthetic and validates only the file format and metric implementation.

## Build a credible holdout set

1. Freeze the extraction schema and prompt before selecting holdout documents.
2. Keep holdout documents out of prompt development and rule design.
3. Obtain explicit permission or verify a public license.
4. Remove business identifiers not needed for evaluation.
5. Have at least one reviewer annotate each document; use two reviewers for high-impact fields where possible.
6. Record disagreements and a final adjudication rule.
7. Run extraction once on the frozen system version.
8. Preserve predictions, abstentions, system version, dates, and hashes.
9. Publish aggregate results and representative redacted errors, not confidential documents.

## Required claim boundary

Allowed:

> On the independently reviewed holdout set, the frozen extraction system achieved the reported field-level metrics, with results separated by document type and language.

Not allowed:

> The AI understands all trade documents accurately or replaces legal, banking, insurance, sanctions, or credit review.

The evaluation covers field extraction only. It does not establish legal interpretation accuracy, transaction approval quality, buyer credit performance, sanctions clearance, product eligibility, or production suitability.
