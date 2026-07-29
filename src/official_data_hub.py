"""Unified, fail-soft orchestration for reviewed official-data snapshots.

Provider adapters remain responsible for transport and response validation.  This hub
only coordinates explicit queries, records per-provider availability, and converts
reviewed results into immutable case assets.  It never treats a live response as an
approval, credit decision, compliance clearance, or executable market quote.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .copilot_case import CaseDataAsset, UnifiedCopilotCase
from .data_providers import (
    BOKECOSProvider,
    KEXIMFXProvider,
    KoreaCustomsTradeProvider,
    NTSBusinessStatusProvider,
    OpenDARTProvider,
    ProviderConfigurationError,
    UNComtradePreviewProvider,
    WorldBankCountryProvider,
)

SnapshotStatus = Literal[
    "available", "partial", "not_configured", "not_requested", "error"
]


class OfficialDataQuery(BaseModel):
    """Explicit, privacy-aware query contract for the official-data hub."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    as_of_date: date
    country_code: str | None = None
    hs_code: str | None = None
    trade_start_yymm: str | None = None
    trade_end_yymm: str | None = None
    comtrade_period: str | None = None
    business_registration_number: str | None = None
    dart_corp_code: str | None = None
    dart_business_year: int | None = Field(default=None, ge=1999, le=2100)
    dart_report_code: str = "11011"
    dart_fs_div: Literal["CFS", "OFS"] = "CFS"
    include_bok_key_statistics: bool = True

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if len(normalized) not in {2, 3} or not normalized.isalpha():
            raise ValueError("country_code must contain two or three letters")
        return normalized


class OfficialDataSnapshot(BaseModel):
    asset_key: str
    provider: str
    operation: str
    status: SnapshotStatus
    source_url: str | None = None
    retrieved_at: datetime | None = None
    observation_date: date | None = None
    response_hash: str | None = None
    request: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] | list[dict[str, Any]] | None = None
    limitations: list[str] = Field(default_factory=list)
    error: str | None = None


class OfficialDataBundle(BaseModel):
    bundle_version: str = "official-data-bundle/1.0"
    query: OfficialDataQuery
    generated_at: datetime
    snapshots: list[OfficialDataSnapshot]
    authority_boundary: str = (
        "Official API responses are read-only context. They require reviewed scope, "
        "observation dates, units, and source hashes before deterministic analysis and "
        "do not establish transaction approval, credit quality, sanctions clearance, "
        "financing eligibility, insurance acceptance, or executable pricing."
    )

    @property
    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.snapshots:
            counts[item.status] = counts.get(item.status, 0) + 1
        return counts

    @property
    def available_asset_keys(self) -> list[str]:
        return [
            item.asset_key
            for item in self.snapshots
            if item.status in {"available", "partial"}
        ]


class OfficialDataHub:
    """Coordinate the seven governed public-data adapters already in the repository."""

    def __init__(
        self,
        *,
        kexim: Any | None = None,
        world_bank: Any | None = None,
        korea_customs: Any | None = None,
        un_comtrade: Any | None = None,
        nts: Any | None = None,
        opendart: Any | None = None,
        bok: Any | None = None,
    ) -> None:
        self.kexim = kexim if kexim is not None else KEXIMFXProvider()
        self.world_bank = (
            world_bank if world_bank is not None else WorldBankCountryProvider()
        )
        self.korea_customs = (
            korea_customs
            if korea_customs is not None
            else KoreaCustomsTradeProvider()
        )
        self.un_comtrade = (
            un_comtrade
            if un_comtrade is not None
            else UNComtradePreviewProvider()
        )
        self.nts = nts if nts is not None else NTSBusinessStatusProvider()
        self.opendart = (
            opendart if opendart is not None else OpenDARTProvider()
        )
        self.bok = bok if bok is not None else BOKECOSProvider()

    @staticmethod
    def _configured(provider: Any) -> bool:
        value = getattr(provider, "is_configured", True)
        return bool(value)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        text = str(value).replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        text = str(value).replace("-", "")
        if len(text) == 8 and text.isdigit():
            try:
                return datetime.strptime(text, "%Y%m%d").date()
            except ValueError:
                return None
        return None

    def _not_configured(
        self,
        asset_key: str,
        provider: Any,
        operation: str,
        *,
        limitation: str,
    ) -> OfficialDataSnapshot:
        return OfficialDataSnapshot(
            asset_key=asset_key,
            provider=str(getattr(provider, "provider_name", type(provider).__name__)),
            operation=operation,
            status="not_configured",
            limitations=[limitation],
        )

    def _capture(
        self,
        asset_key: str,
        provider: Any,
        operation: str,
        call: Callable[[], Any],
        *,
        request: dict[str, Any] | None = None,
    ) -> OfficialDataSnapshot:
        if not self._configured(provider):
            return self._not_configured(
                asset_key,
                provider,
                operation,
                limitation="Deployment credential or provider configuration is missing.",
            )
        try:
            result = call()
        except ProviderConfigurationError as exc:
            return OfficialDataSnapshot(
                asset_key=asset_key,
                provider=str(getattr(provider, "provider_name", type(provider).__name__)),
                operation=operation,
                status="not_configured",
                request=request or {},
                error=str(exc),
                limitations=["Provider credentials must be supplied outside the repository."],
            )
        except Exception as exc:
            return OfficialDataSnapshot(
                asset_key=asset_key,
                provider=str(getattr(provider, "provider_name", type(provider).__name__)),
                operation=operation,
                status="error",
                request=request or {},
                error=f"{type(exc).__name__}: {exc}",
                limitations=[
                    "The failed provider is isolated; other official-data snapshots remain usable.",
                    "A failed live request is never replaced with invented values.",
                ],
            )

        if isinstance(result, list):
            normalized: dict[str, Any] = {
                "provider": str(getattr(provider, "provider_name", type(provider).__name__)),
                "operation": operation,
                "results": result,
            }
        elif isinstance(result, dict):
            normalized = result
        else:
            return OfficialDataSnapshot(
                asset_key=asset_key,
                provider=str(getattr(provider, "provider_name", type(provider).__name__)),
                operation=operation,
                status="error",
                request=request or {},
                error="Provider returned an unsupported result type",
            )

        rows = normalized.get("results")
        usable = rows not in (None, [], {})
        source_url = (
            normalized.get("source_url")
            or normalized.get("official_source_url")
            or normalized.get("official_api_url")
        )
        limitations = normalized.get("limitations") or []
        if isinstance(limitations, str):
            limitations = [limitations]
        return OfficialDataSnapshot(
            asset_key=asset_key,
            provider=str(
                normalized.get("provider")
                or getattr(provider, "provider_name", type(provider).__name__)
            ),
            operation=str(normalized.get("operation") or operation),
            status="available" if usable else "partial",
            source_url=str(source_url) if source_url else None,
            retrieved_at=self._parse_datetime(normalized.get("retrieved_at")),
            observation_date=self._parse_date(
                normalized.get("observation_date") or normalized.get("as_of_date")
            ),
            response_hash=(
                str(normalized.get("response_hash"))
                if normalized.get("response_hash")
                else None
            ),
            request=dict(normalized.get("request") or request or {}),
            payload=normalized,
            limitations=[str(item) for item in limitations],
        )

    def collect(self, query: OfficialDataQuery) -> OfficialDataBundle:
        snapshots: list[OfficialDataSnapshot] = []

        snapshots.append(
            self._capture(
                "kexim_fx_reference",
                self.kexim,
                "reference_rates",
                lambda: self.kexim.fetch_latest_rates(
                    query.as_of_date, lookback_days=10
                ),
                request={"as_of_date": query.as_of_date.isoformat()},
            )
        )

        if query.country_code:
            snapshots.append(
                self._capture(
                    "world_bank_country_macro",
                    self.world_bank,
                    "reference_macro_indicators",
                    lambda: self.world_bank.get_reference_macro_indicators(
                        query.country_code
                    ),
                    request={"country_code": query.country_code},
                )
            )
        else:
            snapshots.append(
                OfficialDataSnapshot(
                    asset_key="world_bank_country_macro",
                    provider="World Bank Indicators API v2",
                    operation="reference_macro_indicators",
                    status="not_requested",
                    limitations=["country_code was not supplied."],
                )
            )

        if (
            query.country_code
            and query.trade_start_yymm
            and query.trade_end_yymm
        ):
            snapshots.append(
                self._capture(
                    "korea_customs_country_product_trade",
                    self.korea_customs,
                    "country_product_trade",
                    lambda: self.korea_customs.get_country_product_trade(
                        start_yymm=query.trade_start_yymm,
                        end_yymm=query.trade_end_yymm,
                        country_code=query.country_code,
                        hs_code=query.hs_code,
                    ),
                    request={
                        "country_code": query.country_code,
                        "start_yymm": query.trade_start_yymm,
                        "end_yymm": query.trade_end_yymm,
                        "hs_code": query.hs_code,
                    },
                )
            )
        else:
            snapshots.append(
                OfficialDataSnapshot(
                    asset_key="korea_customs_country_product_trade",
                    provider=str(
                        getattr(
                            self.korea_customs,
                            "provider_name",
                            "Korea Customs Service trade-statistics API",
                        )
                    ),
                    operation="country_product_trade",
                    status="not_requested",
                    limitations=[
                        "country_code and explicit start/end months are required."
                    ],
                )
            )

        if query.country_code:
            period = query.comtrade_period or str(query.as_of_date.year - 2)
            for flow_code, suffix in (("X", "export"), ("M", "import")):
                snapshots.append(
                    self._capture(
                        f"un_comtrade_{suffix}",
                        self.un_comtrade,
                        "trade_preview",
                        lambda flow_code=flow_code: self.un_comtrade.get_trade_snapshot(
                            period=period,
                            reporter="KR",
                            partner=query.country_code,
                            hs_code=query.hs_code or "TOTAL",
                            flow_code=flow_code,
                            frequency="A",
                            max_records=100,
                        ),
                        request={
                            "period": period,
                            "reporter": "KR",
                            "partner": query.country_code,
                            "hs_code": query.hs_code or "TOTAL",
                            "flow_code": flow_code,
                        },
                    )
                )

        if query.business_registration_number:
            snapshots.append(
                self._capture(
                    "nts_business_status",
                    self.nts,
                    "status",
                    lambda: self.nts.check_status(
                        [query.business_registration_number]
                    ),
                    request={
                        "business_registration_number": query.business_registration_number
                    },
                )
            )
        else:
            snapshots.append(
                OfficialDataSnapshot(
                    asset_key="nts_business_status",
                    provider=str(
                        getattr(
                            self.nts,
                            "provider_name",
                            "National Tax Service business-registration API",
                        )
                    ),
                    operation="status",
                    status="not_requested",
                    limitations=[
                        "A reviewed domestic business registration number was not supplied."
                    ],
                )
            )

        if query.dart_corp_code:
            snapshots.append(
                self._capture(
                    "opendart_company_profile",
                    self.opendart,
                    "company_profile",
                    lambda: self.opendart.get_company(query.dart_corp_code),
                    request={"corp_code": query.dart_corp_code},
                )
            )
            if query.dart_business_year is not None:
                snapshots.append(
                    self._capture(
                        "opendart_financial_statements",
                        self.opendart,
                        "financial_statements",
                        lambda: self.opendart.get_financial_statements(
                            query.dart_corp_code,
                            query.dart_business_year,
                            report_code=query.dart_report_code,
                            fs_div=query.dart_fs_div,
                        ),
                        request={
                            "corp_code": query.dart_corp_code,
                            "business_year": query.dart_business_year,
                            "report_code": query.dart_report_code,
                            "fs_div": query.dart_fs_div,
                        },
                    )
                )
        else:
            snapshots.append(
                OfficialDataSnapshot(
                    asset_key="opendart_company_profile",
                    provider=str(
                        getattr(
                            self.opendart,
                            "provider_name",
                            "Financial Supervisory Service OpenDART API",
                        )
                    ),
                    operation="company_profile",
                    status="not_requested",
                    limitations=["A public OpenDART corporation code was not supplied."],
                )
            )

        if query.include_bok_key_statistics:
            snapshots.append(
                self._capture(
                    "bok_ecos_key_statistics",
                    self.bok,
                    "key_statistics",
                    lambda: self.bok.get_key_statistics(1, 20),
                    request={"start": 1, "end": 20},
                )
            )

        return OfficialDataBundle(
            query=query,
            generated_at=datetime.now(timezone.utc),
            snapshots=snapshots,
        )


def _asset_status(snapshot: OfficialDataSnapshot) -> str:
    if snapshot.status == "available":
        return "available"
    if snapshot.status == "partial":
        return "partial"
    return "missing"


def _normalized_fx_payload(snapshot: OfficialDataSnapshot) -> list[dict[str, Any]]:
    payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
    rows = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return []
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        unit_text = str(
            row.get("currency_unit") or row.get("currency") or ""
        ).strip().upper()
        if not unit_text:
            continue
        unit = 1
        currency = unit_text
        if "(" in unit_text and unit_text.endswith(")"):
            currency, raw_unit = unit_text[:-1].split("(", 1)
            if raw_unit.isdigit() and int(raw_unit) > 0:
                unit = int(raw_unit)
        rate = row.get("deal_base_rate", row.get("spot_rate_krw"))
        if rate in (None, ""):
            continue
        try:
            normalized_rate = float(str(rate).replace(",", "")) / unit
        except ValueError:
            continue
        if normalized_rate <= 0:
            continue
        normalized.append(
            {
                "currency": currency,
                "spot_rate_krw": normalized_rate,
                "source_currency_unit": unit_text,
                "source_rate": rate,
            }
        )
    return normalized


def _payload_has_results(payload: dict[str, Any] | list[dict[str, Any]] | None) -> bool:
    if payload is None:
        return False
    if isinstance(payload, list):
        return bool(payload)
    results = payload.get("results")
    return results not in (None, [], {})


def _bundle_hash(bundle: OfficialDataBundle) -> str:
    payload = {
        "query": bundle.query.model_dump(mode="json"),
        "snapshots": [
            {
                "asset_key": item.asset_key,
                "status": item.status,
                "response_hash": item.response_hash,
            }
            for item in bundle.snapshots
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def attach_official_data_bundle(
    case: UnifiedCopilotCase,
    bundle: OfficialDataBundle,
) -> UnifiedCopilotCase:
    """Attach reviewed provider outputs while preserving provider-level provenance."""

    assets = dict(case.official_data_assets)
    for snapshot in bundle.snapshots:
        limitations = list(snapshot.limitations)
        if snapshot.error:
            limitations.append(snapshot.error)
        assets[snapshot.asset_key] = CaseDataAsset(
            asset_name=snapshot.asset_key,
            status=_asset_status(snapshot),
            source=snapshot.provider,
            as_of_date=snapshot.observation_date or bundle.query.as_of_date,
            retrieved_at=snapshot.retrieved_at,
            source_hash=snapshot.response_hash,
            payload=snapshot.payload,
            limitations=limitations,
        )

    updates: dict[str, Any] = {"official_data_assets": assets}
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

    candidate = case.model_copy(update=updates)
    return UnifiedCopilotCase.model_validate(candidate.model_dump(mode="python"))
