from datetime import date

import pytest

from src.copilot_case import CaseIdentity, UnifiedCopilotCase
from src.intelligence.product_matching import (
    TradeFinanceNeedProfile,
    apply_product_matching,
    canonical_bank_name,
    load_product_registry,
    match_trade_finance_products,
)


def _export_profile(**updates):
    payload = {
        "profile_id": "NEED-EXPORT-001",
        "transaction_id": "EXP-001",
        "transaction_direction": "export",
        "transaction_stage": "pre_shipment",
        "declared_needs": [
            "buyer_credit_investigation",
            "export_receivable_nonpayment_protection",
            "pre_shipment_working_capital",
            "fx_cashflow_certainty",
        ],
        "company_size": "sme",
        "payment_method": "open_account",
        "tenor_days": 90,
        "preferred_bank": "KB국민은행",
        "industry_tags": [],
        "available_documents": ["수출계약 또는 발주서"],
    }
    payload.update(updates)
    return TradeFinanceNeedProfile(**payload)


def _case():
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-PRODUCT-MATCHING",
            analysis_as_of_date=date(2026, 7, 26),
        ),
        approved_transactions=[
            {
                "transaction_id": "EXP-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "expected_date": "2026-10-31",
            }
        ],
    )


def _by_product(result):
    return {
        candidate.product_or_service_name: candidate
        for candidate in result.product_candidates
    }


def test_product_registry_has_unique_products_and_valid_source_links():
    registry = load_product_registry()

    assert registry.registry_version == "trade-finance-products/1.0"
    assert len(registry.products) == 10
    assert len({item.product_id for item in registry.products}) == len(registry.products)
    assert "does not determine eligibility" in registry.authority_boundary


def test_export_profile_generates_specific_consultation_candidates_and_blocked_direct_channel():
    result = match_trade_finance_products([_export_profile()])
    candidates = _by_product(result)

    assert set(candidates) == {
        "국외기업 신용조사",
        "단기수출보험(선적후)",
        "수출신용보증(선적전)",
        "수출신용보증(다이렉트-선적전)",
        "환변동보험",
        "KB 수출기업 우대대출",
    }
    assert candidates["국외기업 신용조사"].candidate_status == "consultation_candidate"
    assert candidates["단기수출보험(선적후)"].candidate_status == "consultation_candidate"
    assert candidates["수출신용보증(선적전)"].candidate_status == "consultation_candidate"
    assert candidates["환변동보험"].candidate_status == "consultation_candidate"
    assert candidates["KB 수출기업 우대대출"].candidate_status == "consultation_candidate"
    direct = candidates["수출신용보증(다이렉트-선적전)"]
    assert direct.candidate_status == "blocked"
    assert any("not in the public channel list" in item for item in direct.disqualifying_conditions)
    assert all(candidate.official_source_ids for candidate in result.product_candidates)
    assert len(result.consultation_requirements) == 5


def test_product_match_does_not_mix_import_products_into_export_case():
    result = match_trade_finance_products([_export_profile()])

    assert not any(
        candidate.product_category == "import_finance"
        for candidate in result.product_candidates
    )


def test_short_term_export_insurance_tenor_above_public_maximum_is_not_applicable():
    profile = _export_profile(
        declared_needs=["export_receivable_nonpayment_protection"],
        tenor_days=900,
    )
    candidate = match_trade_finance_products([profile]).product_candidates[0]

    assert candidate.product_or_service_name == "단기수출보험(선적후)"
    assert candidate.candidate_status == "not_applicable"
    assert any("exceeds the public maximum" in item for item in candidate.disqualifying_conditions)


def test_direct_pre_shipment_product_accepts_current_official_channel_bank():
    profile = _export_profile(
        declared_needs=["pre_shipment_working_capital"],
        preferred_bank="Shinhan Bank",
    )
    candidates = _by_product(match_trade_finance_products([profile]))

    assert candidates["수출신용보증(다이렉트-선적전)"].candidate_status == (
        "consultation_candidate"
    )
    assert canonical_bank_name("Shinhan Bank") == canonical_bank_name("신한은행")
    assert candidates["KB 수출기업 우대대출"].candidate_status == "blocked"


def test_unknown_company_size_keeps_fx_candidate_partial_not_eligible():
    profile = _export_profile(
        declared_needs=["fx_cashflow_certainty"],
        company_size="unknown",
    )
    candidate = match_trade_finance_products([profile]).product_candidates[0]

    assert candidate.product_or_service_name == "환변동보험"
    assert candidate.candidate_status == "insufficient_information"
    assert candidate.record_status == "partial"
    assert any("기업규모" in item for item in candidate.unresolved_eligibility_conditions)


def test_global_supply_chain_import_product_requires_public_industry_context():
    base = {
        "profile_id": "NEED-IMPORT-001",
        "transaction_id": "IMP-001",
        "transaction_direction": "import",
        "transaction_stage": "pre_payment",
        "declared_needs": ["import_working_capital"],
        "company_size": "sme",
        "tenor_days": 180,
    }
    matching = TradeFinanceNeedProfile(
        **base,
        industry_tags=["defense"],
    )
    missing = TradeFinanceNeedProfile(
        **{**base, "profile_id": "NEED-IMPORT-002"},
        industry_tags=[],
    )
    outside = TradeFinanceNeedProfile(
        **{**base, "profile_id": "NEED-IMPORT-003"},
        industry_tags=["consumer_retail"],
    )

    assert match_trade_finance_products([matching]).product_candidates[0].candidate_status == (
        "consultation_candidate"
    )
    assert match_trade_finance_products([missing]).product_candidates[0].candidate_status == (
        "insufficient_information"
    )
    assert match_trade_finance_products([outside]).product_candidates[0].candidate_status == (
        "not_applicable"
    )


def test_kb_candidate_is_a_consultation_route_not_an_approval_claim():
    profile = _export_profile(
        declared_needs=["export_working_capital"],
        preferred_bank="국민은행",
    )
    result = match_trade_finance_products([profile])
    candidate = _by_product(result)["KB 수출기업 우대대출"]
    requirement = next(
        item
        for item in result.consultation_requirements
        if "KB 수출기업 우대대출" in item.purpose
    )

    assert candidate.candidate_status == "consultation_candidate"
    assert any(
        "KB 내부 신용심사" in item
        for item in candidate.unresolved_eligibility_conditions
    )
    assert requirement.consultation_route == "bank_relationship_manager"
    assert candidate.next_action.endswith("확인한다.")
    assert any("not an institutional decision" in item for item in candidate.limitations)


def test_case_application_is_immutable_idempotent_and_replaces_stale_registry_results():
    case = _case()
    before = case.case_hash
    fx_profile = _export_profile(declared_needs=["fx_cashflow_certainty"])

    first, first_outcome = apply_product_matching(case, [fx_profile])
    repeated, repeated_outcome = apply_product_matching(first, [fx_profile])

    assert case.trade_finance.product_candidates == []
    assert case.case_hash == before
    assert first.case_hash != before
    assert repeated.case_hash == first.case_hash
    assert repeated_outcome.product_candidate_ids == first_outcome.product_candidate_ids

    buyer_profile = _export_profile(
        profile_id="NEED-BUYER-001",
        declared_needs=["buyer_credit_investigation"],
    )
    replaced, outcome = apply_product_matching(repeated, [buyer_profile])

    assert outcome.status_counts == {"consultation_candidate": 1}
    assert [
        item.product_or_service_name
        for item in replaced.trade_finance.product_candidates
    ] == ["국외기업 신용조사"]
    assert not any(
        item.product_or_service_name == "환변동보험"
        for item in replaced.trade_finance.product_candidates
    )


def test_case_application_rejects_unknown_transaction_reference():
    profile = _export_profile(transaction_id="EXP-UNKNOWN")

    with pytest.raises(ValueError, match="unknown approved transactions"):
        apply_product_matching(_case(), [profile])


def test_duplicate_need_profile_ids_are_rejected():
    profile = _export_profile()

    with pytest.raises(ValueError, match="profile IDs must be unique"):
        match_trade_finance_products([profile, profile])


def test_product_outputs_preserve_transaction_linkage():
    profile = TradeFinanceNeedProfile(
        profile_id="NEED-LINK-001",
        transaction_id="EXP-LINK-001",
        transaction_direction="export",
        transaction_stage="pre_shipment",
        declared_needs=["buyer_credit_investigation"],
        company_size="sme",
    )

    result = match_trade_finance_products([profile])

    assert result.product_candidates
    assert all(
        item.linked_transaction_ids == ["EXP-LINK-001"]
        for item in result.product_candidates
    )
    assert all(
        item.linked_transaction_ids == ["EXP-LINK-001"]
        for item in result.consultation_requirements
    )
