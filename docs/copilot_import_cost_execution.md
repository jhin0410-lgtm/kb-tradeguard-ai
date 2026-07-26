# Governed Import-Cost Stress Execution

## Purpose

The import-cost scenario tests how a disclosed increase in approved import payment
amounts changes deterministic monthly cash flow and liquidity shortfalls. It is a
stress test, not a price forecast.

## Execution contract

The default proposal uses:

- targeted transactions: all approved import transactions;
- increase assumption: 10 percent;
- cash-flow view: expected;
- dates, currencies, status, and probabilities: unchanged;
- FX input: the case's public or disclosed reference table.

The human-readable percentage is converted to a multiplier only inside the governed
execution contract. A 10 percent stress therefore applies a multiplier of 1.10 to
the approved target amounts.

## Controlled flow

```text
ScenarioCandidate
-> explicit human approval
-> ScenarioExecutionRequest
-> ImportCostExecutionContract validation
-> copied transaction table
-> deterministic monthly cash-flow engine
-> CalculationResult
-> UnifiedCopilotCase calculation attachment
-> executed CaseScenario with Calculation ID
```

The original case and approved transactions are not mutated.

## Validation

Execution is rejected when:

- no target transaction is supplied;
- a target ID is absent from the approved portfolio;
- any target is not an import transaction;
- the increase is negative;
- current cash or monthly fixed-cost assumptions are absent;
- the FX reference contains no usable spot rate.

## Output

The result contains:

- baseline monthly cash flow;
- stressed monthly cash flow;
- changed months and incremental import outflow;
- baseline and stressed maximum cash shortfalls;
- deterministic Calculation ID and engine metadata.

## Authority boundary

The Copilot proposes and routes the scenario but performs no financial arithmetic.
Cash-flow arithmetic remains in the deterministic engine. The 10 percent increase
is a disclosed stress assumption, not an occurrence probability or forecast. Public
or disclosed FX inputs are reference values and are not executable KB quotes. The
output is not a loan approval, product-suitability determination, or official credit
rating.
