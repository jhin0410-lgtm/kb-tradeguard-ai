from datetime import date, datetime, timezone

import pytest

from src.official_case_studies import (
    build_official_context_query,
    load_official_context_query_manifest,
    pin_official_context_case,
)
from src.official_data_hub import (
    OfficialDataBundle,
    OfficialDataQuery,
    OfficialDataSnapshot,
)


def _snapshot(asset_key: str, *, status: str = "available") -> OfficialDataSnapshot:
    return OfficialDataSnapshot(
        asset_key=asset_key,
        provider="Official provider fixture",
        operation="fixture",
        status=status,
        source_url="https://example.invalid/official-source",
        retrieved_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        observation_date=date(2024, 12, 31),
        response_hash=f"hash-{asset_key}",
        payload={"results": [{"value": 1}]} if status == "available" else {"results": []},
        limitations=["Fixture only."],
    )


def test_official_context_manifest_is_exactly_three_governed_cases():
    manifest = load_official_context_query_manifest()

    assert manifest.manifest_version == "official-context-queries/1.0"
    assert len(manifest.cases) == 3
    assert len({item.case_id for item in manifest.cases}) == 3
    assert {item.country_code for item in manifest.cases} == {"VN", "US", "JP"}
    assert {item.trade_flow_code for item in manifest.cases} == {"X", "M"}


def test_case_definition_builds_explicit_official_data_query():
    definition = load_official_context_query_manifest().cases[0]
    query = build_official_context_query(
        definition,
        as_of_date=date(2026, 7, 29),
    )

    assert query.country_code == definition.country_code
    assert query.hs_code == definition.hs_code
    assert query.comtrade_period == "2024"
    assert query.trade_start_yymm == "202501"
    assert query.trade_end_yymm == "202512"
    assert query.business_registration_number is None
    assert query.dart_corp_code is None


def test_pin_official_context_case_keeps_only_required_real_public_sources():
    definition = load_official_context_query_manifest().cases[0]
    query = OfficialDataQuery(
        as_of_date=date(2026, 7, 29),
        country_code="VN",
        hs_code="85",
        comtrade_period="2024",
    )
    bundle = OfficialDataBundle(
        query=query,
        generated_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        snapshots=[
            _snapshot("world_bank_country_macro"),
            _snapshot("un_comtrade_export"),
            _snapshot("un_comtrade_import"),
            _snapshot("kexim_fx_reference", status="not_configured"),
        ],
    )

    pinned = pin_official_context_case(definition, bundle)

    assert [item.asset_key for item in pinned.sources] == [
        "un_comtrade_export",
        "world_bank_country_macro",
    ]
    assert all(item.response_hash for item in pinned.sources)
    assert "synthetic" in pinned.limitations[0].lower()


def test_pin_official_context_case_rejects_empty_required_trade_response():
    definition = load_official_context_query_manifest().cases[2]
    bundle = OfficialDataBundle(
        query=OfficialDataQuery(
            as_of_date=date(2026, 7, 29),
            country_code="JP",
            hs_code="84",
            comtrade_period="2024",
        ),
        generated_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        snapshots=[
            _snapshot("world_bank_country_macro"),
            _snapshot("un_comtrade_import", status="partial"),
        ],
    )

    with pytest.raises(ValueError, match="un_comtrade_import"):
        pin_official_context_case(definition, bundle)
