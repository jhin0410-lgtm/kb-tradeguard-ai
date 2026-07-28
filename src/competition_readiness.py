"""Deterministic release-readiness checks for the competition prototype.

The report verifies repository artifacts, showcase scenarios, presentation snapshots,
Gold Dataset coverage, official-data adapters, extraction-evaluation infrastructure,
public-demo entrypoints, and public-repository safety. It performs no network calls and
does not change any case, finding, calculation, or product candidate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .assessment_app_presentation import build_presentation_snapshot, scenario_narrative
from .assessment_app_v2 import build_presentation_snapshot_v2
from .competition_demo import build_competition_validation_status
from .demo_scenarios import list_demo_scenarios, load_demo_scenario
from .portfolio_demo import build_demo_company_workspace
from .intelligence.portfolio_assessment import analyze_trade_portfolio, match_portfolio_products
from .intelligence.product_matching import load_product_registry
from .intelligence.single_transaction_package import run_single_transaction_package
from .intelligence.trade_document_gold import (
    iter_semantic_preserving_gold_mutations,
    list_trade_document_gold_cases,
    load_trade_document_gold_dataset,
)
from .intelligence.trade_document_rules import load_trade_document_rule_registry
from .public_repo_safety import build_public_repo_safety_report


ROOT = Path(__file__).resolve().parents[1]

_REQUIRED_FILES = [
    ".env.example",
    ".gitignore",
    ".streamlit/config.toml",
    "LICENSE",
    "NOTICE.md",
    "README.md",
    "SECURITY.md",
    "assessment_app.py",
    "assessment_app_v2.py",
    "assessment_app_v2_mobile.py",
    "competition_app.py",
    "streamlit_app.py",
    "requirements.txt",
    "run-mobile-demo.ps1",
    "docs/assessment_demo_app.md",
    "docs/competition_demo_script.md",
    "docs/document_extraction_evaluation.md",
    "docs/korea_customs_trade_data.md",
    "docs/public_competition_demo.md",
    "docs/trade_document_gold_dataset.md",
    "docs/ui_v2_mobile.md",
    "docs/un_comtrade_preview.md",
    "examples/document_extraction_evaluation_example.json",
    "data/gold/trade_document_gold_v1.json",
    "data/reference/trade_document_rules_v1.json",
    "data/reference/trade_finance_product_registry_v2.json",
    "scripts/evaluate_document_extraction.py",
    "scripts/public_repo_safety_check.py",
    "scripts/trade_document_gold_summary.py",
    "scripts/live_ai_provider_smoke_test.py",
    "src/data_providers/kexim_fx.py",
    "src/data_providers/korea_customs_trade.py",
    "src/data_providers/un_comtrade.py",
    "src/data_providers/world_bank_country.py",
    "src/data_providers/bok_ecos.py",
    "src/data_providers/nts_business.py",
    "src/data_providers/opendart.py",
    "src/official_data_hub.py",
    "src/intelligence/portfolio_assessment.py",
    "src/portfolio_demo.py",
    "src/competition_portfolio_view.py",
    "docs/portfolio_assessment.md",
    "docs/official_data_hub.md",
    "src/intelligence/document_extraction_evaluation.py",
]

_OFFICIAL_DATA_SURFACES = {
    "kexim_fx": {
        "path": "src/data_providers/kexim_fx.py",
        "requires_secret": True,
    },
    "world_bank_country": {
        "path": "src/data_providers/world_bank_country.py",
        "requires_secret": False,
    },
    "un_comtrade_preview": {
        "path": "src/data_providers/un_comtrade.py",
        "requires_secret": False,
    },
    "korea_customs_trade": {
        "path": "src/data_providers/korea_customs_trade.py",
        "requires_secret": True,
    },
    "nts_business_status": {
        "path": "src/data_providers/nts_business.py",
        "requires_secret": True,
    },
    "opendart_company_financials": {
        "path": "src/data_providers/opendart.py",
        "requires_secret": True,
    },
    "bok_ecos": {
        "path": "src/data_providers/bok_ecos.py",
        "requires_secret": True,
    },
}


def build_competition_readiness_report() -> dict[str, Any]:
    """Return a compact, auditable local-readiness report without live API calls."""

    failures: list[str] = []
    missing_files = [path for path in _REQUIRED_FILES if not (ROOT / path).exists()]
    if missing_files:
        failures.append("Missing required repository artifacts")

    public_safety = build_public_repo_safety_report(ROOT)
    if public_safety["status"] != "safe":
        failures.append("Public repository safety review is required")

    dataset = load_trade_document_gold_dataset()
    gold_cases = list_trade_document_gold_cases()
    mutations = list(iter_semantic_preserving_gold_mutations(gold_cases))
    registry = load_trade_document_rule_registry()
    governed_rule_ids = {item.rule_id for item in registry.rules}
    covered_rule_ids = {
        rule_id for case in gold_cases for rule_id in case.expected_rule_ids
    }
    uncovered_rule_ids = sorted(governed_rule_ids - covered_rule_ids)
    unexpected_rule_ids = sorted(covered_rule_ids - governed_rule_ids)
    if uncovered_rule_ids or unexpected_rule_ids:
        failures.append("Gold Dataset Rule-ID coverage does not match the registry")

    compact_validation = build_competition_validation_status()
    if compact_validation.governed_rule_count != len(governed_rule_ids):
        failures.append("Public demo validation summary does not match the registry")

    official_data_surfaces = []
    for surface_id, contract in _OFFICIAL_DATA_SURFACES.items():
        exists = (ROOT / contract["path"]).exists()
        official_data_surfaces.append(
            {
                "surface_id": surface_id,
                "path": contract["path"],
                "adapter_present": exists,
                "requires_deployment_secret": contract["requires_secret"],
                "network_verified": False,
            }
        )
        if not exists:
            failures.append(f"Official-data adapter is missing: {surface_id}")

    product_registry = load_product_registry()
    if len(product_registry.products) < 20:
        failures.append("Trade-finance product registry does not cover the governed minimum")

    portfolio_workspace = build_demo_company_workspace()
    portfolio_results = []
    for company_id, portfolio_case in portfolio_workspace.companies.items():
        assessment = analyze_trade_portfolio(portfolio_case)
        _, product_matches = match_portfolio_products(portfolio_case)
        if assessment.transaction_count < 2:
            failures.append(f"Portfolio demo {company_id} is not multi-transaction")
        if not product_matches.product_candidates:
            failures.append(f"Portfolio demo {company_id} has no product candidates")
        portfolio_results.append(
            {
                "company_id": company_id,
                "case_id": portfolio_case.identity.case_id,
                "transaction_count": assessment.transaction_count,
                "currency_count": assessment.currency_count,
                "product_candidate_count": len(product_matches.product_candidates),
                "missing_inputs": assessment.missing_inputs,
            }
        )

    extraction_evaluation = {
        "harness_present": (
            ROOT / "src/intelligence/document_extraction_evaluation.py"
        ).exists(),
        "cli_present": (ROOT / "scripts/evaluate_document_extraction.py").exists(),
        "synthetic_format_example_present": (
            ROOT / "examples/document_extraction_evaluation_example.json"
        ).exists(),
        "external_holdout_in_repository": False,
        "external_accuracy_claim_allowed": False,
    }
    if not all(
        extraction_evaluation[key]
        for key in (
            "harness_present",
            "cli_present",
            "synthetic_format_example_present",
        )
    ):
        failures.append("Document-extraction evaluation infrastructure is incomplete")

    scenario_results = []
    for metadata in list_demo_scenarios():
        package = load_demo_scenario(metadata.scenario_id)
        run = run_single_transaction_package(package)
        actual_disposition = run.assessment_result.brief.disposition
        narrative = scenario_narrative(metadata.scenario_id)
        snapshot_v1 = build_presentation_snapshot(run, scenario_id=metadata.scenario_id)
        snapshot_v2 = build_presentation_snapshot_v2(run, scenario_id=metadata.scenario_id)
        matches = actual_disposition == metadata.expected_disposition
        if not matches:
            failures.append(
                f"Scenario {metadata.scenario_id} disposition changed from its governed expectation"
            )
        if narrative is None:
            failures.append(
                f"Scenario {metadata.scenario_id} has no presentation narrative"
            )
        if snapshot_v2["view_contract"] != "risk_first_60_second_brief":
            failures.append(
                f"Scenario {metadata.scenario_id} has an invalid V2 presentation contract"
            )
        scenario_results.append(
            {
                "scenario_id": metadata.scenario_id,
                "expected_disposition": metadata.expected_disposition,
                "actual_disposition": actual_disposition,
                "matches_expected": matches,
                "input_package_hash": run.input_package_hash,
                "output_case_hash": run.output_case_hash,
                "stage_count": len(run.assessment_result.stage_traces),
                "presentation_snapshot_version": snapshot_v1["snapshot_version"],
                "presentation_snapshot_v2_version": snapshot_v2["snapshot_version"],
                "presentation_v2_top_risk_count": len(snapshot_v2["top_risks"]),
            }
        )

    return {
        "report_version": "competition-readiness/1.5",
        "status": "ready" if not failures else "not_ready",
        "network_calls": "none",
        "public_demo_entrypoint": "streamlit_app.py",
        "public_demo_data_mode": (
            "synthetic_transaction_and_portfolio_with_read_only_official_context"
        ),
        "required_file_count": len(_REQUIRED_FILES),
        "missing_files": missing_files,
        "public_repo_safety_status": public_safety["status"],
        "public_repo_safety_finding_count": public_safety["finding_count"],
        "official_data_surfaces": official_data_surfaces,
        "no_secret_official_data_surface_count": sum(
            not item["requires_deployment_secret"] for item in official_data_surfaces
        ),
        "secret_required_official_data_surface_count": sum(
            item["requires_deployment_secret"] for item in official_data_surfaces
        ),
        "official_data_network_verified": False,
        "product_registry_version": product_registry.registry_version,
        "product_registry_product_count": len(product_registry.products),
        "portfolio_company_count": len(portfolio_results),
        "portfolio_results": portfolio_results,
        "document_extraction_evaluation": extraction_evaluation,
        "demo_scenario_count": len(scenario_results),
        "scenario_results": scenario_results,
        "gold_dataset_version": dataset["dataset_version"],
        "gold_case_count": len(gold_cases),
        "mutation_case_count": len(mutations),
        "governed_rule_count": len(governed_rule_ids),
        "covered_rule_count": len(covered_rule_ids),
        "uncovered_rule_ids": uncovered_rule_ids,
        "unexpected_rule_ids": unexpected_rule_ids,
        "failures": failures,
        "authority_boundary": (
            "Readiness means repository artifacts, deterministic fixtures, official-data adapter "
            "contracts, and the extraction-evaluation harness are internally consistent, while "
            "the current working tree passed the local credential-pattern scan. This offline check "
            "does not prove live API availability, external holdout accuracy, repository-history "
            "erasure, legal correctness, bank approval, K-SURE acceptance, compliance clearance, "
            "or production deployment readiness."
        ),
    }
