from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected anchor not found in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/intelligence/single_transaction_pipeline.py",
    '''    def belongs_to_transaction(record: Any) -> bool:
        linked = list(getattr(record, "linked_transaction_ids", []) or [])
        if transaction_id in linked:
            return True
        source_id = str(getattr(getattr(record, "source", None), "source_id", ""))
        return not linked and source_id.startswith("TRADE-FINANCE-PRODUCTS-")
''',
    '''    def belongs_to_transaction(record: Any) -> bool:
        linked = list(getattr(record, "linked_transaction_ids", []) or [])
        source_id = str(getattr(getattr(record, "source", None), "source_id", ""))
        registry_derived = source_id.startswith("TRADE-FINANCE-PRODUCTS-")
        return registry_derived and (transaction_id in linked or not linked)
''',
)

replace_once(
    "src/copilot_scenarios.py",
    '''    payload = asset.payload
    if isinstance(payload, dict):
        if all(isinstance(value, (int, float)) for value in payload.values()):
            return {
                str(currency).upper()
                for currency, value in payload.items()
                if float(value) > 0
            }
        payload = [payload]
''',
    '''    payload = asset.payload
    if isinstance(payload, dict):
        mapping_like = bool(payload) and all(
            len(str(currency)) == 3 and str(currency).isalpha()
            for currency in payload
        )
        if mapping_like:
            currencies: set[str] = set()
            for currency, value in payload.items():
                try:
                    usable = value is not None and float(value) > 0
                except (TypeError, ValueError):
                    usable = False
                if usable:
                    currencies.add(str(currency).upper())
            return currencies
        payload = [payload]
''',
)

replace_once(
    "src/intelligence/transaction_capacity.py",
    '''def _json_value(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None
''',
    '''def _json_value(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _audit_decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None
''',
)
replace_once(
    "src/intelligence/transaction_capacity.py",
    '''            "amount_fc": _json_value(amount_fc),
            "fx_rate_krw": _json_value(fx_rate),
''',
    '''            "amount_fc": _audit_decimal(amount_fc),
            "fx_rate_krw": _audit_decimal(fx_rate),
''',
)
replace_once(
    "src/intelligence/transaction_capacity.py",
    '''            "protection_percent": _json_value(request.protection_percent),
            "pre_shipment_funding_need_krw": _json_value(
                request.pre_shipment_funding_need_krw
            ),
''',
    '''            "protection_percent": _audit_decimal(request.protection_percent),
            "pre_shipment_funding_need_krw": _audit_decimal(
                request.pre_shipment_funding_need_krw
            ),
''',
)

path = ROOT / "tests/test_latest_review_followups.py"
text = path.read_text(encoding="utf-8")
text = text.replace(
    '''    other = ProductCandidate(
        product_candidate_id="PC-OTHER", linked_transaction_ids=["IMP-002"], provider="Bank",
        product_or_service_name="Other", product_category="import_finance", matched_need="need",
        candidate_status="insufficient_information", next_action="consult", source=other_source,
    )
''',
    '''    other = ProductCandidate(
        product_candidate_id="PC-OTHER", linked_transaction_ids=["IMP-002"], provider="Bank",
        product_or_service_name="Other", product_category="import_finance", matched_need="need",
        candidate_status="insufficient_information", next_action="consult", source=other_source,
    )
    manual_current = ProductCandidate(
        product_candidate_id="PC-MANUAL-CURRENT", linked_transaction_ids=["EXP-001"], provider="Advisor",
        product_or_service_name="Manual reviewed option", product_category="other", matched_need="manual",
        candidate_status="insufficient_information", next_action="review", source=other_source,
    )
''',
)
text = text.replace(
    '''            product_candidates=[current, other], consultation_requirements=[requirement]
''',
    '''            product_candidates=[current, other, manual_current], consultation_requirements=[requirement]
''',
)
text = text.replace(
    '''    assert [item.product_candidate_id for item in updated.trade_finance.product_candidates] == ["PC-OTHER"]
''',
    '''    assert [item.product_candidate_id for item in updated.trade_finance.product_candidates] == [
        "PC-OTHER", "PC-MANUAL-CURRENT"
    ]
''',
)
text += '''\n\ndef test_fx_scenario_accepts_numeric_string_rate_mapping():
    case = UnifiedCopilotCase(
        identity=CaseIdentity(case_id="CASE-FX-STRING"),
        approved_transactions=[
            {"transaction_id": "EXP-USD", "transaction_type": "export", "currency": "USD", "amount_fc": 100},
        ],
        official_fx_reference=CaseDataAsset(
            asset_name="FX", status="available", source="fixture", payload={"USD": "1350"},
        ),
    )
    proposal = propose_scenarios(case)
    fx = next(item for item in proposal.candidates if item.scenario_type == "fx_shock")
    assert fx.readiness == "ready"
    assert fx.missing_inputs == []


def test_capacity_result_metrics_remain_numeric_for_grounding():
    analysis = analyze_transaction_capacity(_capacity_case(), _capacity_request())
    metrics = analysis.calculation.result["metrics"]
    assert isinstance(metrics["gross_transaction_krw"], float)
    assert isinstance(metrics["gross_transaction_to_cash_pct"], float)
    assert analysis.calculation.input_assumptions["amount_fc"] == "500000"
    assert analysis.calculation.input_assumptions["fx_rate_krw"] == "1350.123456789"
'''
path.write_text(text, encoding="utf-8")
