from datetime import date

from src.copilot_case import CaseIdentity, UnifiedCopilotCase
from src.official_data_hub import (
    OfficialDataHub,
    OfficialDataQuery,
    attach_official_data_bundle,
)


class FakeKEXIM:
    provider_name = "Fake KEXIM"
    is_configured = True

    def fetch_latest_rates(self, as_of_date, lookback_days=10):
        return {
            "provider": self.provider_name,
            "operation": "reference_rates",
            "source_url": "https://example.test/kexim",
            "retrieved_at": "2026-07-28T00:00:00+00:00",
            "observation_date": "20260725",
            "response_hash": "hash-kexim",
            "results": [
                {"currency_unit": "USD", "deal_base_rate": 1350},
                {"currency_unit": "JPY(100)", "deal_base_rate": 910},
            ],
            "limitations": ["reference only"],
        }


class FakeWorldBank:
    provider_name = "Fake World Bank"

    def get_reference_macro_indicators(self, country_code):
        return [
            {
                "provider": self.provider_name,
                "results": {
                    "country_code": country_code,
                    "indicator_code": "NY.GDP.MKTP.KD.ZG",
                    "observation_year": 2025,
                    "value": 6.5,
                },
                "response_hash": "hash-world-bank",
            }
        ]


class FakeCustoms:
    provider_name = "Fake Customs"
    is_configured = True

    def get_country_product_trade(self, **kwargs):
        return {
            "provider": self.provider_name,
            "operation": "country_product_trade",
            "source_url": "https://example.test/customs",
            "retrieved_at": "2026-07-28T00:00:00+00:00",
            "request": kwargs,
            "response_hash": "hash-customs",
            "results": [{"period": "202601", "export_value_usd": 1000}],
            "limitations": [],
        }


class FakeComtrade:
    provider_name = "Fake Comtrade"

    def get_trade_snapshot(self, **kwargs):
        return {
            "provider": self.provider_name,
            "operation": "trade_preview",
            "source_url": "https://example.test/comtrade",
            "retrieved_at": "2026-07-28T00:00:00+00:00",
            "request": kwargs,
            "response_hash": f"hash-{kwargs['flow_code']}",
            "results": [{"flow_code": kwargs["flow_code"], "primary_value_usd": 100}],
            "limitations": [],
        }


class FakeNTS:
    provider_name = "Fake NTS"
    is_configured = True

    def check_status(self, business_numbers):
        return {
            "provider": self.provider_name,
            "operation": "status",
            "source_url": "https://example.test/nts",
            "retrieved_at": "2026-07-28T00:00:00+00:00",
            "response_hash": "hash-nts",
            "results": [
                {
                    "business_number": business_numbers[0],
                    "business_status": "계속사업자",
                }
            ],
            "limitations": [],
        }


class FakeOpenDART:
    provider_name = "Fake OpenDART"
    is_configured = True

    def get_company(self, corp_code):
        return {
            "provider": self.provider_name,
            "operation": "company_profile",
            "source_url": "https://example.test/dart",
            "retrieved_at": "2026-07-28T00:00:00+00:00",
            "response_hash": "hash-company",
            "results": {"corp_code": corp_code, "corp_name": "Demo Corp"},
            "limitations": [],
        }

    def get_financial_statements(
        self,
        corp_code,
        business_year,
        *,
        report_code,
        fs_div,
    ):
        return {
            "provider": self.provider_name,
            "operation": "financial_statements",
            "source_url": "https://example.test/dart",
            "retrieved_at": "2026-07-28T00:00:00+00:00",
            "response_hash": "hash-financials",
            "corp_code": corp_code,
            "business_year": str(business_year),
            "report_code": report_code,
            "fs_div": fs_div,
            "results": [{"account_nm": "자산총계", "thstrm_amount": "100"}],
            "limitations": [],
        }


class FakeBOK:
    provider_name = "Fake BOK"
    is_configured = True

    def get_key_statistics(self, start, end):
        return {
            "provider": self.provider_name,
            "operation": "key_statistics",
            "source_url": "https://example.test/bok",
            "retrieved_at": "2026-07-28T00:00:00+00:00",
            "response_hash": "hash-bok",
            "results": [{"stat_name": "기준금리", "data_value": "2.50"}],
            "limitations": [],
        }


def _hub(**overrides):
    providers = {
        "kexim": FakeKEXIM(),
        "world_bank": FakeWorldBank(),
        "korea_customs": FakeCustoms(),
        "un_comtrade": FakeComtrade(),
        "nts": FakeNTS(),
        "opendart": FakeOpenDART(),
        "bok": FakeBOK(),
    }
    providers.update(overrides)
    return OfficialDataHub(**providers)


def _query():
    return OfficialDataQuery(
        as_of_date=date(2026, 7, 28),
        country_code="VN",
        hs_code="8542",
        trade_start_yymm="202601",
        trade_end_yymm="202606",
        comtrade_period="2025",
        business_registration_number="123-45-67890",
        dart_corp_code="00123456",
        dart_business_year=2025,
    )


def test_hub_collects_all_provider_surfaces_with_per_source_provenance():
    bundle = _hub().collect(_query())
    by_key = {item.asset_key: item for item in bundle.snapshots}

    assert {
        "kexim_fx_reference",
        "world_bank_country_macro",
        "korea_customs_country_product_trade",
        "un_comtrade_export",
        "un_comtrade_import",
        "nts_business_status",
        "opendart_company_profile",
        "opendart_financial_statements",
        "bok_ecos_key_statistics",
    }.issubset(by_key)
    assert all(
        by_key[key].status == "available"
        for key in {
            "kexim_fx_reference",
            "world_bank_country_macro",
            "korea_customs_country_product_trade",
            "un_comtrade_export",
            "un_comtrade_import",
            "nts_business_status",
            "opendart_company_profile",
            "opendart_financial_statements",
            "bok_ecos_key_statistics",
        }
    )
    assert by_key["kexim_fx_reference"].response_hash == "hash-kexim"
    assert bundle.status_counts["available"] == 9


def test_bundle_attachment_preserves_assets_and_builds_case_fx_and_financial_context():
    bundle = _hub().collect(_query())
    case = UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="CASE-OFFICIAL-DATA",
            company_name="Demo Corp",
            analysis_as_of_date=date(2026, 7, 28),
        )
    )

    updated = attach_official_data_bundle(case, bundle)

    assert case.official_data_assets == {}
    assert len(updated.official_data_assets) == len(bundle.snapshots)
    assert updated.official_fx_reference is not None
    rates = {
        row["currency"]: row["spot_rate_krw"]
        for row in updated.official_fx_reference.payload
    }
    assert rates == {"USD": 1350.0, "JPY": 9.1}
    assert updated.financial_context is not None
    assert updated.financial_context.status == "available"
    assert updated.audit_summary()["official_data_asset_count"] == len(bundle.snapshots)


class UnconfiguredProvider:
    provider_name = "No Key Provider"
    is_configured = False


class FailingWorldBank:
    provider_name = "Failing World Bank"

    def get_reference_macro_indicators(self, country_code):
        raise RuntimeError("simulated outage")


def test_hub_is_fail_soft_and_never_invents_fallback_values():
    bundle = _hub(
        kexim=UnconfiguredProvider(),
        world_bank=FailingWorldBank(),
    ).collect(_query())
    by_key = {item.asset_key: item for item in bundle.snapshots}

    assert by_key["kexim_fx_reference"].status == "not_configured"
    assert by_key["kexim_fx_reference"].payload is None
    assert by_key["world_bank_country_macro"].status == "error"
    assert by_key["world_bank_country_macro"].payload is None
    assert "simulated outage" in by_key["world_bank_country_macro"].error
    assert by_key["korea_customs_country_product_trade"].status == "available"


def test_missing_optional_identifiers_are_reported_as_not_requested():
    query = OfficialDataQuery(as_of_date=date(2026, 7, 28))
    bundle = _hub().collect(query)
    by_key = {item.asset_key: item for item in bundle.snapshots}

    assert by_key["world_bank_country_macro"].status == "not_requested"
    assert by_key["korea_customs_country_product_trade"].status == "not_requested"
    assert by_key["nts_business_status"].status == "not_requested"
    assert by_key["opendart_company_profile"].status == "not_requested"
