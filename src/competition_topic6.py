"""Topic-six competition fixture preparation.

The public demonstration explicitly includes an FX-cashflow consultation need so the
product and hedge-information surfaces are visible. This is a fixture declaration,
not an inference that every foreign-currency customer should execute a hedge.
"""

from __future__ import annotations

from .intelligence.product_matching import TradeFinanceNeedProfile
from .intelligence.single_transaction_package import SingleTransactionAssessmentPackage


def prepare_topic6_demo_package(
    package: SingleTransactionAssessmentPackage,
) -> SingleTransactionAssessmentPackage:
    """Add one explicit FX consultation profile to a foreign-currency demo transaction."""

    transaction = package.case.approved_transactions[0]
    currency = str(transaction.get("currency") or "").strip().upper()
    profiles = list(package.request.product_profiles)
    if currency in {"", "KRW"} or any(
        "fx_cashflow_certainty" in profile.declared_needs for profile in profiles
    ):
        return package

    if profiles:
        template = profiles[0]
        fx_profile = TradeFinanceNeedProfile(
            profile_id=f"{template.profile_id}-FX",
            transaction_id=template.transaction_id,
            transaction_direction=template.transaction_direction,
            transaction_stage=template.transaction_stage,
            declared_needs=["fx_cashflow_certainty"],
            company_size=template.company_size,
            payment_method=template.payment_method,
            tenor_days=template.tenor_days,
            preferred_bank=template.preferred_bank,
            industry_tags=list(template.industry_tags),
            available_documents=list(template.available_documents),
        )
    else:
        fx_profile = TradeFinanceNeedProfile(
            profile_id=f"NEED-{package.request.transaction_id}-FX",
            transaction_id=package.request.transaction_id,
            transaction_direction=str(transaction.get("transaction_type")),
            transaction_stage="ongoing",
            declared_needs=["fx_cashflow_certainty"],
            company_size="unknown",
        )

    updated_request = package.request.model_copy(
        update={"product_profiles": [*profiles, fx_profile]}
    )
    return package.model_copy(
        update={
            "request": updated_request,
            "notes": [
                *package.notes,
                (
                    "Competition fixture explicitly requests an FX-cashflow consultation "
                    "comparison; this does not assert hedge suitability or execution."
                ),
            ],
        }
    )
