"""Synthetic multi-company portfolio fixtures for the public competition view."""

from __future__ import annotations

from datetime import date

from .copilot_case import CaseDataAsset, CaseIdentity, UnifiedCopilotCase
from .intelligence.portfolio_assessment import CompanyPortfolioWorkspace


def _asset(
    name: str,
    source: str,
    *,
    status: str = "available",
    payload=None,
) -> CaseDataAsset:
    return CaseDataAsset(
        asset_name=name,
        status=status,
        source=source,
        as_of_date=date(2026, 7, 28),
        source_hash=f"synthetic-{name}",
        payload=payload,
        limitations=[
            "Synthetic reviewed snapshot for public demonstration; not a live customer record."
        ],
    )


def _hanbit_case() -> UnifiedCopilotCase:
    official_assets = {
        "kexim_fx_reference": _asset(
            "kexim_fx_reference", "Synthetic KEXIM-style snapshot"
        ),
        "world_bank_country_macro": _asset(
            "world_bank_country_macro", "Synthetic World Bank-style snapshot"
        ),
        "korea_customs_country_product_trade": _asset(
            "korea_customs_country_product_trade",
            "Synthetic Korea Customs-style snapshot",
        ),
        "opendart_financial_statements": _asset(
            "opendart_financial_statements",
            "Synthetic OpenDART-style snapshot",
            status="partial",
        ),
        "nts_business_status": _asset(
            "nts_business_status", "Synthetic NTS-style snapshot"
        ),
    }
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="PORTFOLIO-HANBIT-2026H2",
            company_name="Hanbit Components Co., Ltd.",
            business_registration_number="000-00-00000",
            analysis_as_of_date=date(2026, 7, 28),
        ),
        approved_transactions=[
            {
                "transaction_id": "EXP-USD-OA-001",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 500000,
                "probability": 0.9,
                "status": "pre_shipment",
                "expected_date": "2026-09-30",
                "country_code": "VN",
                "payment_method": "open_account",
                "transaction_stage": "pre_shipment",
                "tenor_days": 90,
                "company_size": "sme",
                "preferred_bank": "KB국민은행",
                "available_documents": ["수출계약 또는 발주서"],
            },
            {
                "transaction_id": "IMP-USD-LC-001",
                "transaction_type": "import",
                "currency": "USD",
                "amount_fc": 220000,
                "probability": 1.0,
                "status": "confirmed",
                "expected_date": "2026-09-15",
                "country_code": "US",
                "payment_method": "usance L/C",
                "transaction_stage": "pre_payment",
                "tenor_days": 120,
                "company_size": "sme",
                "preferred_bank": "KB국민은행",
                "industry_tags": ["materials_parts_equipment"],
                "available_documents": ["수입계약", "Invoice"],
            },
            {
                "transaction_id": "EXP-EUR-LC-001",
                "transaction_type": "export",
                "currency": "EUR",
                "amount_fc": 300000,
                "probability": 0.8,
                "status": "post_shipment",
                "expected_date": "2026-10-31",
                "country_code": "DE",
                "payment_method": "letter of credit",
                "transaction_stage": "post_shipment",
                "tenor_days": 60,
                "company_size": "sme",
                "preferred_bank": "KB국민은행",
                "available_documents": ["수출계약 또는 발주서", "선적서류"],
            },
            {
                "transaction_id": "IMP-JPY-ADV-001",
                "transaction_type": "import",
                "currency": "JPY",
                "amount_fc": 30000000,
                "probability": 1.0,
                "status": "confirmed",
                "expected_date": "2026-08-31",
                "country_code": "JP",
                "payment_method": "advance payment",
                "transaction_stage": "pre_payment",
                "advance_payment_percent": 30,
                "company_size": "sme",
                "preferred_bank": "KB국민은행",
                "industry_tags": ["materials_parts_equipment"],
                "available_documents": ["선급금 조건이 포함된 수입계약"],
            },
        ],
        foreign_cash_positions=[
            {"currency": "USD", "amount_fc": 40000},
            {"currency": "EUR", "amount_fc": 20000},
        ],
        monthly_cost_assumptions={
            "current_cash_krw": 550000000,
            "monthly_fixed_cost_krw": 85000000,
        },
        official_fx_reference=CaseDataAsset(
            asset_name="Synthetic reviewed portfolio FX reference",
            status="available",
            source="Synthetic official FX snapshot",
            as_of_date=date(2026, 7, 28),
            source_hash="synthetic-portfolio-fx-hanbit",
            payload=[
                {"currency": "USD", "spot_rate_krw": 1350},
                {"currency": "EUR", "spot_rate_krw": 1580},
                {"currency": "JPY", "spot_rate_krw": 9.1},
            ],
            limitations=[
                "Synthetic rates for deterministic portfolio demonstration only."
            ],
        ),
        official_data_assets=official_assets,
    )


def _mirae_case() -> UnifiedCopilotCase:
    official_assets = {
        "kexim_fx_reference": _asset(
            "kexim_fx_reference", "Synthetic KEXIM-style snapshot"
        ),
        "world_bank_country_macro": _asset(
            "world_bank_country_macro",
            "Synthetic World Bank-style snapshot",
            status="partial",
        ),
        "un_comtrade_export": _asset(
            "un_comtrade_export", "Synthetic UN Comtrade-style snapshot"
        ),
        "bok_ecos_key_statistics": _asset(
            "bok_ecos_key_statistics", "Synthetic ECOS-style snapshot"
        ),
    }
    return UnifiedCopilotCase(
        identity=CaseIdentity(
            case_id="PORTFOLIO-MIRAE-2026H2",
            company_name="Mirae Beauty Labs",
            business_registration_number="111-11-11111",
            analysis_as_of_date=date(2026, 7, 28),
        ),
        approved_transactions=[
            {
                "transaction_id": "EXP-USD-DP-101",
                "transaction_type": "export",
                "currency": "USD",
                "amount_fc": 180000,
                "probability": 0.95,
                "status": "post_shipment",
                "expected_date": "2026-08-31",
                "country_code": "US",
                "payment_method": "D/P",
                "transaction_stage": "post_shipment",
                "tenor_days": 30,
                "company_size": "sme",
                "preferred_bank": "KB국민은행",
                "available_documents": ["수출계약 또는 발주서", "선적서류"],
            },
            {
                "transaction_id": "EXP-JPY-OA-101",
                "transaction_type": "export",
                "currency": "JPY",
                "amount_fc": 40000000,
                "probability": 0.75,
                "status": "pre_shipment",
                "expected_date": "2026-10-15",
                "country_code": "JP",
                "payment_method": "open_account",
                "transaction_stage": "pre_shipment",
                "tenor_days": 60,
                "company_size": "sme",
                "preferred_bank": "KB국민은행",
                "available_documents": ["수출계약 또는 발주서"],
            },
            {
                "transaction_id": "IMP-CNY-ADV-101",
                "transaction_type": "import",
                "currency": "CNY",
                "amount_fc": 900000,
                "probability": 1.0,
                "status": "confirmed",
                "expected_date": "2026-09-20",
                "country_code": "CN",
                "payment_method": "advance payment",
                "transaction_stage": "pre_payment",
                "advance_payment_percent": 50,
                "company_size": "sme",
                "preferred_bank": "KB국민은행",
                "industry_tags": ["consumer_retail"],
                "available_documents": ["선급금 조건이 포함된 수입계약"],
            },
        ],
        foreign_cash_positions=[{"currency": "USD", "amount_fc": 25000}],
        monthly_cost_assumptions={
            "current_cash_krw": 320000000,
            "monthly_fixed_cost_krw": 55000000,
        },
        official_fx_reference=CaseDataAsset(
            asset_name="Synthetic reviewed portfolio FX reference",
            status="available",
            source="Synthetic official FX snapshot",
            as_of_date=date(2026, 7, 28),
            source_hash="synthetic-portfolio-fx-mirae",
            payload=[
                {"currency": "USD", "spot_rate_krw": 1350},
                {"currency": "JPY", "spot_rate_krw": 9.1},
                {"currency": "CNY", "spot_rate_krw": 188},
            ],
            limitations=[
                "Synthetic rates for deterministic portfolio demonstration only."
            ],
        ),
        official_data_assets=official_assets,
    )


def build_demo_company_workspace() -> CompanyPortfolioWorkspace:
    companies = {
        "hanbit": _hanbit_case(),
        "mirae": _mirae_case(),
    }
    return CompanyPortfolioWorkspace(
        workspace_id="COMPETITION-PORTFOLIO-WORKSPACE",
        companies=companies,
        active_company_id="hanbit",
    )
