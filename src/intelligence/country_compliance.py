"""Deterministic country-context and FATF public-list fact builders.

This layer converts validated provider payloads and a reviewed official snapshot into
typed facts.  It deliberately avoids a composite country score, trade approval, or
institution-specific AML decision.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..trade_finance_domain import (
    ComplianceMatch,
    ComplianceScreeningResult,
    CountryRiskFact,
    SourceReference,
)

WORLD_BANK_INDICATOR_SPECS: dict[str, dict[str, str]] = {
    "NY.GDP.MKTP.KD.ZG": {
        "dimension": "macroeconomic",
        "unit": "% annual growth",
        "risk_direction": "lower_is_worse",
        "interpretation": (
            "Annual real GDP growth is a macroeconomic context fact. Weak or negative growth "
            "can increase commercial stress, but this observation alone does not determine "
            "buyer credit quality or transaction acceptability."
        ),
    },
    "FP.CPI.TOTL.ZG": {
        "dimension": "macroeconomic",
        "unit": "% annual change",
        "risk_direction": "higher_is_worse",
        "interpretation": (
            "Consumer-price inflation is a macroeconomic context fact. Elevated inflation may "
            "signal operating, funding, and currency pressure, but must be assessed with other "
            "country and transaction evidence."
        ),
    },
    "FI.RES.TOTL.MO": {
        "dimension": "sovereign_transfer",
        "unit": "months of imports",
        "risk_direction": "lower_is_worse",
        "interpretation": (
            "Reserve coverage in months of imports is a transfer-liquidity context fact. Lower "
            "coverage can indicate less capacity to absorb external-payment stress; it is not "
            "a prediction that remittance or settlement will be restricted."
        ),
    },
    "BN.CAB.XOKA.GD.ZS": {
        "dimension": "macroeconomic",
        "unit": "% of GDP",
        "risk_direction": "lower_is_worse",
        "interpretation": (
            "The current-account balance relative to GDP is an external-balance context fact. "
            "A deficit can add vulnerability, but the observation must not be used as a stand-"
            "alone country-risk grade."
        ),
    },
}


def _stable_id(prefix: str, payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_world_bank_country_facts(provider_payloads: list[dict[str, Any]]) -> list[CountryRiskFact]:
    """Convert governed World Bank observations into typed, non-scored country facts."""

    facts: list[CountryRiskFact] = []
    for payload in provider_payloads:
        indicator_code = str(payload.get("indicator_code") or "").upper()
        spec = WORLD_BANK_INDICATOR_SPECS.get(indicator_code)
        if spec is None:
            raise ValueError(f"Indicator {indicator_code!r} is outside the governed country set")
        result = payload.get("results")
        if result is None:
            continue
        country_code = str(result.get("country_code") or payload.get("country_code") or "").upper()
        observation_year = int(result["observation_year"])
        value = Decimal(str(result["value"]))
        source_id = f"WB-WDI-{country_code}-{indicator_code}-{observation_year}"
        source = SourceReference(
            source_id=source_id,
            source_name="World Bank Indicators API v2",
            source_tier="tier_1",
            source_kind="official_api",
            source_locator=payload.get("official_source_url"),
            as_of_date=date(observation_year, 12, 31),
            retrieved_at=_parse_datetime(payload.get("retrieved_at")),
            content_hash=payload.get("response_hash"),
            effective_date_verified=True,
        )
        limitations = list(payload.get("limitations") or [])
        limitations.extend(
            [
                "Annual country data may be published with a lag and may be revised.",
                "No project-defined cut-off or composite country score is applied.",
                "Country context cannot substitute for buyer due diligence or current K-SURE and bank review.",
            ]
        )
        facts.append(
            CountryRiskFact(
                fact_id=_stable_id("COUNTRY", source_id),
                country_code=country_code,
                dimension=spec["dimension"],
                metric_name=str(result.get("indicator_name") or indicator_code),
                value=value,
                unit=spec["unit"],
                observation_date=date(observation_year, 12, 31),
                risk_direction=spec["risk_direction"],
                interpretation=spec["interpretation"],
                benchmark_or_threshold=None,
                source=source,
                record_status="verified",
                limitations=limitations,
            )
        )
    return facts


def default_fatf_registry_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "reference" / "fatf_jurisdictions_2026-06-19.json"


def load_fatf_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path is not None else default_fatf_registry_path()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load FATF registry: {registry_path}") from exc

    required = {
        "publication_date",
        "retrieval_date",
        "official_source_url",
        "high_risk_call_for_action",
        "increased_monitoring",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError("FATF registry is missing required fields: " + ", ".join(missing))

    codes: list[str] = []
    for key in ("high_risk_call_for_action", "increased_monitoring"):
        rows = payload[key]
        if not isinstance(rows, list):
            raise ValueError(f"FATF registry field {key} must be a list")
        for row in rows:
            code = str(row.get("country_code") or "").upper()
            if len(code) != 2 or not code.isalpha():
                raise ValueError(f"Invalid FATF country code: {code!r}")
            codes.append(code)
    if len(codes) != len(set(codes)):
        raise ValueError("FATF registry country codes must be unique")
    return payload


def _fatf_lookup(country_code: str, registry: dict[str, Any]) -> tuple[str, str | None]:
    code = str(country_code).strip().upper()
    if len(code) != 2 or not code.isalpha():
        raise ValueError("FATF country code must contain two letters")
    for row in registry["high_risk_call_for_action"]:
        if row["country_code"].upper() == code:
            return "call_for_action", row["country_name"]
    for row in registry["increased_monitoring"]:
        if row["country_code"].upper() == code:
            return "increased_monitoring", row["country_name"]
    return "not_listed_in_public_statements", None


def _fatf_source(registry: dict[str, Any]) -> SourceReference:
    publication = date.fromisoformat(registry["publication_date"])
    retrieval = date.fromisoformat(registry["retrieval_date"])
    return SourceReference(
        source_id=f"FATF-PUBLIC-LISTS-{publication.isoformat()}",
        source_name="FATF high-risk and other monitored jurisdictions",
        source_tier="tier_1",
        source_kind="official_publication",
        source_locator=registry["official_source_url"],
        as_of_date=publication,
        retrieved_at=datetime.combine(retrieval, time.min, tzinfo=timezone.utc),
        content_hash=hashlib.sha256(
            json.dumps(registry, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        effective_date_verified=True,
    )


def _fatf_record_status(
    publication_date: date,
    analysis_as_of_date: date,
    max_age_days: int,
) -> tuple[str, list[str]]:
    if max_age_days < 1:
        raise ValueError("max_age_days must be positive")
    if analysis_as_of_date < publication_date:
        raise ValueError("analysis_as_of_date cannot precede the FATF publication date")
    age_days = (analysis_as_of_date - publication_date).days
    if age_days > max_age_days:
        return "stale", [
            f"FATF snapshot is {age_days} days old, exceeding the {max_age_days}-day freshness limit."
        ]
    return "verified", []


def build_fatf_country_fact(
    country_code: str,
    *,
    analysis_as_of_date: date,
    registry_path: str | Path | None = None,
    max_age_days: int = 150,
) -> CountryRiskFact:
    registry = load_fatf_registry(registry_path)
    publication = date.fromisoformat(registry["publication_date"])
    status, country_name = _fatf_lookup(country_code, registry)
    record_status, freshness_limitations = _fatf_record_status(
        publication, analysis_as_of_date, max_age_days
    )
    code = str(country_code).strip().upper()
    interpretations = {
        "call_for_action": (
            "The FATF public statement identifies the jurisdiction as high-risk and subject "
            "to a call for action. Current enhanced-due-diligence and institutional policy "
            "requirements must be confirmed before proceeding."
        ),
        "increased_monitoring": (
            "The FATF public statement identifies the jurisdiction under increased monitoring. "
            "This is an AML/CFT screening flag, not a transaction prohibition or buyer rating."
        ),
        "not_listed_in_public_statements": (
            "The jurisdiction is not included in this snapshot's two FATF public statements. "
            "Absence from the lists does not establish low AML/CFT or transaction risk."
        ),
    }
    limitations = list(registry.get("limitations") or []) + freshness_limitations
    return CountryRiskFact(
        fact_id=_stable_id("COUNTRY", f"FATF:{publication}:{code}:{status}"),
        country_code=code,
        dimension="sanctions_aml",
        metric_name="FATF public-list status",
        value=status,
        unit=None,
        observation_date=publication,
        risk_direction="categorical",
        interpretation=interpretations[status],
        benchmark_or_threshold="FATF public statements, not a project score",
        source=_fatf_source(registry),
        record_status=record_status,
        limitations=limitations
        + ([f"Official list country name: {country_name}"] if country_name else []),
    )


def build_fatf_country_screening(
    country_code: str,
    country_name: str,
    *,
    analysis_as_of_date: date,
    registry_path: str | Path | None = None,
    max_age_days: int = 150,
) -> ComplianceScreeningResult:
    registry = load_fatf_registry(registry_path)
    publication = date.fromisoformat(registry["publication_date"])
    status, official_name = _fatf_lookup(country_code, registry)
    record_status, freshness_limitations = _fatf_record_status(
        publication, analysis_as_of_date, max_age_days
    )
    listed = status != "not_listed_in_public_statements"
    matched_entries = []
    if listed:
        matched_entries.append(
            ComplianceMatch(
                matched_name=official_name or country_name,
                list_name=(
                    "FATF high-risk jurisdictions subject to a call for action"
                    if status == "call_for_action"
                    else "FATF jurisdictions under increased monitoring"
                ),
                match_score=Decimal("1"),
                identifiers={"country_code": str(country_code).upper(), "status": status},
                source_entry_locator=registry["official_source_url"],
            )
        )
    return ComplianceScreeningResult(
        screening_id=_stable_id(
            "SCREEN", f"FATF:{publication}:{str(country_code).upper()}:{status}"
        ),
        subject_type="country",
        subject_id=str(country_code).upper(),
        subject_name=country_name,
        screening_type="aml_country",
        result="potential_match" if listed else "clear",
        method="exact",
        matched_entries=matched_entries,
        reviewed_by_human=False,
        source=_fatf_source(registry),
        record_status=record_status,
        limitations=list(registry.get("limitations") or [])
        + freshness_limitations
        + [
            "A listed-country result requires current compliance review; the system does not make an AML acceptance decision."
        ],
    )
