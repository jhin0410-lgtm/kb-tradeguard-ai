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

Status: implemented foundation.

- `CaseCapabilities`
- `AnalysisPlanStep`
- `CopilotAnalysisPlan`
- deterministic objective classification
- partial-plan behavior when inputs are missing
- sensitive-request rejection

The planner creates a reviewable execution plan. It does not execute financial
calculations.

### Phase 2 — Unified case model

Status: implemented foundation.

`UnifiedCopilotCase` now provides one state contract containing:

- company identity and analysis date;
- approved and unresolved document evidence;
- approved transactions and foreign-currency cash;
- monthly cost assumptions;
- official FX provenance;
- financial and policy context;
- proposed or executed scenarios;
- deterministic results keyed by calculation ID;
- grounded findings;
- unresolved inputs;
- stable case hashing and compact audit summary;
- derived `CaseCapabilities` for the planner.

The case object is an orchestration boundary, not a replacement calculation
engine. Existing pages still need to be migrated to consume this contract rather
than independently rebuilding state.

### Phase 3 — Read-only tool expansion

Status: implemented foundation.

Implemented governed case-intelligence tools for:

- document readiness and evidence coverage;
- cross-document conflict reporting;
- information-gap derivation;
- consultation-question generation;
- integrated consultation brief generation.

Remaining integration work:

- expose the tools through the existing `ReadOnlyAdvisorTools` facade;
- add official-data and financial-context adapters;
- connect planner execution trace, UI, and audit export.

Every financial number must continue to originate from a deterministic result.

### Phase 4 — Scenario intelligence

Status: implemented foundation.

`copilot_scenarios` now provides:

- structured settlement-delay, FX-shock, import-cost, and combined-stress candidates;
- capability-aware `ready` or `blocked` status;
- disclosed parameter sources and limitations;
- stable scenario IDs bound to the case snapshot;
- explicit human approval before execution request creation;
- stale-case rejection;
- immutable attachment of proposed scenarios to `UnifiedCopilotCase`.

Scenario proposal does not calculate outcomes or assign occurrence probabilities.
The existing deterministic scenario engines must validate and execute each
approved request, then attach calculation IDs before a scenario can be marked
`executed`.

Remaining integration work:

- implement or adapt deterministic import-cost and combined-stress executors;
- route approved requests through the governed tool facade;
- persist execution traces and calculation citations in the case audit export;
- expose scenario approval and comparison in the Copilot workspace.

### Phase 5 — Integrated reasoning

Status: implemented foundation.

`copilot_reasoning` now provides:

- ordered risk chains generated from grounded case findings;
- explicit separation of document facts, calculated facts, scenario assumptions,
  contextual facts, inference, and consultation priority;
- calculation, evidence, scenario, and upstream-node references;
- validation that direct facts have source identifiers;
- validation that interpretive nodes depend only on earlier grounded nodes;
- stable chain and node IDs bound to the case snapshot;
- unresolved information gaps and authority limitations on every report.

The reasoning layer performs no financial arithmetic. It links existing facts and
marks interpretive statements as inference rather than presenting them as newly
computed facts.

Remaining integration work:

- derive richer multi-finding chains from executed scenario deltas;
- connect financial-context observations as separately cited context nodes;
- add chain-level answer validation and audit export;
- render the trace in the Copilot workspace.

### Phase 6 — Copilot workspace

Status: implemented foundation.

`copilot_workspace` now provides one client-neutral presentation contract with:

1. user objective and dependency-aware analysis plan;
2. data readiness and blocked-step disclosure;
3. structured scenario candidates and readiness state;
4. integrated risk chains;
5. consultation brief and questions;
6. calculation and document citation IDs;
7. a contiguous execution trace;
8. a stable workspace ID bound to objective and case snapshot;
9. a compact audit export with mandatory human-review status;
10. snapshot-consistency validation across scenarios and reasoning.

The workspace does not execute deterministic calculations or approve scenarios.
It composes existing governed outputs so Streamlit and future API clients can
render the same auditable state.

Remaining product integration work:

- add a Streamlit Copilot workspace renderer and make it the primary navigation view;
- construct `UnifiedCopilotCase` from current session, official-data, and calculation state;
- route approved scenario requests through deterministic executors;
- attach calculation results and findings back to the case;
- render before/after scenario comparisons and risk-chain citations;
- export the complete workspace audit JSON from the UI;
- run the full test suite and resolve any integration regressions.

Standalone dashboards remain supporting views, not the primary product narrative.

## Required wording

Where applicable, surface the following statement:

> 현재 데모는 외부 생성형 AI가 연결되지 않은 결정론적 fallback 모드이며,
> 구조화 AI 공급자 연동 인터페이스는 구현되어 있다.

KEXIM data must be described as a public reference rate, not an executable KB
quote. Financial-health output must be described as `재무건전성 사전 스크리닝`,
not an official credit rating.
