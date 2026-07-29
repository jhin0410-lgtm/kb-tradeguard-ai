import json
from datetime import date
from decimal import Decimal

import pytest

from src.data_providers import ProviderResponseError, WorldBankCountryProvider
from src.intelligence.country_compliance import (
    build_fatf_country_fact,
    build_fatf_country_screening,
    build_world_bank_country_facts,
)


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _world_bank_payload(indicator_code="NY.GDP.MKTP.KD.ZG"):
    return [
        {"page": 1, "pages": 1, "per_page": 100, "total": 2},
        [
            {
                "indicator": {"id": indicator_code, "value": "GDP growth (annual %)"},
                "country": {"id": "VN", "value": "Vietnam"},
                "countryiso3code": "VNM",
                "date": "2024",
                "value": 7.09,
                "unit": "",
                "obs_status": "",
                "decimal": 1,
            },
            {
                "indicator": {"id": indicator_code, "value": "GDP growth (annual %)"},
                "country": {"id": "VN", "value": "Vietnam"},
                "countryiso3code": "VNM",
                "date": "2025",
                "value": None,
                "unit": "",
                "obs_status": "",
                "decimal": 1,
            },
        ],
    ]


def test_world_bank_provider_requires_no_key_and_keeps_latest_non_null_observation():
    captured = {}

    def transport(url, headers, timeout):
        captured.update(url=url, headers=headers, timeout=timeout)
        return _json_bytes(_world_bank_payload())

    result = WorldBankCountryProvider(transport=transport).get_latest_indicator(
        "vn", "ny.gdp.mktp.kd.zg", start_year=2020, end_year=2025
    )

    assert "/country/VN/indicator/NY.GDP.MKTP.KD.ZG" in captured["url"]
    assert "date=2020%3A2025" in captured["url"]
    assert captured["headers"]["Accept"] == "application/json"
    assert result["results"]["observation_year"] == 2024
    assert result["results"]["value"] == pytest.approx(7.09)
    assert len(result["response_hash"]) == 64


def test_world_bank_provider_does_not_fabricate_missing_observation():
    provider = WorldBankCountryProvider(
        transport=lambda *args: _json_bytes([{"page": 1}, []])
    )
    result = provider.get_latest_indicator(
        "US", "FI.RES.TOTL.MO", start_year=2020, end_year=2025
    )

    assert result["results"] is None
    assert result["limitations"]


def test_world_bank_provider_rejects_malformed_response():
    provider = WorldBankCountryProvider(transport=lambda *args: _json_bytes({"bad": True}))
    with pytest.raises(ProviderResponseError, match="metadata/data array"):
        provider.get_latest_indicator("VN", "NY.GDP.MKTP.KD.ZG")


def test_world_bank_observation_becomes_typed_non_scored_country_fact():
    provider = WorldBankCountryProvider(
        transport=lambda *args: _json_bytes(_world_bank_payload())
    )
    payload = provider.get_latest_indicator(
        "VN", "NY.GDP.MKTP.KD.ZG", start_year=2020, end_year=2025
    )
    facts = build_world_bank_country_facts([payload])

    assert len(facts) == 1
    fact = facts[0]
    assert fact.country_code == "VN"
    assert fact.dimension == "macroeconomic"
    assert fact.value == Decimal("7.09")
    assert fact.risk_direction == "lower_is_worse"
    assert fact.benchmark_or_threshold is None
    assert any("No project-defined cut-off" in item for item in fact.limitations)


def test_fatf_vietnam_is_a_sourced_monitoring_flag_not_a_prohibition():
    fact = build_fatf_country_fact(
        "VN", analysis_as_of_date=date(2026, 7, 26)
    )
    screening = build_fatf_country_screening(
        "VN", "Vietnam", analysis_as_of_date=date(2026, 7, 26)
    )

    assert fact.value == "increased_monitoring"
    assert fact.record_status == "verified"
    assert "not a transaction prohibition" in fact.interpretation
    assert screening.result == "potential_match"
    assert screening.method == "exact"
    assert screening.matched_entries[0].identifiers["country_code"] == "VN"
    assert screening.reviewed_by_human is False


def test_fatf_unlisted_country_does_not_claim_low_risk():
    fact = build_fatf_country_fact(
        "US", analysis_as_of_date=date(2026, 7, 26)
    )
    screening = build_fatf_country_screening(
        "US", "United States", analysis_as_of_date=date(2026, 7, 26)
    )

    assert fact.value == "not_listed_in_public_statements"
    assert "does not establish low" in fact.interpretation
    assert screening.result == "clear"
    assert screening.matched_entries == []
    assert any("does not establish low" in item for item in screening.limitations)


def test_fatf_snapshot_is_marked_stale_after_freshness_limit():
    fact = build_fatf_country_fact(
        "VN", analysis_as_of_date=date(2027, 1, 31), max_age_days=150
    )

    assert fact.record_status == "stale"
    assert any("freshness limit" in item for item in fact.limitations)
