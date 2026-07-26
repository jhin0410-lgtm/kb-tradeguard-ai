# Governed Copilot Scenario Execution

The Copilot scenario layer proposes and explains stress candidates. It does not
perform financial arithmetic. Approved candidates cross into the deterministic
engine only through `GovernedScenarioExecutor`.

## Implemented execution path

`settlement_delay` is currently supported end to end:

1. `propose_scenarios` creates a disclosed 30-day delay candidate;
2. a human explicitly approves execution;
3. `build_execution_request` validates readiness and approval;
4. `GovernedScenarioExecutor` calls
   `ReadOnlyAdvisorTools.run_cashflow_delay_scenario`;
5. the returned `CalculationResult` is attached to `UnifiedCopilotCase`;
6. the matching `CaseScenario` is marked `executed` and cites the deterministic
   calculation ID;
7. the outcome records before and after case hashes.

The original case remains unchanged. The returned case is a new snapshot.

## Unsupported routes

`fx_shock`, `import_cost_increase`, and `combined_stress` remain proposed or
approved only until a semantically exact deterministic executor is registered.
They raise `NotImplementedError` rather than silently substituting another tool or
inventing arithmetic.

## Authority boundary

- financial arithmetic remains in deterministic engines;
- human approval is mandatory;
- an executed scenario must cite at least one calculation ID;
- public or disclosed FX references are not executable KB quotes;
- outputs are simulations for consultation preparation, not loan approval,
  suitability determination, or an official credit rating.
