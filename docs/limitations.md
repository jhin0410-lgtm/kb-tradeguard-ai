# Limitations

- The app uses bundled or user-entered FX/rate assumptions. It has no real-time
  market data or executable pricing.
- Forward rates are indicative covered-interest-parity calculations using
  configured assumptions and ACT/365 tenor. They are not actual KB quotes.
- The approved policy corpus is a small local set of project-authored summaries,
  not official source documents. Retrieval is lexical, not legal interpretation, and does
  not prove current product availability, eligibility, or document sufficiency.
- Missing effective dates and corpus age are shown as warnings. A source can
  change after its retrieval date, so users must verify important information
  with the issuing organization.
- The configured structured advisor is optional. It classifies questions but
  does not calculate values. Provider outages or invalid responses trigger the
  deterministic fallback.
- In configured advisory mode, questions are sent to the configured provider.
  Optional document LLM extraction may transmit document content. Organizations
  must assess consent, retention, confidentiality, and provider terms before
  enabling either path.
- PDF support is extractable text only; scanned files require OCR, which is not
  implemented. TXT/PDF extraction does not invent missing structured fields.
- Header detection and aliases are deterministic and may require human edits.
  Parsing confidence 1.0 proves only that a cell was read, not that its business
  meaning is certain.
- Fingerprints reduce duplicate risk but cannot prove two records represent the
  same legal transaction. The probable-near-duplicate key is deliberately
  coarse, so human review remains required.
- Session state is not a durable system of record. Uploaded bytes are held in
  process memory and are not placed in audit exports.
- Maturity buckets and monthly cash flow simplify intramonth timing. Foreign
  cash allocation is analytical and does not reserve or transfer funds.
- There is no transaction execution, account integration, actual KB product or
  pricing integration, official rating, credit limit, loan approval,
  eligibility/suitability determination, guaranteed result, or personalized
  financial, legal, or tax advice.
