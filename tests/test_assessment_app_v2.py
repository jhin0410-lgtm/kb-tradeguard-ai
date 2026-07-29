import assessment_app_v2

from src.assessment_app_v2 import (
    build_evidence_drawer_items,
    build_presentation_snapshot_v2,
    build_reference_index,
    build_risk_first_summary,
    render_presentation_snapshot_html,
)
from src.demo_scenarios import load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


def _run():
    return run_single_transaction_package(load_demo_scenario("oa_high_risk"))


def test_v2_risk_first_summary_is_compact_and_governed():
    run = _run()

    summary = build_risk_first_summary(run)

    assert summary.disposition == "conditions_required_before_commitment"
    assert 1 <= len(summary.top_risks) <= 3
    assert len(summary.next_actions) <= 3
    assert summary.stage_count == 5
    assert summary.completed_stage_count <= summary.stage_count
    assert summary.evidence_reference_count == len(
        {
            reference_id
            for risk in summary.top_risks
            for reference_id in risk.reference_ids
        }
    )


def test_v2_evidence_drawer_resolves_direct_and_linked_records():
    run = _run()
    summary = build_risk_first_summary(run)
    reference_ids = summary.top_risks[0].reference_ids

    index = build_reference_index(run)
    items = build_evidence_drawer_items(run, reference_ids, include_linked=True)

    assert all(reference_id in index for reference_id in reference_ids)
    assert items
    assert {item.reference_id for item in items} >= set(reference_ids)
    assert all(item.title and item.summary and item.status for item in items)


def test_v2_presentation_snapshot_and_html_are_mobile_ready():
    run = _run()

    snapshot = build_presentation_snapshot_v2(run, scenario_id="oa_high_risk")
    html = render_presentation_snapshot_html(snapshot)

    assert snapshot["snapshot_version"] == "competition-presentation/2.0"
    assert snapshot["view_contract"] == "risk_first_60_second_brief"
    assert snapshot["mobile_compact_query"] == "?view=compact"
    assert len(snapshot["input_package_hash"]) == 64
    assert len(snapshot["output_case_hash"]) == 64
    assert "<meta name=\"viewport\"" in html
    assert "@media(max-width:760px)" in html
    assert "RISK-FIRST 60 SECOND BRIEF" in html


def test_v2_streamlit_entrypoint_has_responsive_and_evidence_components():
    css = assessment_app_v2.V2_CSS

    assert callable(assessment_app_v2.main)
    assert ".v2-risk-card" in css
    assert ".v2-evidence" in css
    assert "@media (max-width: 640px)" in css
    assert "http://" not in css
    assert "https://" not in css
