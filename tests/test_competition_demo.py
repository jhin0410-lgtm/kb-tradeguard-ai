import pytest

from src.competition_demo import (
    build_competition_validation_status,
    build_public_demo_qr_png,
    normalize_public_demo_url,
)


def test_competition_validation_status_matches_governed_assets():
    status = build_competition_validation_status()

    assert status.governed_rule_count == 22
    assert status.gold_case_count == 30
    assert status.mutation_case_count == 150
    assert status.demo_scenario_count == 4
    assert "합성 Fixture" in status.authority_boundary


def test_public_demo_url_is_normalized_and_governed():
    assert normalize_public_demo_url("https://example.streamlit.app") == (
        "https://example.streamlit.app/?demo=1"
    )
    assert normalize_public_demo_url(
        "https://example.streamlit.app/path?scenario=oa_high_risk#ignored",
        presentation=True,
    ) == (
        "https://example.streamlit.app/path?scenario=oa_high_risk&demo=1&presentation=1"
    )


@pytest.mark.parametrize(
    "value",
    ["", "example.com", "ftp://example.com", "javascript:alert(1)"],
)
def test_public_demo_url_rejects_unsafe_or_relative_values(value):
    with pytest.raises(ValueError):
        normalize_public_demo_url(value)


def test_public_demo_qr_is_a_png_created_without_network_calls():
    payload = build_public_demo_qr_png("https://example.streamlit.app")

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(payload) > 100
