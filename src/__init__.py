"""Deterministic financial analysis engine for KB TradeGuard."""

from .advisor_models import AdvisoryAnswer, CalculationResult, IntentClassification
from .advisor_orchestrator import (
    AdvisorOrchestrator,
    ConfiguredStructuredAdvisor,
    DeterministicOfflineAdvisor,
)
from .advisor_tools import ReadOnlyAdvisorTools
from .answer_validation import AnswerValidationReport, validate_advisory_answer
from .cash_allocation import CashAllocationResult, allocate_foreign_cash
from .cashflow import CASH_FLOW_VIEWS, calculate_monthly_cashflow
from .citation_models import CalculationCitation, DocumentCitation
from .document_models import ExtractedTradeDocument, FieldProvenance, ReviewQueueItem
from .exposure import ExposureResult, calculate_exposure
from .forward_rates import (
    build_settlement_forward_table,
    calculate_theoretical_forward_rate,
    calculate_theoretical_forward_rate_for_years,
)
from .hedging import (
    DEFAULT_HEDGE_ANALYSIS_BASIS,
    NaturalHedgeResult,
    calculate_natural_hedge,
    compare_hedge_ratios,
    select_hedge_analysis_basis,
)
from .maturity_buckets import (
    MaturityBucketResult,
    assign_maturity_bucket,
    build_maturity_bucket_exposure,
)
from .portfolio_hedging import (
    PortfolioHedgeResult,
    calculate_maturity_bucket_portfolio_hedge,
    calculate_transaction_level_portfolio_hedge,
)
from .policy_retrieval import BundledPolicyRetriever, PolicyExcerpt
from .scenarios import calculate_scenarios
from .validators import validate_fx_rates, validate_transactions

__all__ = [
    "ExposureResult",
    "AdvisoryAnswer",
    "AdvisorOrchestrator",
    "AnswerValidationReport",
    "BundledPolicyRetriever",
    "CASH_FLOW_VIEWS",
    "CalculationCitation",
    "CalculationResult",
    "CashAllocationResult",
    "ConfiguredStructuredAdvisor",
    "DEFAULT_HEDGE_ANALYSIS_BASIS",
    "DeterministicOfflineAdvisor",
    "DocumentCitation",
    "ExtractedTradeDocument",
    "FieldProvenance",
    "IntentClassification",
    "MaturityBucketResult",
    "NaturalHedgeResult",
    "PortfolioHedgeResult",
    "PolicyExcerpt",
    "ReadOnlyAdvisorTools",
    "ReviewQueueItem",
    "allocate_foreign_cash",
    "assign_maturity_bucket",
    "build_maturity_bucket_exposure",
    "build_settlement_forward_table",
    "calculate_exposure",
    "calculate_monthly_cashflow",
    "calculate_maturity_bucket_portfolio_hedge",
    "calculate_natural_hedge",
    "calculate_scenarios",
    "calculate_theoretical_forward_rate",
    "calculate_theoretical_forward_rate_for_years",
    "calculate_transaction_level_portfolio_hedge",
    "compare_hedge_ratios",
    "select_hedge_analysis_basis",
    "validate_fx_rates",
    "validate_advisory_answer",
    "validate_transactions",
]
