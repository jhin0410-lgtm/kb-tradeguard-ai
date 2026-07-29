import pytest

from src.competition_product_view import build_product_consultation_cards
from src.competition_topic6 import prepare_topic6_demo_package
from src.demo_scenarios import load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


_ALLOWED_STATUSES = {
    "consultation_candidate",
    "insufficient_information",
    "not_applicable",
    "blocked",
}


def _default_run():
    package = prepare_topic6_demo_package(load_demo_scenario("oa_high_risk"))
    return run_single_transaction_package(package)


def test_default_competition_case_surfaces_governed_product_consultation_cards():
    cards = build_product_consultation_cards(_default_run(), limit=4)

    assert cards
    assert len(cards) <= 4
    assert all(card.status in _ALLOWED_STATUSES for card in cards)
    assert all(card.official_source_count >= 1 for card in cards)
    assert all(card.next_action for card in cards)
    assert any(card.provider == "K-SURE" for card in cards)
    assert any(card.provider == "KB Kookmin Bank" for card in cards)
    assert any(card.product_name == "환변동보험" for card in cards)


def test_product_consultation_cards_do_not_claim_approval_or_pricing():
    parts = []
    for card in build_product_consultation_cards(_default_run()):
        parts.extend(
            [
                card.product_name,
                card.status_label,
                card.next_action,
                *card.unresolved_conditions,
            ]
        )
    combined = " ".join(parts)

    forbidden = ["승인 확정", "대출 승인", "보증 발급 확정", "보험 인수 확정", "확정 금리"]
    assert not any(term in combined for term in forbidden)


def test_product_card_limit_must_be_positive():
    with pytest.raises(ValueError, match="at least 1"):
        build_product_consultation_cards(_default_run(), limit=0)
