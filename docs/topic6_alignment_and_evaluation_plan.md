# Topic 6 alignment and evaluation plan

## Target problem

The project targets the competition topic `수출입 금융 지원 에이전트`.

The product must connect five decision surfaces rather than operate as a generic chatbot:

1. foreign-exchange exposure and reference-rate context;
2. country macroeconomic and trade-statistics context;
3. contract, invoice, purchase-order, and L/C review;
4. trade-finance, guarantee, insurance, policy-fund, and FX-product consultation candidates;
5. an evidence-linked action plan for an SME or sole proprietor.

The operating unit remains:

```text
company × transaction × buyer/supplier × country × contract/payment terms
```

## Current coverage matrix

| Topic-6 requirement | Current implementation | Current evidence boundary |
|---|---|---|
| Exchange rates | KEXIM official reference-rate adapter, FX normalization, transaction exposure and scenario calculations | Public reference rate, not an executable KB quote |
| Trade statistics | Korea Customs Service country-by-HS-code aggregate API adapter | Aggregate country/product statistics, not company declarations |
| Country indicators | World Bank GDP growth, CPI, reserves/imports, and current-account indicators | Latest non-null observation; indicator years may differ |
| Domestic company identity | NTS business-registration status and authenticity adapter | Identity/operating status only; not trade statistics or credit assessment |
| Corporate financials | OpenDART company and financial-statement adapters | Public filings; not an internal bank credit view |
| Contract and L/C risk | Versioned deterministic screening and reconciliation rules | Reviewed structured fields; not autonomous legal interpretation |
| Trade-finance products | Reviewed registry covering K-SURE services, insurance, guarantees, import support, FX fluctuation insurance, and a KB export-company loan consultation route | Consultation candidates only; no eligibility, pricing, limit, approval, or suitability conclusion |
| Explainability and audit | Evidence IDs, calculation IDs, source dates, hashes, Action Plan, Markdown/JSON/ZIP exports | Change tracking and provenance, not a guarantee of correctness |
| Generative AI | Optional grounded explanation layer and a governed role boundary | OFF in the public demo; deterministic outputs remain authoritative |

## National Tax Service versus trade statistics

The National Tax Service API is not a customs-statistics source.

```text
NTS
  -> Korean business registration identity/status

Korea Customs Service
  -> country/HS-code aggregate exports, imports, weights, and trade balance
```

The two providers must stay separate in the domain model and user interface. A continuing-business result must never be interpreted as proof of export performance, buyer quality, transaction safety, or financing eligibility.

## Product recommendation meaning

The product layer is a governed consultation matcher, not a recommender that predicts approval.

Inputs include:

- transaction direction and stage;
- declared financing or risk-management need;
- payment method and tenor;
- company size and industry context;
- preferred banking channel;
- documents currently available.

Outputs are limited to these statuses:

```text
consultation_candidate
insufficient_information
not_applicable
blocked
```

Every candidate must show:

- institution and product/service name;
- matched need;
- public conditions already verified;
- unresolved conditions and missing documents;
- official source IDs and effective date;
- the next consultation action.

## AI responsibility model

```text
AI assist
  -> propose structured fields from unstructured documents
  -> explain completed deterministic results with citations
  -> summarize missing information and consultation questions

Deterministic engine
  -> normalize payment terms
  -> calculate exposure and liquidity comparisons
  -> detect document mismatches and governed rule triggers
  -> match reviewed public product conditions
  -> build final status and action dependencies

Human review
  -> approve extracted fields
  -> inspect original documents
  -> verify current official terms
  -> make transaction, legal, credit, insurance, pricing, and suitability decisions
```

The next AI milestone is not a free-form chatbot. It is a measured extraction task with a reviewed schema and an abstention path for uncertain fields.

## Evaluation layers

### Layer 1: deterministic regression

Current internal evidence:

- 30 project-authored reviewed structured fixtures;
- positive and negative controls;
- exact expected Rule-ID sets;
- 150 meaning-preserving mutations;
- full governed-rule registry coverage.

Report exact-set match, micro precision, recall, false-positive Rule IDs, and false-negative Rule IDs. Label all values as an internal synthetic regression benchmark.

### Layer 2: independent document extraction benchmark

Required before claiming AI document accuracy:

- documents not used to design the extraction prompt or schema;
- at least contract, invoice, purchase order, sight L/C, usance L/C, and acceptance L/C groups;
- field-level precision, recall, and exact match;
- document-level abstention and missing-field rates;
- separate results by document type and language;
- reviewer disagreement log and adjudication rule.

No metric from Layer 1 may be presented as Layer-2 extraction accuracy.

### Layer 3: decision usefulness

Required for business validation:

- manual review time versus assisted review time;
- high-impact risk items found and missed;
- false alarms requiring reviewer dismissal;
- completeness of consultation documents;
- whether the recommended consultation route was relevant after expert review.

This layer requires trade-finance or export-support practitioner review. It must not use fabricated customer outcomes.

## Real-data delivery order

1. Display live no-key World Bank country indicators in the competition app.
2. Configure KEXIM and Korea Customs Service keys in the deployment secret store.
3. Save dated, hashed provider snapshots for reproducible submissions.
4. Add HS-code concentration, trade growth, and balance calculations as a versioned context module.
5. Add explicit hedge comparison inputs: currency, amount, settlement date, existing foreign-currency balances, and existing hedges.
6. Compare consultation alternatives such as no hedge, staged forward consultation, and FX fluctuation insurance without claiming executable pricing or suitability.
7. Expand the reviewed product registry with current KB trade-finance and FX products only after official terms are rechecked and dated.

## Submission wording

Use:

> 공식 환율·국가경제·무역통계와 검토된 거래자료를 결합해 환노출, 문서위험, 자금부담과 금융·보험·보증 상담 후보를 근거 기반으로 제시한다.

Do not use:

> AI가 최적 상품을 자동 추천하고 대출 가능성을 판정한다.

The prototype prepares a traceable consultation package. It does not replace a financial institution's current product explanation, suitability review, credit decision, pricing, guarantee issuance, or insurance underwriting.
