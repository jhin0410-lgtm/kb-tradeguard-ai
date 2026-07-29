from datetime import date, datetime, timezone

from src.copilot_case import CaseIdentity, UnifiedCopilotCase
from src.trade_finance_domain import (
    CompanyProfile,
    CounterpartyProfile,
    SourceReference,
    TradeFinanceDomainState,
)


def _source(source_id: str) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_name="Synthetic reviewed fixture",
        source_tier="user_provided",
        source_kind="user_document",
        as_of_date=date(2026, 7, 26),
        retrieved_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )


def test_existing_case_construction_remains_valid_with_empty_domain_state():
    case = UnifiedCopilotCase(identity=CaseIdentity(case_id="CASE-LEGACY"))

    assert case.case_version == "copilot-case/1.1"
    assert case.trade_finance.domain_version == "trade-finance-domain/1.0"
    assert all(value == 0 for value in case.trade_finance.record_counts().values())


def test_typed_domain_state_is_included_in_hash_and_audit_summary():
    base = UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-001",
            company_name="한빛테크",
            analysis_as_of_date=date(2026, 7, 26),
        )
    )
    domain = TradeFinanceDomainState(
        company_profile=CompanyProfile(
            company_id="COMP-001",
            legal_name="한빛테크",
            source=_source("SRC-COMPANY"),
            record_status="verified",
        ),
        counterparties=[
            CounterpartyProfile(
                counterparty_id="BUYER-001",
                legal_name="Example Buyer Co.",
                country_code="VN",
                relationship_status="new",
                source=_source("SRC-BUYER"),
                record_status="partial",
            )
        ],
    )
    enriched = base.model_copy(update={"trade_finance": domain})
    summary = enriched.audit_summary()

    assert base.case_hash != enriched.case_hash
    assert summary["trade_finance_domain_version"] == "trade-finance-domain/1.0"
    assert summary["trade_finance_record_counts"]["counterparties"] == 1
    assert enriched.canonical_snapshot()["trade_finance"]["company_profile"]["company_id"] == "COMP-001"
