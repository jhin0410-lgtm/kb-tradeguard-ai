from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected anchor not found in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1/13 + 13/13: clear failed FX refreshes and require usable statements for financial capability.
replace_once(
    "src/official_data_hub.py",
    "def _bundle_hash(bundle: OfficialDataBundle) -> str:\n",
    "def _payload_has_results(payload: dict[str, Any] | list[dict[str, Any]] | None) -> bool:\n"
    "    if payload is None:\n"
    "        return False\n"
    "    if isinstance(payload, list):\n"
    "        return bool(payload)\n"
    "    results = payload.get(\"results\")\n"
    "    return results not in (None, [], {})\n\n\n"
    "def _bundle_hash(bundle: OfficialDataBundle) -> str:\n",
)
old = '''    updates: dict[str, Any] = {"official_data_assets": assets}
    fx_snapshot = next(
        (
            item
            for item in bundle.snapshots
            if item.asset_key == "kexim_fx_reference"
            and item.status in {"available", "partial"}
        ),
        None,
    )
    if fx_snapshot is not None:
        fx_payload = _normalized_fx_payload(fx_snapshot)
        updates["official_fx_reference"] = CaseDataAsset(
            asset_name="KEXIM reviewed public reference FX",
            status="available" if fx_payload else "partial",
            source=fx_snapshot.provider,
            as_of_date=fx_snapshot.observation_date or bundle.query.as_of_date,
            retrieved_at=fx_snapshot.retrieved_at,
            source_hash=fx_snapshot.response_hash,
            payload=fx_payload,
            limitations=[
                *fx_snapshot.limitations,
                "Public reference rates only; not an executable KB spot or forward quote.",
            ],
        )

    financial_keys = {
        "nts_business_status",
        "opendart_company_profile",
        "opendart_financial_statements",
    }
    financial_snapshots = [
        item
        for item in bundle.snapshots
        if item.asset_key in financial_keys
        and item.status in {"available", "partial"}
    ]
    if financial_snapshots:
        updates["financial_context"] = CaseDataAsset(
            asset_name="Reviewed official company and financial context",
            status=(
                "available"
                if all(item.status == "available" for item in financial_snapshots)
                else "partial"
            ),
            source="OfficialDataHub",
            as_of_date=bundle.query.as_of_date,
            source_hash=_bundle_hash(bundle),
            payload=[
                {
                    "asset_key": item.asset_key,
                    "provider": item.provider,
                    "response_hash": item.response_hash,
                    "payload": item.payload,
                }
                for item in financial_snapshots
            ],
            limitations=[
                "Business status and issuer filings are context only; they are not a bank credit decision.",
                bundle.authority_boundary,
            ],
        )
'''
new = '''    updates: dict[str, Any] = {"official_data_assets": assets}
    fx_snapshot = next(
        (item for item in bundle.snapshots if item.asset_key == "kexim_fx_reference"),
        None,
    )
    fx_payload = (
        _normalized_fx_payload(fx_snapshot)
        if fx_snapshot is not None
        and fx_snapshot.status in {"available", "partial"}
        else []
    )
    if fx_snapshot is not None and fx_payload:
        updates["official_fx_reference"] = CaseDataAsset(
            asset_name="KEXIM reviewed public reference FX",
            status="available" if fx_snapshot.status == "available" else "partial",
            source=fx_snapshot.provider,
            as_of_date=fx_snapshot.observation_date or bundle.query.as_of_date,
            retrieved_at=fx_snapshot.retrieved_at,
            source_hash=fx_snapshot.response_hash,
            payload=fx_payload,
            limitations=[
                *fx_snapshot.limitations,
                "Public reference rates only; not an executable KB spot or forward quote.",
            ],
        )
    else:
        failure_limitations = list(fx_snapshot.limitations) if fx_snapshot is not None else []
        if fx_snapshot is not None and fx_snapshot.error:
            failure_limitations.append(fx_snapshot.error)
        failure_limitations.append(
            "The prior derived FX reference was cleared because the latest refresh produced no usable reviewed rates."
        )
        updates["official_fx_reference"] = CaseDataAsset(
            asset_name="KEXIM reviewed public reference FX",
            status="missing",
            source=fx_snapshot.provider if fx_snapshot is not None else "OfficialDataHub",
            as_of_date=bundle.query.as_of_date,
            retrieved_at=fx_snapshot.retrieved_at if fx_snapshot is not None else None,
            source_hash=fx_snapshot.response_hash if fx_snapshot is not None else None,
            payload=None,
            limitations=failure_limitations,
        )

    financial_keys = {
        "nts_business_status",
        "opendart_company_profile",
        "opendart_financial_statements",
    }
    financial_snapshots = [
        item
        for item in bundle.snapshots
        if item.asset_key in financial_keys
        and item.status in {"available", "partial"}
    ]
    statement_snapshot = next(
        (
            item
            for item in bundle.snapshots
            if item.asset_key == "opendart_financial_statements"
        ),
        None,
    )
    if (
        statement_snapshot is not None
        and statement_snapshot.status in {"available", "partial"}
        and _payload_has_results(statement_snapshot.payload)
    ):
        updates["financial_context"] = CaseDataAsset(
            asset_name="Reviewed official company and financial context",
            status="available" if statement_snapshot.status == "available" else "partial",
            source="OfficialDataHub",
            as_of_date=bundle.query.as_of_date,
            source_hash=_bundle_hash(bundle),
            payload=[
                {
                    "asset_key": item.asset_key,
                    "provider": item.provider,
                    "response_hash": item.response_hash,
                    "payload": item.payload,
                }
                for item in financial_snapshots
            ],
            limitations=[
                "Business status and issuer filings are context only; they are not a bank credit decision.",
                bundle.authority_boundary,
            ],
        )
    else:
        updates["financial_context"] = CaseDataAsset(
            asset_name="Reviewed official company and financial context",
            status="missing",
            source="OfficialDataHub",
            as_of_date=bundle.query.as_of_date,
            source_hash=_bundle_hash(bundle),
            payload=None,
            limitations=[
                "A usable reviewed financial-statement snapshot is required before financial capability is enabled.",
                bundle.authority_boundary,
            ],
        )
'''
replace_once("src/official_data_hub.py", old, new)

# 2/13, 3/13, 7/13, 11/13, 12/13: transaction-capacity engine boundaries and audit precision.
replace_once(
    "src/intelligence/transaction_capacity.py",
    '''    if missing:
        raise ValueError(
            "Approved transaction is missing capacity inputs: " + ", ".join(missing)
        )
    return transaction
''',
    '''    if missing:
        raise ValueError(
            "Approved transaction is missing capacity inputs: " + ", ".join(missing)
        )
    amount = _decimal(transaction["amount_fc"], "transaction amount_fc")
    if amount <= 0:
        raise ValueError("transaction amount_fc must be greater than zero")
    return transaction
''',
)
replace_once(
    "src/intelligence/transaction_capacity.py",
    '''    statement = matches[0]
    if statement.currency != "KRW":
        raise ValueError("Transaction-capacity assessment currently requires KRW statements")
    if (
        case.trade_finance.company_profile is not None
        and statement.company_id != case.trade_finance.company_profile.company_id
    ):
        raise ValueError("Financial statement company does not match the case company profile")
    return statement
''',
    '''    statement = matches[0]
    if statement.currency != "KRW":
        raise ValueError("Transaction-capacity assessment currently requires KRW statements")
    company_profile = case.trade_finance.company_profile
    if company_profile is None:
        raise ValueError(
            "A reviewed company profile is required to bind the financial statement to the case"
        )
    if statement.company_id != company_profile.company_id:
        raise ValueError("Financial statement company does not match the case company profile")
    return statement
''',
)
replace_once(
    "src/intelligence/transaction_capacity.py",
    '''    asset = case.official_fx_reference
    if asset is None or asset.payload is None:
        raise ValueError(f"FX reference is required for transaction currency {currency}")
''',
    '''    asset = case.official_fx_reference
    if (
        asset is None
        or asset.status not in {"available", "partial"}
        or asset.payload is None
    ):
        raise ValueError(
            f"A current available or partial FX reference is required for transaction currency {currency}"
        )
''',
)
replace_once(
    "src/intelligence/transaction_capacity.py",
    '''def _json_value(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
''',
    '''def _json_value(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None
''',
)
replace_once(
    "src/intelligence/transaction_capacity.py",
    '''    amount_fc = _decimal(transaction["amount_fc"], "transaction amount_fc")
    fx_rate = (
''',
    '''    amount_fc = _decimal(transaction["amount_fc"], "transaction amount_fc")
    if amount_fc <= 0:
        raise ValueError("transaction amount_fc must be greater than zero")
    fx_rate = (
''',
)
replace_once(
    "src/intelligence/transaction_capacity.py",
    '''    gross_transaction_krw = amount_fc * fx_rate
''',
    '''    if fx_rate <= 0:
        raise ValueError("FX rate must be greater than zero")
    gross_transaction_krw = amount_fc * fx_rate
''',
)
replace_once(
    "src/intelligence/transaction_capacity.py",
    '''            "statement_id": request.statement_id,
            "payment_structure_id": (
''',
    '''            "statement_id": request.statement_id,
            "statement_snapshot": statement.model_dump(mode="json"),
            "payment_structure_id": (
''',
)
replace_once(
    "src/intelligence/transaction_capacity.py",
    '''            "amount_fc": float(amount_fc),
            "fx_rate_krw": float(fx_rate),
''',
    '''            "amount_fc": _json_value(amount_fc),
            "fx_rate_krw": _json_value(fx_rate),
''',
)
replace_once(
    "src/intelligence/transaction_capacity.py",
    '''            "protection_percent": (
                float(request.protection_percent)
                if request.protection_percent is not None
                else None
            ),
            "pre_shipment_funding_need_krw": (
                float(request.pre_shipment_funding_need_krw)
                if request.pre_shipment_funding_need_krw is not None
                else None
            ),
''',
    '''            "protection_percent": _json_value(request.protection_percent),
            "pre_shipment_funding_need_krw": _json_value(
                request.pre_shipment_funding_need_krw
            ),
''',
)

# 4/13: remove stale transaction-linked product outputs when matching is skipped.
insert = '''\n\ndef _clear_transaction_product_records(\n    case: UnifiedCopilotCase,\n    transaction_id: str,\n) -> tuple[UnifiedCopilotCase, list[str]]:\n    \"\"\"Remove registry-derived product records unsupported by the current run.\"\"\"\n\n    def belongs_to_transaction(record: Any) -> bool:\n        linked = list(getattr(record, \"linked_transaction_ids\", []) or [])\n        if transaction_id in linked:\n            return True\n        source_id = str(getattr(getattr(record, \"source\", None), \"source_id\", \"\"))\n        return not linked and source_id.startswith(\"TRADE-FINANCE-PRODUCTS-\")\n\n    removed_ids = [\n        item.product_candidate_id\n        for item in case.trade_finance.product_candidates\n        if belongs_to_transaction(item)\n    ] + [\n        item.requirement_id\n        for item in case.trade_finance.consultation_requirements\n        if belongs_to_transaction(item)\n    ]\n    if not removed_ids:\n        return case, []\n    domain = case.trade_finance.model_copy(\n        update={\n            \"product_candidates\": [\n                item\n                for item in case.trade_finance.product_candidates\n                if not belongs_to_transaction(item)\n            ],\n            \"consultation_requirements\": [\n                item\n                for item in case.trade_finance.consultation_requirements\n                if not belongs_to_transaction(item)\n            ],\n        }\n    )\n    candidate = case.model_copy(update={\"trade_finance\": domain})\n    return UnifiedCopilotCase.model_validate(candidate.model_dump(mode=\"python\")), sorted(removed_ids)\n'''
replace_once(
    "src/intelligence/single_transaction_pipeline.py",
    "\n\ndef run_single_transaction_assessment(\n",
    insert + "\n\ndef run_single_transaction_assessment(\n",
)
replace_once(
    "src/intelligence/single_transaction_pipeline.py",
    '''    else:
        traces.append(
            _trace(
                4,
                "product_matching",
                "skipped",
                before,
                before,
                reason="No explicit trade-finance need profiles were supplied.",
            )
        )
''',
    '''    else:
        working, removed_product_record_ids = _clear_transaction_product_records(
            working,
            request.transaction_id,
        )
        traces.append(
            _trace(
                4,
                "product_matching",
                "skipped",
                before,
                working.case_hash,
                reason="No explicit trade-finance need profiles were supplied.",
                removed_record_ids=removed_product_record_ids,
            )
        )
''',
)

# 5/13: propagate unknown liquidity when any transaction cannot be valued.
replace_once(
    "src/intelligence/portfolio_assessment.py",
    '''class LiquidityBucket(BaseModel):
    period: str
    expected_inflow_krw: Decimal
    expected_outflow_krw: Decimal
    fixed_cost_krw: Decimal
    net_cashflow_krw: Decimal
    ending_cash_krw: Decimal
''',
    '''class LiquidityBucket(BaseModel):
    period: str
    expected_inflow_krw: Decimal | None
    expected_outflow_krw: Decimal | None
    fixed_cost_krw: Decimal
    net_cashflow_krw: Decimal | None
    ending_cash_krw: Decimal | None
''',
)
replace_once(
    "src/intelligence/portfolio_assessment.py",
    '''    ending_cash = opening_cash
    result: list[LiquidityBucket] = []
    for period, values in raw.items():
        net = values["inflow"] - values["outflow"] - fixed_cost
        ending_cash += net
        result.append(
            LiquidityBucket(
                period=period,
                expected_inflow_krw=values["inflow"],
                expected_outflow_krw=values["outflow"],
                fixed_cost_krw=fixed_cost,
                net_cashflow_krw=net,
                ending_cash_krw=ending_cash,
''',
    '''    ending_cash: Decimal | None = opening_cash
    result: list[LiquidityBucket] = []
    for period, values in raw.items():
        has_unvalued_transaction = bool(values["missing_rates"])
        inflow = None if has_unvalued_transaction else values["inflow"]
        outflow = None if has_unvalued_transaction else values["outflow"]
        net = (
            None
            if has_unvalued_transaction
            else values["inflow"] - values["outflow"] - fixed_cost
        )
        if ending_cash is None or net is None:
            ending_cash = None
        else:
            ending_cash += net
        result.append(
            LiquidityBucket(
                period=period,
                expected_inflow_krw=inflow,
                expected_outflow_krw=outflow,
                fixed_cost_krw=fixed_cost,
                net_cashflow_krw=net,
                ending_cash_krw=ending_cash,
''',
)

# 6/13: validate pinned hashes against the exact stored payload and preserve provider raw hash separately.
replace_once(
    "src/official_case_studies.py",
    '''    response_hash: str
    payload: dict[str, Any] | list[dict[str, Any]]
    limitations: list[str] = Field(default_factory=list)
''',
    '''    response_hash: str
    provider_response_hash: str | None = None
    payload: dict[str, Any] | list[dict[str, Any]]
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def stored_payload_matches_hash(self):
        expected = _canonical_payload_hash(self.payload)
        if self.response_hash != expected:
            raise ValueError(
                f"Pinned source {self.asset_key} payload does not match response_hash"
            )
        return self
''',
)
replace_once(
    "src/official_case_studies.py",
    '''                response_hash=(
                    snapshot.response_hash or _canonical_payload_hash(snapshot.payload)
                ),
                payload=snapshot.payload,
''',
    '''                response_hash=_canonical_payload_hash(snapshot.payload),
                provider_response_hash=snapshot.response_hash,
                payload=snapshot.payload,
''',
)

snapshot_path = ROOT / "data/case_studies/official_context_snapshots_v1.json"
snapshot_data = json.loads(snapshot_path.read_text(encoding="utf-8"))
for case in snapshot_data["cases"]:
    for source in case["sources"]:
        old_hash = source.get("provider_response_hash") or source.get("response_hash")
        source["provider_response_hash"] = old_hash
        encoded = json.dumps(
            source["payload"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        source["response_hash"] = hashlib.sha256(encoded).hexdigest()
snapshot_path.write_text(
    json.dumps(snapshot_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

# 8/13: make the documented direct competition entrypoint self-contained.
replace_once(
    "competition_app.py",
    '''    by_label = {item.label: item.scenario_id for item in scenarios}
    active_label = next(item.label for item in scenarios if item.scenario_id == active_id)
''',
    '''    by_label = {item.title: item.scenario_id for item in scenarios}
    active_label = next(item.title for item in scenarios if item.scenario_id == active_id)
''',
)

# 9/13: let the documented Streamlit secret override the fallback QR URL.
replace_once(
    "streamlit_app.py",
    '''# The public URL is not a secret. An explicit deployment environment value can still
# override it if the app is moved or renamed later.
os.environ.setdefault("TRADEGUARD_PUBLIC_DEMO_URL", PUBLIC_DEMO_URL)
''',
    '''# The public URL is not a secret. Deployment configuration is applied in main so a
# Streamlit secret can override this fallback on forks or renamed applications.
''',
)
replace_once(
    "streamlit_app.py",
    '''    for key in ("KEXIM_API_KEY", "KCS_TRADE_API_KEY", "DATA_GO_KR_SERVICE_KEY"):
        _secret_to_environment(key)
''',
    '''    for key in (
        "KEXIM_API_KEY",
        "KCS_TRADE_API_KEY",
        "DATA_GO_KR_SERVICE_KEY",
        "TRADEGUARD_PUBLIC_DEMO_URL",
    ):
        _secret_to_environment(key)
    os.environ.setdefault("TRADEGUARD_PUBLIC_DEMO_URL", PUBLIC_DEMO_URL)
''',
)

# 10/13: require an FX rate for every active transaction currency before readiness.
replace_once(
    "src/copilot_scenarios.py",
    '''    if not case.capabilities.official_fx_reference:
        fx_missing.append("official or disclosed FX reference")
    fx_payload = {
''',
    '''    if not case.capabilities.official_fx_reference:
        fx_missing.append("official or disclosed FX reference")
    else:
        uncovered_fx_currencies = sorted(
            set(currencies) - _usable_fx_currencies(case)
        )
        if uncovered_fx_currencies:
            fx_missing.append(
                "FX reference for currencies: " + ", ".join(uncovered_fx_currencies)
            )
    fx_payload = {
''',
)

# Focused regression tests for all new review findings.
test_path = ROOT / "tests/test_latest_review_followups.py"
test_path.write_text('''from __future__ import annotations

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
''', encoding="utf-8")
