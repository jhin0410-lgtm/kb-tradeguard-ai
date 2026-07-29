# Governed FX-shock execution

The Copilot may propose a disclosed FX shock, but execution requires explicit human approval and is delegated to the existing deterministic hedge-ratio comparison engine.

## Contract

The current governed default is:

- currencies: approved transaction currencies only;
- shock: `-5%`, converted to deterministic engine input `-0.05`;
- analysis basis: `Expected transaction exposure`;
- hedge ratios: `0%, 30%, 50%, 70%, 100%`;
- tenor: 3 months;
- spread: 0.0 unless explicitly disclosed.

The contract is represented by `FXShockExecutionContract`. It validates currency scope, percentage units, hedge-ratio bounds, positive tenor, and non-negative spread before any financial tool is called.

## Execution flow

```text
ScenarioCandidate
→ explicit human approval
→ ScenarioExecutionRequest
→ FXShockExecutionContract
→ ReadOnlyAdvisorTools.compare_hedge_ratios
→ one CalculationResult per currency
→ UnifiedCopilotCase.calculations
→ executed CaseScenario with all Calculation IDs
```

The Copilot does not calculate the theoretical forward rate, scenario KRW values, protection, or opportunity cost. Those values remain authoritative only in the deterministic engine.

## Authority and limitations

- Public or disclosed FX references are simulation inputs, not executable KB quotations.
- Theoretical forward rates are not actual KB prices.
- Results are comparisons under disclosed assumptions, not product suitability decisions.
- The execution layer does not approve loans, transactions, hedge products, or customer eligibility.
- A scenario is not executed without explicit human approval.
