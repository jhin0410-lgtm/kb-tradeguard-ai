"""Governed real-public-data case studies for the competition prototype.

The transaction questions are synthetic.  Only aggregate public observations from the
existing official-data providers may be pinned by this module.  No customer, buyer,
shipment, customs declaration, credit conclusion, approval, or executable quote is
represented by these case studies.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .official_data_hub import OfficialDataBundle, OfficialDataQuery

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUERY_MANIFEST = ROOT / "data" / "case_studies" / "official_context_queries_v1.json"
DEFAULT_PINNED_SNAPSHOTS = (
    ROOT / "data" / "case_studies" / "official_context_snapshots_v1.json"
)


class OfficialContextCaseDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    case_id: str
    title: str
    decision_question: str
    country_code: str
    hs_code: str
    trade_flow_code: Literal["X", "M"]
    comtrade_period: str
    trade_start_yymm: str
    trade_end_yymm: str

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        code = value.upper()
        if len(code) != 2 or not code.isalpha():
            raise ValueError("country_code must contain two letters")
        return code

    @field_validator("hs_code")
    @classmethod
    def validate_hs(cls, value: str) -> str:
        code = value.strip()
        if len(code) not in {2, 4, 6} or not code.isdigit():
            raise ValueError("hs_code must contain 2, 4, or 6 digits")
        return code

    @field_validator("comtrade_period")
    @classmethod
    def validate_period(cls, value: str) -> str:
        if len(value) != 4 or not value.isdigit():
            raise ValueError("comtrade_period must use YYYY format")
        return value


class OfficialContextQueryManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_version: str
    authority_boundary: str
    cases: list[OfficialContextCaseDefinition]

    @model_validator(mode="after")
    def identifiers_are_unique(self):
        identifiers = [item.case_id for item in self.cases]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("official context case IDs must be unique")
        if len(self.cases) != 3:
            raise ValueError("the competition evidence pack requires exactly three cases")
        return self


class PinnedOfficialSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_key: str
    provider: str
    operation: str
    source_url: str | None = None
    retrieved_at: datetime | None = None
    observation_date: date | None = None
    response_hash: str
    payload: dict[str, Any] | list[dict[str, Any]]
    limitations: list[str] = Field(default_factory=list)


class PinnedOfficialContextCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    title: str
    decision_question: str
    country_code: str
    hs_code: str
    trade_flow_code: Literal["X", "M"]
    comtrade_period: str
    generated_at: datetime
    sources: list[PinnedOfficialSource]
    limitations: list[str]

    @model_validator(mode="after")
    def required_sources_exist(self):
        keys = {item.asset_key for item in self.sources}
        expected_trade_key = (
            "un_comtrade_export" if self.trade_flow_code == "X" else "un_comtrade_import"
        )
        required = {"world_bank_country_macro", expected_trade_key}
        missing = sorted(required - keys)
        if missing:
            raise ValueError("pinned case is missing required sources: " + ", ".join(missing))
        if any(not item.response_hash for item in self.sources):
            raise ValueError("pinned sources require response hashes")
        return self


class PinnedOfficialContextDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: str
    generated_at: datetime
    authority_boundary: str
    cases: list[PinnedOfficialContextCase]

    @model_validator(mode="after")
    def dataset_contract(self):
        if len(self.cases) != 3:
            raise ValueError("pinned official context dataset requires exactly three cases")
        identifiers = [item.case_id for item in self.cases]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("pinned official context case IDs must be unique")
        return self


def load_official_context_query_manifest(
    path: str | Path = DEFAULT_QUERY_MANIFEST,
) -> OfficialContextQueryManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return OfficialContextQueryManifest.model_validate(payload)


def build_official_context_query(
    definition: OfficialContextCaseDefinition,
    *,
    as_of_date: date,
    business_registration_number: str | None = None,
    dart_corp_code: str | None = None,
    dart_business_year: int | None = None,
) -> OfficialDataQuery:
    return OfficialDataQuery(
        as_of_date=as_of_date,
        country_code=definition.country_code,
        hs_code=definition.hs_code,
        trade_start_yymm=definition.trade_start_yymm,
        trade_end_yymm=definition.trade_end_yymm,
        comtrade_period=definition.comtrade_period,
        business_registration_number=business_registration_number,
        dart_corp_code=dart_corp_code,
        dart_business_year=dart_business_year,
        include_bok_key_statistics=True,
    )


def pin_official_context_case(
    definition: OfficialContextCaseDefinition,
    bundle: OfficialDataBundle,
) -> PinnedOfficialContextCase:
    expected_trade_key = (
        "un_comtrade_export" if definition.trade_flow_code == "X" else "un_comtrade_import"
    )
    required_keys = {"world_bank_country_macro", expected_trade_key}
    snapshots = {
        item.asset_key: item
        for item in bundle.snapshots
        if item.asset_key in required_keys and item.status == "available"
    }
    missing = sorted(required_keys - set(snapshots))
    if missing:
        raise ValueError(
            f"{definition.case_id} has no usable live response for: " + ", ".join(missing)
        )

    sources = []
    for asset_key in sorted(required_keys):
        snapshot = snapshots[asset_key]
        if snapshot.response_hash is None or snapshot.payload is None:
            raise ValueError(f"{asset_key} must preserve payload and response_hash")
        sources.append(
            PinnedOfficialSource(
                asset_key=asset_key,
                provider=snapshot.provider,
                operation=snapshot.operation,
                source_url=snapshot.source_url,
                retrieved_at=snapshot.retrieved_at,
                observation_date=snapshot.observation_date,
                response_hash=snapshot.response_hash,
                payload=snapshot.payload,
                limitations=snapshot.limitations,
            )
        )

    return PinnedOfficialContextCase(
        case_id=definition.case_id,
        title=definition.title,
        decision_question=definition.decision_question,
        country_code=definition.country_code,
        hs_code=definition.hs_code,
        trade_flow_code=definition.trade_flow_code,
        comtrade_period=definition.comtrade_period,
        generated_at=bundle.generated_at,
        sources=sources,
        limitations=[
            "The decision question and company context are synthetic; the attached observations are aggregate public data.",
            "World Bank and UN Comtrade observations have publication lags and can be revised after this pinned snapshot.",
            bundle.authority_boundary,
        ],
    )


def load_pinned_official_context_dataset(
    path: str | Path = DEFAULT_PINNED_SNAPSHOTS,
) -> PinnedOfficialContextDataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PinnedOfficialContextDataset.model_validate(payload)
