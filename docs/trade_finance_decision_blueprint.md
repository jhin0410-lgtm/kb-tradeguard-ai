# Trade Finance Decision Blueprint

## 1. Purpose

KB TradeGuard must be evaluated as a trade-finance decision-support product, not as a collection of FX calculators, agent traces, or UI cards.

The product objective is:

> Help a Korean SME assess one material export or import transaction before commitment by combining company capacity, counterparty and country context, document terms, payment structure, foreign-exchange exposure, and publicly verifiable insurance, guarantee, and banking consultation candidates.

The system does not determine an internal bank credit grade, approve a facility, guarantee insurance acceptance, or provide an executable KB price. It performs evidence-backed pre-screening and consultation preparation.

## 2. Primary unit of analysis

The primary analysis unit is:

```text
Company × Transaction × Counterparty × Country × Contract Terms
```

A company-level ratio alone is insufficient. A transaction-level cash-flow simulation alone is also insufficient. The decision must connect the transaction to the company's ability to absorb non-payment, delay, foreign-exchange movement, document discrepancy, and funding needs.

## 3. Target user and target decision

### Primary user

A Korean SME owner, finance manager, or trade practitioner preparing a material export transaction with a new or important overseas buyer.

### Secondary user

A bank relationship manager using the package to understand the customer's need, identify missing documents, and route the consultation to the appropriate trade-finance or foreign-exchange specialist.

### Core decision questions

1. Is the transaction sufficiently understood to proceed, or are critical facts missing?
2. Which risks are material: buyer, country, payment, document, liquidity, concentration, foreign exchange, sanctions, or operational execution?
3. Which contract or L/C terms should be clarified or revised before commitment?
4. Can the company absorb a delay or loss relative to disclosed financial capacity?
5. Which mitigation structures are plausible candidates?
6. Which KB consultation route, K-SURE service, insurance, or guarantee category should be checked?
7. What should the user do next, in what order, and with which documents?

## 4. Required output contract

Every completed assessment should return the following sections in this order.

### 4.1 Decision status

One of:

- `proceed_with_current_evidence`
- `proceed_after_condition_improvement`
- `insurance_or_bank_support_should_be_checked_before_proceeding`
- `counterparty_due_diligence_required`
- `insufficient_evidence`
- `material_compliance_blocker`

This is a project pre-screening result, not a bank approval or legal opinion.

### 4.2 Top risks

No more than five ranked risks. Each risk must include:

- category;
- factual trigger;
- affected transaction or document;
- materiality measure where available;
- evidence IDs and calculation IDs;
- mitigating facts;
- unresolved facts;
- limitations.

### 4.3 Contract and document actions

For each material contract or L/C issue:

- source clause or field;
- issue type;
- failure path;
- suggested clarification or revision;
- whether legal, bank, insurer, logistics, or customs review is needed.

### 4.4 Financial capacity connection

Stress results must be normalized against company capacity, where available. At minimum:

- transaction amount / cash and cash equivalents;
- maximum stressed cash shortfall / cash and cash equivalents;
- maximum stressed cash shortfall / quick assets;
- 90-day foreign-currency outflow / cash and cash equivalents;
- largest buyer receivable / equity;
- short-term borrowings / cash and cash equivalents;
- operating cash flow / total borrowings;
- residual net foreign-currency exposure / equity.

Missing denominators must block the associated interpretation rather than produce an invented ratio.

### 4.5 Mitigation options

Generate two or three realistic structures rather than one product recommendation. Each option must state:

- risk addressed;
- transaction stage;
- mechanism;
- residual risk;
- information or eligibility still requiring verification;
- required documents;
- official source references;
- operational next step.

### 4.6 Consultation candidates

The system may identify product or service candidates only when the need and public conditions match. It must distinguish:

- verified public condition;
- user-provided fact;
- inferred match;
- unresolved eligibility condition;
- institution-specific decision.

The output must say `consultation candidate`, not `approved`, `eligible`, `guaranteed`, or `best product`.

### 4.7 Action plan

Return an ordered list, normally three to seven actions. The order must reflect dependency and risk reduction, for example:

1. identify or verify the counterparty;
2. resolve a contract or L/C blocker;
3. check K-SURE investigation, insurance, or guarantee applicability;
4. prepare KB consultation documents;
5. structure funding or receivables financing;
6. hedge only the residual currency exposure.

## 5. Risk taxonomy

### 5.1 Counterparty risk

- identity uncertainty;
- weak or unavailable financial information;
- adverse public records;
- payment history concerns;
- buyer concentration;
- parent or guarantor uncertainty;
- professional credit investigation required.

### 5.2 Country and transfer risk

- sovereign or transfer restrictions;
- foreign-exchange liquidity stress;
- external-debt vulnerability;
- political violence or expropriation;
- sanctions and AML status;
- import restriction or licensing risk;
- enforceability and recovery difficulty.

Country context cannot substitute for buyer due diligence.

### 5.3 Payment and instrument risk

- open-account tenor;
- advance-payment imbalance;
- documentary collection weakness;
- issuing-bank and confirming-bank uncertainty;
- L/C availability and expiry;
- reimbursement structure;
- document discrepancy exposure;
- buyer-controlled payment condition.

### 5.4 Contract and document risk

- missing or ambiguous Incoterms rule, year, or named place;
- inconsistent amount, currency, quantity, dates, or party names;
- undefined inspection or acceptance period;
- buyer-controlled evidence requirements;
- impractical shipment and presentation timetable;
- broad unilateral amendment, set-off, termination, warranty, or indemnity terms;
- unclear governing law or dispute resolution;
- sanctions, export-control, insurance, transport, and title-transfer inconsistency.

### 5.5 Company capacity and liquidity risk

- transaction size relative to immediately available liquidity;
- short-term borrowing concentration;
- working-capital dependence;
- weak operating cash generation;
- maturity mismatch;
- receivables and inventory concentration;
- insufficient unused funding visibility.

### 5.6 Foreign-exchange risk

- gross exposure;
- natural offset;
- timing mismatch;
- transaction-currency concentration;
- residual exposure after existing hedges;
- foreign-currency debt interaction;
- hedge instrument and accounting limitations.

FX risk must not automatically outrank buyer, document, or liquidity risk.

### 5.7 Compliance and operational risk

- sanctions name match;
- FATF status;
- restricted goods or destination;
- customs or licensing requirements;
- missing shipping, insurance, inspection, or origin documents;
- transaction facts inconsistent across sources.

## 6. Evidence hierarchy

### Tier 1 — authoritative or transaction-direct evidence

- reviewed user documents;
- OpenDART filings and XBRL source records;
- K-SURE official pages and published rules;
- KB official product disclosures;
- OECD, World Bank, IMF, BIS, FATF, UN, Korean government, customs, and central-bank sources.

Tier 1 may support deterministic rules and principal findings.

### Tier 2 — reputable contextual evidence

- government trade guides;
- KOTRA and trade-association publications;
- official country agencies;
- established multilateral or legal guidance.

Tier 2 may support context but should not override transaction documents or official product terms.

### Tier 3 — discovery signals

- news;
- general web sources;
- industry commentary.

Tier 3 can trigger further review but cannot alone establish eligibility, sanctions status, financial capacity, or a binding country-risk conclusion.

## 7. Deterministic versus AI authority

### Deterministic responsibilities

- financial ratios;
- exposure and cash-flow calculations;
- maturity aggregation;
- document field reconciliation;
- sanctions-list exact and configured fuzzy matching;
- policy-rule evaluation;
- product-condition matching;
- evidence and calculation identifiers;
- input completeness and staleness checks.

### AI responsibilities

- classify clauses and user needs;
- connect risk facts across evidence domains;
- explain causal risk chains;
- identify contradictions and missing information;
- rank risks using governed features and explicit rationale;
- assemble mitigation structures from validated candidates;
- generate a cited consultation brief.

AI must not invent financial values, unpublished bank rules, product eligibility, insurance acceptance, legal conclusions, or counterparty credit quality.

## 8. Data model implications

The current `UnifiedCopilotCase` remains the audit envelope but must no longer treat financial and policy context as unstructured catch-all payloads only.

The future domain layer should introduce typed records for:

- `CompanyProfile`;
- `FinancialStatementSnapshot`;
- `FinancialMetric`;
- `CounterpartyProfile`;
- `CountryRiskFact`;
- `ComplianceScreeningResult`;
- `TradeDocumentProfile`;
- `ContractClauseFinding`;
- `PaymentStructure`;
- `TradeRiskSignal`;
- `MitigationOption`;
- `ProductCandidate`;
- `ConsultationRequirement`;
- `ActionPlanItem`.

Every typed record must retain source, as-of date, retrieval date, status, and limitations.

## 9. First reference scenario

Development should optimize one narrow, end-to-end reference case before broadening.

### Scenario

A Korean SME exporter plans a material goods sale to a new buyer in Vietnam or the United States under either open-account terms or a letter of credit.

### Minimum inputs

- company identifier;
- buyer legal name and country;
- contract or purchase order;
- commercial invoice;
- L/C or disclosed payment terms;
- currency, amount, shipment date, due date;
- reviewed transaction facts;
- available company financial statements.

### Required result

- company financial-health pre-screening;
- country and compliance context;
- buyer due-diligence status;
- document and payment-condition findings;
- transaction-to-capacity metrics;
- calibrated or reverse stress where data supports it;
- K-SURE service, insurance, or guarantee consultation candidates;
- KB consultation candidates based only on current public disclosures;
- missing evidence;
- ordered action plan.

## 10. Delivery gates

A new feature should not be added unless it passes all gates.

### Gate A — decision relevance

Which user decision changes because of this feature?

### Gate B — evidence

Which source supports the fact or rule, and how is staleness handled?

### Gate C — materiality

How is the result normalized against transaction or company scale?

### Gate D — authority boundary

Is the output a fact, calculation, screening flag, inference, or institution-specific decision?

### Gate E — actionability

What concrete next action follows from the result?

### Gate F — validation

How can the result be tested against a fixture, expert review, or expected rule outcome?

Features failing any gate should remain out of the user-facing product.

## 11. Immediate implementation sequence

1. Freeze additional scenario and UI expansion.
2. Add typed trade-finance domain models without breaking existing case serialization.
3. Build one country and compliance fact registry for the reference countries.
4. Build a contract and L/C rule registry with traceable sources and synthetic test fixtures.
5. Normalize OpenDART financial statements and calculate transaction-to-capacity bridge metrics.
6. Build a versioned K-SURE and KB consultation-candidate registry.
7. Generate evidence-backed risk signals and an ordered action plan.
8. Only then reintroduce calibrated stress, report generation, and broader country coverage.

## 12. Product success criteria

The prototype is successful when a reviewer can answer yes to the following:

- Does the output identify a risk that a basic spreadsheet would miss?
- Does every material statement show its evidence, calculation, or limitation?
- Does the analysis distinguish buyer, country, document, company, and FX risk?
- Does transaction materiality connect to real company capacity?
- Does the system recommend a realistic sequence of mitigations rather than a generic warning?
- Does it avoid claiming bank approval, internal credit judgement, insurance acceptance, or live pricing?
- Can an SME use the result to improve a contract, prepare a K-SURE inquiry, or enter a KB consultation better prepared?

Until these criteria are met, additional agent, scenario, report, and UI features are secondary.