"""Deterministic release-readiness checks for the competition prototype.

The report verifies repository artifacts, showcase scenarios, presentation snapshots,
Gold Dataset coverage, and public-repository safety. It performs no network calls and
does not change any case, finding, calculation, or product candidate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .assessment_app_presentation import build_presentation_snapshot, scenario_narrative
from .assessment_app_v2 import build_presentation_snapshot_v2
from .demo_scenarios import list_demo_scenarios, load_demo_scenario
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
    "LICENSE",
    "NOTICE.md",
    "README.md",
    "SECURITY.md",
    "assessment_app.py",
    "assessment_app_v2.py",
    "requirements.txt",
    "run-mobile-demo.ps1",
    "docs/assessment_demo_app.md",
    "docs/competition_demo_script.md",
    "docs/trade_document_gold_dataset.md",
    "docs/ui_v2_mobile.md",
    "data/gold/trade_document_gold_v1.json",
    "data/reference/trade_document_rules_v1.json",
    "scripts/public_repo_safety_check.py",
    "scripts/trade_document_gold_summary.py",
    "scripts/live_ai_provider_smoke_test.py",
]


def build_competition_readiness_report() -> dict[str, Any]:
    """Return a compact, auditable local-readiness report."""

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
        "report_version": "competition-readiness/1.2",
        "status": "ready" if not failures else "not_ready",
        "network_calls": "none",
        "required_file_count": len(_REQUIRED_FILES),
        "missing_files": missing_files,
        "public_repo_safety_status": public_safety["status"],
        "public_repo_safety_finding_count": public_safety["finding_count"],
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
            "Readiness means the local prototype artifacts and governed deterministic fixtures "
            "are internally consistent and the current working tree passed the local credential-pattern scan. "
            "It does not establish repository-history erasure, legal correctness, bank approval, K-SURE "
            "acceptance, compliance clearance, or production deployment readiness."
        ),
    }
