# Global Trade Copilot v2 Roadmap

## Product direction

The next version does not replace the existing deterministic trade-risk engines.
It turns them into governed read-only tools used by an evidence-grounded AI
copilot.

The target product is:

> A trade-finance copilot that combines reviewed trade documents, official public
> reference data, company financial context, and deterministic risk engines to
> plan and execute a traceable pre-consultation review.

The copilot may plan, select tools, identify missing information, compare
scenarios, connect findings, and prepare review questions. It may not invent
financial values, mutate the portfolio, issue an official credit rating, approve
a loan, determine product suitability, or represent a theoretical forward rate
as an executable KB quote.

## Architectural layers

1. **Evidence and case state**
   - reviewed document candidates and field-level provenance;
   - approved transactions only;
   - official-data observation and retrieval metadata;
   - explicit assumptions, missing fields, and document conflicts.

2. **Deterministic authority**
   - exposure;
   - natural offset and maturity matching;
   - settlement-timed cash flow;
   - delay and FX stress scenarios;
   - theoretical forward and hedge comparisons;
   - financial-health pre-screening context.

3. **Copilot intelligence**
   - objective classification;
   - capability-aware multi-step planning;
   - missing-input detection;
   - tool selection and dependency handling;
   - evidence-grounded synthesis;
   - consultation-question and brief generation.

4. **Governance**
   - human approval before transaction registration;
   - calculation-ID and document citations;
   - answer validation;
   - read-only AI tool boundary;
   - audit export of plan, inputs, assumptions, results, and limitations.

## Implementation phases

### Phase 1 — Planning contracts

Status: started.

- `CaseCapabilities`
- `AnalysisPlanStep`
- `CopilotAnalysisPlan`
- deterministic objective classification
- partial-plan behavior when inputs are missing
- sensitive-request rejection

The planner creates a reviewable execution plan. It does not execute financial
calculations.

### Phase 2 — Unified case model

Create one state contract containing:

- company identity and analysis date;
- documents and approval state;
- transactions and foreign-currency cash;
- official FX provenance;
- financial context;
- generated scenarios;
- deterministic results and citations;
- unresolved gaps and conflicts.

Existing pages should consume this contract rather than independently rebuilding
state.

### Phase 3 — Read-only tool expansion

Add governed tools for:

- document readiness and evidence coverage;
- cross-document conflict reporting;
- official-data readiness;
- financial-context retrieval;
- integrated consultation brief generation.

Every financial number must continue to originate from a deterministic result.

### Phase 4 — Scenario intelligence

The AI may propose structured scenario candidates from the reviewed case, for
example settlement delay, FX shock, import-cost increase, or combinations.
The deterministic scenario engine validates and executes the structured inputs.
The output must disclose why the scenario was selected and which assumptions
changed.

### Phase 5 — Integrated reasoning

Generate a cited risk chain rather than a generic score, for example:

`receivable delay -> maturity mismatch -> cash shortfall -> reduced financial buffer -> consultation priority`

The chain must distinguish computed facts, retrieved context, and interpretive
inference.

### Phase 6 — Copilot workspace

The primary UI should show:

1. user objective;
2. proposed analysis plan;
3. data readiness and blocked steps;
4. tool execution trace;
5. integrated risk findings;
6. scenario comparison;
7. consultation brief;
8. citations and audit export.

Standalone dashboards remain supporting views, not the primary product narrative.

## Required wording

Where applicable, surface the following statement:

> 현재 데모는 외부 생성형 AI가 연결되지 않은 결정론적 fallback 모드이며,
> 구조화 AI 공급자 연동 인터페이스는 구현되어 있다.

KEXIM data must be described as a public reference rate, not an executable KB
quote. Financial-health output must be described as `재무건전성 사전 스크리닝`,
not an official credit rating.
