from src.competition_product_view import build_product_consultation_cards
from src.demo_scenarios import load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


_ALLOWED_STATUSES = {
    "consultation_candidate",
    "insufficient_information",
    "not_applicable",
    "blocked",
}


def test_default_competition_case_surfaces_governed_product_consultation_cards():
    package = load_demo_scenario("oa_high_risk")
    run = run_single_transaction_package(package)

    cards = build_product_consultation_cards(run, limit=4)

    assert cards
    assert len(cards) <= 4
    assert all(card.status in _ALLOWED_STATUSES for card in cards)
    assert all(card.official_source_count >= 1 for card in cards)
    assert all(card.next_action for card in cards)
    assert any(card.provider == "K-SURE" for card in cards)
    assert any(card.provider == "KB Kookmin Bank" for card in cards)


def test_product_consultation_cards_do_not_claim_approval_or_pricing():
    package = load_demo_scenario("oa_high_risk")
    run = run_single_transaction_package(package)

    combined = " ".join(
        [
            card.product_name,
            card.status_label,
            card.next_action,
            *card.unresolved_conditions,
        ]
        for card in build_product_consultation_cards(run)
    )

    flattened = " ".join(combined)
    forbidden = ["승인 확정", "대출 승인", "보증 발급 확정", "보험 인수 확정", "확정 금리"]
    assert not any(term in flattened for term in forbidden)


def test_product_card_limit_must_be_positive():
    package = load_demo_scenario("oa_high_risk")
    run = run_single_transaction_package(package)

    try:
        build_product_consultation_cards(run, limit=0)
    except ValueError as exc:
        assert "at least 1" in str(exc)
    else:
        raise AssertionError("limit=0 must be rejected")
