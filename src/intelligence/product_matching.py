"""Evidence-grounded trade-finance product consultation matching.

The matcher maps explicitly declared financing and risk-management needs to a reviewed
public product registry.  It never predicts approval, pricing, limits, suitability, or
institution-specific credit and insurance decisions.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..copilot_case import UnifiedCopilotCase
from ..trade_finance_domain import (
    ConsultationRequirement,
    ProductCandidate,
    SourceReference,
)

NeedCode = Literal[
    "buyer_credit_investigation",
    "export_receivable_nonpayment_protection",
    "pre_shipment_working_capital",
    "post_shipment_receivables_financing",
    "fx_cashflow_certainty",
    "import_working_capital",
    "import_advance_payment_protection",
    "export_working_capital",
]
TransactionDirection = Literal["export", "import"]
TransactionStage = Literal[
    "pre_contract", "pre_shipment", "post_shipment", "pre_payment", "ongoing"
]
CompanySize = Literal["sme", "mid_market", "large", "unknown"]
ProductCategory = Literal[
    "buyer_credit_investigation",
    "trade_credit_insurance",
    "export_guarantee_pre_shipment",
    "export_guarantee_post_shipment",
    "receivables_financing",
    "working_capital",
    "import_finance",
    "foreign_exchange_hedging",
    "other",
]
ConsultationRoute = Literal[
    "bank_relationship_manager",
    "trade_finance_specialist",
    "foreign_exchange_specialist",
    "ksure",
    "legal",
    "customs",
    "logistics",
    "other",
]


class RegistryOfficialSource(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_id: str
    provider: str
    source_name: str
    source_url: str


class ProductRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: str
    provider: str
    product_name: str
    product_category: ProductCategory
    need_codes: list[NeedCode]
    transaction_directions: list[TransactionDirection]
    transaction_stages: list[TransactionStage]
    company_sizes: list[CompanySize]
    max_tenor_days: int | None = Field(default=None, ge=0)
    required_industry_tags_any: list[str] = Field(default_factory=list)
    supported_banks: list[str] = Field(default_factory=list)
    public_conditions: list[str] = Field(default_factory=list)
    unresolved_conditions: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    next_action: str
    consultation_route: ConsultationRoute
    official_source_ids: list[str]

    @model_validator(mode="after")
    def lists_are_nonempty_and_unique(self):
        required_nonempty = {
            "need_codes": self.need_codes,
            "transaction_directions": self.transaction_directions,
            "transaction_stages": self.transaction_stages,
            "company_sizes": self.company_sizes,
            "official_source_ids": self.official_source_ids,
        }
        for label, values in required_nonempty.items():
            if not values:
                raise ValueError(f"Product registry field {label} must not be empty")
            if len(values) != len(set(values)):
                raise ValueError(f"Product registry field {label} must be unique")
        return self


class TradeFinanceProductRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    registry_name: str
    registry_version: str
    effective_date: date
    authority_boundary: str
    official_sources: list[RegistryOfficialSource]
    products: list[ProductRegistryEntry]

    @model_validator(mode="after")
    def identifiers_and_source_links_are_valid(self):
        source_ids = [item.source_id for item in self.official_sources]
        product_ids = [item.product_id for item in self.products]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Official product source IDs must be unique")
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Trade-finance product IDs must be unique")
        known_sources = set(source_ids)
        unknown = sorted(
            {
                source_id
                for product in self.products
                for source_id in product.official_source_ids
                if source_id not in known_sources
            }
        )
        if unknown:
            raise ValueError("Products cite unknown official source IDs: " + ", ".join(unknown))
        return self


class TradeFinanceNeedProfile(BaseModel):
    """Explicit customer need and transaction context used for pre-screening only."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    profile_id: str
    transaction_id: str
    transaction_direction: TransactionDirection
    transaction_stage: TransactionStage
    declared_needs: list[NeedCode]
    company_size: CompanySize = "unknown"
    payment_method: str | None = None
    tenor_days: int | None = Field(default=None, ge=0)
    preferred_bank: str | None = None
    industry_tags: list[str] = Field(default_factory=list)
    available_documents: list[str] = Field(default_factory=list)

    @field_validator("declared_needs")
    @classmethod
    def needs_are_nonempty_and_unique(cls, value: list[NeedCode]) -> list[NeedCode]:
        if not value:
            raise ValueError("At least one declared trade-finance need is required")
        if len(value) != len(set(value)):
            raise ValueError("Declared trade-finance needs must be unique")
        return value

    @field_validator("industry_tags", "available_documents")
    @classmethod
    def normalized_lists_are_unique(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Profile list values must be unique")
        return normalized


class ProductMatchingResult(BaseModel):
    registry_version: str
    profile_ids: list[str] = Field(default_factory=list)
    product_candidates: list[ProductCandidate] = Field(default_factory=list)
    consultation_requirements: list[ConsultationRequirement] = Field(default_factory=list)


class ProductMatchingOutcome(BaseModel):
    case_before_hash: str
    case_after_hash: str
    profile_ids: list[str] = Field(default_factory=list)
    product_candidate_ids: list[str] = Field(default_factory=list)
    consultation_requirement_ids: list[str] = Field(default_factory=list)
    status_counts: dict[str, int] = Field(default_factory=dict)


def default_product_registry_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "reference"
        / "trade_finance_product_registry_v1.json"
    )


def load_product_registry(
    path: str | Path | None = None,
) -> TradeFinanceProductRegistry:
    registry_path = Path(path) if path is not None else default_product_registry_path()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load trade-finance product registry: {registry_path}") from exc
    return TradeFinanceProductRegistry.model_validate(payload)


def _registry_source(
    registry: TradeFinanceProductRegistry,
    path: Path,
) -> SourceReference:
    return SourceReference(
        source_id=f"TRADE-FINANCE-PRODUCTS-{registry.registry_version}",
        source_name=registry.registry_name,
        source_tier="derived",
        source_kind="project_rule",
        source_locator=path.as_posix(),
        as_of_date=registry.effective_date,
        content_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
        effective_date_verified=True,
    )


def _normalize_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^0-9a-z가-힣]+", "", normalized)


_BANK_ALIASES = {
    "국민은행": "kb국민은행",
    "kb국민은행": "kb국민은행",
    "kbkookminbank": "kb국민은행",
    "kookminbank": "kb국민은행",
    "신한은행": "신한은행",
    "shinhanbank": "신한은행",
    "하나은행": "하나은행",
    "hanabank": "하나은행",
    "토스뱅크": "토스뱅크",
    "tossbank": "토스뱅크",
}


def canonical_bank_name(value: str) -> str:
    token = _normalize_token(value)
    return _BANK_ALIASES.get(token, token)


def _candidate_id(product: ProductRegistryEntry, profile: TradeFinanceNeedProfile) -> str:
    return f"PRODUCT-{product.product_id}-{profile.profile_id}"


def _requirement_id(product: ProductRegistryEntry, profile: TradeFinanceNeedProfile) -> str:
    return f"CONSULT-{product.product_id}-{profile.profile_id}"


def _match_one_product(
    product: ProductRegistryEntry,
    profile: TradeFinanceNeedProfile,
    registry: TradeFinanceProductRegistry,
    source: SourceReference,
) -> tuple[ProductCandidate, ConsultationRequirement | None] | None:
    matched_needs = sorted(set(product.need_codes) & set(profile.declared_needs))
    if not matched_needs:
        return None
    if profile.transaction_direction not in product.transaction_directions:
        return None
    if profile.transaction_stage not in product.transaction_stages:
        return None

    match_reasons = [
        f"Declared need '{need}' maps to this public product purpose."
        for need in matched_needs
    ]
    match_reasons.extend(
        [
            f"Transaction direction '{profile.transaction_direction}' is within the registry scope.",
            f"Transaction stage '{profile.transaction_stage}' is within the registry scope.",
        ]
    )
    verified_conditions = list(product.public_conditions)
    unresolved = list(product.unresolved_conditions)
    disqualifying: list[str] = []
    missing_inputs: list[str] = []
    status: Literal[
        "consultation_candidate", "insufficient_information", "not_applicable", "blocked"
    ] = "consultation_candidate"

    if profile.company_size not in product.company_sizes:
        if profile.company_size == "unknown":
            missing_inputs.append(
                "기업규모가 공개 지원대상 범주에 해당하는지 확인이 필요함"
            )
            status = "insufficient_information"
        else:
            disqualifying.append(
                f"공개 지원대상 기업규모 {product.company_sizes}에 '{profile.company_size}'가 포함되지 않음"
            )
            status = "not_applicable"
    else:
        verified_conditions.append(
            f"Declared company size '{profile.company_size}' is within the registry scope."
        )

    if product.max_tenor_days is not None:
        if profile.tenor_days is None:
            missing_inputs.append(
                f"공개 최대 결제·대출기간 {product.max_tenor_days}일과 비교할 실제 기간"
            )
            if status == "consultation_candidate":
                status = "insufficient_information"
        elif profile.tenor_days > product.max_tenor_days:
            disqualifying.append(
                f"Declared tenor {profile.tenor_days} days exceeds the public maximum of {product.max_tenor_days} days."
            )
            status = "not_applicable"
        else:
            verified_conditions.append(
                f"Declared tenor {profile.tenor_days} days does not exceed the public maximum of {product.max_tenor_days} days."
            )

    if product.required_industry_tags_any:
        declared_tags = set(profile.industry_tags)
        required_tags = set(product.required_industry_tags_any)
        if not declared_tags:
            missing_inputs.append(
                "공개 업종요건 확인을 위한 기업 업종과 수입품목 분류"
            )
            if status == "consultation_candidate":
                status = "insufficient_information"
        elif not declared_tags.intersection(required_tags):
            disqualifying.append(
                "Declared industry tags do not match the public target categories: "
                + ", ".join(product.required_industry_tags_any)
            )
            status = "not_applicable"
        else:
            verified_conditions.append(
                "Declared industry context intersects the public target categories."
            )

    if product.supported_banks:
        supported = {canonical_bank_name(item) for item in product.supported_banks}
        if profile.preferred_bank:
            preferred = canonical_bank_name(profile.preferred_bank)
            if preferred not in supported:
                disqualifying.append(
                    f"Declared preferred bank '{profile.preferred_bank}' is not in the public channel list: "
                    + ", ".join(product.supported_banks)
                )
                status = "blocked"
            else:
                verified_conditions.append(
                    f"Declared preferred bank '{profile.preferred_bank}' matches the public channel list."
                )
        elif product.provider == "K-SURE" and len(product.supported_banks) > 1:
            missing_inputs.append(
                "공식 취급은행 목록 중 실제 이용할 금융기관 선택"
            )
            if status == "consultation_candidate":
                status = "insufficient_information"

    available_document_tokens = {
        _normalize_token(item) for item in profile.available_documents
    }
    missing_documents = [
        document
        for document in product.required_documents
        if _normalize_token(document) not in available_document_tokens
    ]
    if missing_documents:
        unresolved.append(
            "상담 전 준비 필요서류: " + "; ".join(missing_documents)
        )
        missing_inputs.extend(missing_documents)

    if missing_inputs:
        unresolved.extend(item for item in missing_inputs if item not in unresolved)

    record_status = "partial" if status == "insufficient_information" else "verified"
    candidate = ProductCandidate(
        product_candidate_id=_candidate_id(product, profile),
        provider=product.provider,
        product_or_service_name=product.product_name,
        product_category=product.product_category,
        matched_need=", ".join(matched_needs),
        candidate_status=status,
        match_reasons=match_reasons,
        verified_public_conditions=verified_conditions,
        unresolved_eligibility_conditions=unresolved,
        disqualifying_conditions=disqualifying,
        required_documents=list(product.required_documents),
        official_source_ids=list(product.official_source_ids),
        source_effective_date=registry.effective_date,
        next_action=product.next_action,
        source=source,
        record_status=record_status,
        limitations=[
            registry.authority_boundary,
            "The match is based on declared needs and reviewed public conditions, not an institutional decision.",
            "Official product terms and availability must be rechecked at consultation time.",
        ],
    )

    requirement = None
    if status in {"consultation_candidate", "insufficient_information"}:
        requirement = ConsultationRequirement(
            requirement_id=_requirement_id(product, profile),
            consultation_route=product.consultation_route,
            purpose=(
                f"Confirm current conditions and eligibility for {product.product_name} "
                f"in relation to transaction {profile.transaction_id}."
            ),
            questions_to_confirm=list(dict.fromkeys(unresolved)),
            required_documents=list(product.required_documents),
            blocked_by_missing_inputs=list(dict.fromkeys(missing_inputs)),
            source=source,
            record_status=record_status,
            limitations=[registry.authority_boundary],
        )
    return candidate, requirement


def match_trade_finance_products(
    profiles: list[TradeFinanceNeedProfile],
    *,
    registry_path: str | Path | None = None,
) -> ProductMatchingResult:
    """Generate consultation candidates from explicit need profiles."""

    profile_ids = [profile.profile_id for profile in profiles]
    if len(profile_ids) != len(set(profile_ids)):
        raise ValueError("Trade-finance need profile IDs must be unique")

    resolved_path = (
        Path(registry_path) if registry_path is not None else default_product_registry_path()
    )
    registry = load_product_registry(resolved_path)
    source = _registry_source(registry, resolved_path)
    candidates: list[ProductCandidate] = []
    requirements: list[ConsultationRequirement] = []

    for profile in profiles:
        for product in registry.products:
            matched = _match_one_product(product, profile, registry, source)
            if matched is None:
                continue
            candidate, requirement = matched
            candidates.append(candidate)
            if requirement is not None:
                requirements.append(requirement)

    return ProductMatchingResult(
        registry_version=registry.registry_version,
        profile_ids=profile_ids,
        product_candidates=candidates,
        consultation_requirements=requirements,
    )


def apply_product_matching(
    case: UnifiedCopilotCase,
    profiles: list[TradeFinanceNeedProfile],
    *,
    registry_path: str | Path | None = None,
) -> tuple[UnifiedCopilotCase, ProductMatchingOutcome]:
    """Replace current registry-derived candidates while preserving other case records."""

    approved_transactions = {
        str(item.get("transaction_id")): str(item.get("transaction_type"))
        for item in case.approved_transactions
        if item.get("transaction_id") is not None
    }
    missing_transactions = sorted(
        {
            profile.transaction_id
            for profile in profiles
            if profile.transaction_id not in approved_transactions
        }
    )
    if missing_transactions:
        raise ValueError(
            "Product matching profiles reference unknown approved transactions: "
            + ", ".join(missing_transactions)
        )

    direction_conflicts = sorted(
        {
            f"{profile.transaction_id}: case={approved_transactions[profile.transaction_id]}, profile={profile.transaction_direction}"
            for profile in profiles
            if approved_transactions[profile.transaction_id] != profile.transaction_direction
        }
    )
    if direction_conflicts:
        raise ValueError(
            "Product matching profile direction conflicts with approved transaction data: "
            + "; ".join(direction_conflicts)
        )

    resolved_path = (
        Path(registry_path) if registry_path is not None else default_product_registry_path()
    )
    registry = load_product_registry(resolved_path)
    source_id = _registry_source(registry, resolved_path).source_id
    result = match_trade_finance_products(profiles, registry_path=resolved_path)

    retained_candidates = [
        item
        for item in case.trade_finance.product_candidates
        if item.source.source_id != source_id
    ]
    retained_requirements = [
        item
        for item in case.trade_finance.consultation_requirements
        if item.source.source_id != source_id
    ]
    updated_domain = case.trade_finance.model_copy(
        update={
            "product_candidates": retained_candidates + result.product_candidates,
            "consultation_requirements": (
                retained_requirements + result.consultation_requirements
            ),
        }
    )
    updated_case = case.model_copy(update={"trade_finance": updated_domain})
    status_counts: dict[str, int] = {}
    for candidate in result.product_candidates:
        status_counts[candidate.candidate_status] = (
            status_counts.get(candidate.candidate_status, 0) + 1
        )
    outcome = ProductMatchingOutcome(
        case_before_hash=case.case_hash,
        case_after_hash=updated_case.case_hash,
        profile_ids=result.profile_ids,
        product_candidate_ids=[
            item.product_candidate_id for item in result.product_candidates
        ],
        consultation_requirement_ids=[
            item.requirement_id for item in result.consultation_requirements
        ],
        status_counts=status_counts,
    )
    return updated_case, outcome
