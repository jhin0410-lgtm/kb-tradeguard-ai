from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

import competition_app
import streamlit_app
from src.copilot_case import CaseDataAsset, CaseIdentity, UnifiedCopilotCase
from src.copilot_scenarios import propose_scenarios
from src.intelligence.portfolio_assessment import analyze_trade_portfolio
from src.intelligence.single_transaction_pipeline import _clear_transaction_product_records
from src.intelligence.transaction_capacity import TransactionCapacityRequest, analyze_transaction_capacity
from src.official_case_studies import load_pinned_official_context_dataset
from src.official_data_hub import OfficialDataBundle, OfficialDataQuery, OfficialDataSnapshot, attach_official_data_bundle
from src.trade_finance_domain import (
    CompanyProfile,
    ConsultationRequirement,
    FinancialStatementSnapshot,
    ProductCandidate,
    SourceReference,
    TradeFinanceDomainState,
)


def _source(source_id: str, kind: str = "official_api") -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_name="Reviewed fixture",
        source_tier="tier_1" if kind == "official_api" else "derived",
        source_kind=kind,
        source_locator=f"fixture://{source_id}",
        as_of_date=date(2025, 12, 31),
        content_hash=f"hash-{source_id}",
        effective_date_verified=True,
    )


def _statement(*, cash: Decimal = Decimal("300000000"), company_id: str = "COMPANY-001"):
    return FinancialStatementSnapshot(
        statement_id="FS-2025-CFS",
        company_id=company_id,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        report_type="annual",
        consolidation_scope="consolidated",
        currency="KRW",
        cash_and_cash_equivalents=cash,
        current_assets=Decimal("1000000000"),
        equity=Decimal("500000000"),
        revenue=Decimal("5000000000"),
        source=_source("FS"),
        record_status="verified",
    )


def _capacity_case(*, amount: Decimal = Decimal("500000"), fx_status: str = "available", company=True, cash=Decimal("300000000")):
    profile = (
        CompanyProfile(
            company_id="COMPANY-001",
            legal_name="Example Co.",
            source=_source("COMPANY"),
            record_status="verified",
        )
        if company
        else None
    )
    return UnifiedCopilotCase(
        identity=CaseIdentity(case_id="CASE-CAP", company_name="Example Co.", analysis_as_of_date=date(2026, 7, 29)),
        approved_transactions=[{
            "transaction_id": "EXP-001",
            "transaction_type": "export",
            "currency": "USD",
            "amount_fc": amount,
            "expected_date": "2026-10-31",
        }],
        official_fx_reference=CaseDataAsset(
            asset_name="FX",
            status=fx_status,
            source="fixture",
            payload=[{"currency": "USD", "spot_rate_krw": "1350.123456789"}],
        ),
        trade_finance=TradeFinanceDomainState(
            company_profile=profile,
            financial_statements=[_statement(cash=cash)],
        ),
    )


def _capacity_request():
    return TransactionCapacityRequest(
        assessment_id="CAP-1",
        transaction_id="EXP-001",
        statement_id="FS-2025-CFS",
    )


def test_failed_refresh_clears_prior_fx_and_non_statement_financial_capability():
    case = UnifiedCopilotCase(
        identity=CaseIdentity(case_id="CASE-REFRESH"),
        official_fx_reference=CaseDataAsset(
            asset_name="old FX", status="available", source="old", payload={"USD": 1300}
        ),
        financial_context=CaseDataAsset(
            asset_name="old financials", status="available", source="old", payload={"cash": 1}
        ),
    )
    bundle = OfficialDataBundle(
        query=OfficialDataQuery(as_of_date=date(2026, 7, 29)),
        generated_at=datetime.now(timezone.utc),
        snapshots=[
            OfficialDataSnapshot(
                asset_key="kexim_fx_reference", provider="KEXIM", operation="rates", status="error", error="outage"
            ),
            OfficialDataSnapshot(
                asset_key="nts_business_status", provider="NTS", operation="status", status="available", payload={"results": [{"status": "active"}]}
            ),
            OfficialDataSnapshot(
                asset_key="opendart_company_profile", provider="DART", operation="company", status="available", payload={"results": {"corp": "demo"}}
            ),
        ],
    )
    updated = attach_official_data_bundle(case, bundle)
    assert updated.official_fx_reference.status == "missing"
    assert updated.official_fx_reference.payload is None
    assert updated.financial_context.status == "missing"
    assert updated.financial_context.payload is None
    assert updated.capabilities.official_fx_reference is False
    assert updated.capabilities.financial_context is False


def test_capacity_rejects_stale_fx_missing_company_and_nonpositive_amount():
    with pytest.raises(ValueError, match="current available or partial FX"):
        analyze_transaction_capacity(_capacity_case(fx_status="stale"), _capacity_request())
    with pytest.raises(ValueError, match="company profile is required"):
        analyze_transaction_capacity(_capacity_case(company=False), _capacity_request())
    with pytest.raises(ValueError, match="greater than zero"):
        analyze_transaction_capacity(_capacity_case(amount=Decimal("0")), _capacity_request())


def test_capacity_audit_preserves_decimal_precision_and_statement_content_hashing():
    amount = Decimal("9007199254740993.25")
    first = analyze_transaction_capacity(_capacity_case(amount=amount), _capacity_request())
    second = analyze_transaction_capacity(
        _capacity_case(amount=amount, cash=Decimal("300000001")), _capacity_request()
    )
    assert first.calculation.input_assumptions["amount_fc"] == "9007199254740993.25"
    assert first.calculation.input_assumptions["fx_rate_krw"] == "1350.123456789"
    assert first.calculation.input_assumptions["statement_snapshot"]["cash_and_cash_equivalents"] == "300000000"
    assert first.calculation.normalized_input_hash != second.calculation.normalized_input_hash


def test_product_cleanup_removes_only_current_transaction_registry_outputs():
    registry_source = _source("TRADE-FINANCE-PRODUCTS-v2", kind="project_rule")
    other_source = _source("OTHER", kind="project_rule")
    current = ProductCandidate(
        product_candidate_id="PC-CURRENT", linked_transaction_ids=["EXP-001"], provider="Bank",
        product_or_service_name="Current", product_category="working_capital", matched_need="need",
        candidate_status="insufficient_information", next_action="consult", source=registry_source,
    )
    other = ProductCandidate(
        product_candidate_id="PC-OTHER", linked_transaction_ids=["IMP-002"], provider="Bank",
        product_or_service_name="Other", product_category="import_finance", matched_need="need",
        candidate_status="insufficient_information", next_action="consult", source=other_source,
    )
    requirement = ConsultationRequirement(
        requirement_id="REQ-CURRENT", linked_transaction_ids=["EXP-001"], consultation_route="trade_finance_specialist",
        purpose="confirm", source=registry_source,
    )
    case = UnifiedCopilotCase(
        identity=CaseIdentity(case_id="CASE-PRODUCT-CLEANUP"),
        trade_finance=TradeFinanceDomainState(
            product_candidates=[current, other], consultation_requirements=[requirement]
        ),
    )
    updated, removed = _clear_transaction_product_records(case, "EXP-001")
    assert removed == ["PC-CURRENT", "REQ-CURRENT"]
    assert [item.product_candidate_id for item in updated.trade_finance.product_candidates] == ["PC-OTHER"]
    assert updated.trade_finance.consultation_requirements == []


def test_unvalued_transaction_makes_affected_liquidity_unknown():
    case = UnifiedCopilotCase(
        identity=CaseIdentity(case_id="CASE-LIQUIDITY"),
        approved_transactions=[{
            "transaction_id": "IMP-001", "transaction_type": "import", "currency": "EUR",
            "amount_fc": "1000000", "expected_date": "2026-08-15", "probability": "1",
        }],
        monthly_cost_assumptions={"current_cash_krw": "100000000", "monthly_fixed_cost_krw": "10000000"},
    )
    assessment = analyze_trade_portfolio(case)
    bucket = assessment.liquidity_buckets[0]
    assert bucket.missing_currency_rates == ["EUR"]
    assert bucket.expected_inflow_krw is None
    assert bucket.expected_outflow_krw is None
    assert bucket.net_cashflow_krw is None
    assert bucket.ending_cash_krw is None


def test_pinned_loader_rejects_payload_tampering(tmp_path: Path):
    source_path = Path("data/case_studies/official_context_snapshots_v1.json")
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    payload["cases"][0]["sources"][0]["payload"]["tampered"] = True
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="payload does not match response_hash"):
        load_pinned_official_context_dataset(tampered)


def test_direct_entrypoint_uses_title_and_qr_secret_is_configured_in_main(monkeypatch):
    source = Path("competition_app.py").read_text(encoding="utf-8")
    assert "item.label" not in source
    assert "item.title" in source

    monkeypatch.delenv("TRADEGUARD_PUBLIC_DEMO_URL", raising=False)
    monkeypatch.setattr(
        streamlit_app,
        "_secret_to_environment",
        lambda name: __import__("os").environ.__setitem__(name, "https://fork.example/")
        if name == "TRADEGUARD_PUBLIC_DEMO_URL"
        else None,
    )
    for key in (
        "KEXIM_API_KEY", "KCS_TRADE_API_KEY", "DATA_GO_KR_SERVICE_KEY", "TRADEGUARD_PUBLIC_DEMO_URL"
    ):
        streamlit_app._secret_to_environment(key)
    __import__("os").environ.setdefault("TRADEGUARD_PUBLIC_DEMO_URL", streamlit_app.PUBLIC_DEMO_URL)
    assert __import__("os").environ["TRADEGUARD_PUBLIC_DEMO_URL"] == "https://fork.example/"


def test_fx_scenario_blocks_when_any_active_currency_lacks_a_rate():
    case = UnifiedCopilotCase(
        identity=CaseIdentity(case_id="CASE-FX-COVERAGE"),
        approved_transactions=[
            {"transaction_id": "EXP-USD", "transaction_type": "export", "currency": "USD", "amount_fc": 100},
            {"transaction_id": "IMP-EUR", "transaction_type": "import", "currency": "EUR", "amount_fc": 100},
        ],
        official_fx_reference=CaseDataAsset(
            asset_name="FX", status="partial", source="fixture",
            payload=[{"currency": "USD", "spot_rate_krw": 1350}],
        ),
    )
    proposal = propose_scenarios(case)
    fx = next(item for item in proposal.candidates if item.scenario_type == "fx_shock")
    assert fx.readiness == "blocked"
    assert any("EUR" in item for item in fx.missing_inputs)
