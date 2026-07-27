from src.demo_scenarios import list_demo_scenarios, load_demo_scenario
from src.intelligence.single_transaction_package import run_single_transaction_package


def test_demo_scenario_catalog_is_unique_and_covers_key_dispositions():
    scenarios = list_demo_scenarios()

    assert len(scenarios) == 4
    assert len({item.scenario_id for item in scenarios}) == len(scenarios)
    assert {item.expected_disposition for item in scenarios} == {
        "additional_information_required",
        "conditions_required_before_commitment",
        "specialist_clearance_required",
        "no_material_screening_flags",
    }
    assert all(item.source_modes for item in scenarios)


def test_demo_packages_are_deterministic_and_match_expected_dispositions():
    for metadata in list_demo_scenarios():
        first = load_demo_scenario(metadata.scenario_id)
        second = load_demo_scenario(metadata.scenario_id)

        assert first.package_hash == second.package_hash
        assert first.case.case_hash == second.case.case_hash

        run = run_single_transaction_package(first)
        assert run.assessment_result.brief.disposition == metadata.expected_disposition
        assert len(run.assessment_result.stage_traces) == 5
        assert run.output_case_hash == run.updated_case.case_hash
        assert "approve" not in run.assessment_result.authority_boundary.casefold()


def test_unknown_demo_scenario_is_rejected():
    try:
        load_demo_scenario("not-a-scenario")
    except KeyError as exc:
        assert "Unknown demo scenario" in str(exc)
    else:
        raise AssertionError("Unknown scenario should raise KeyError")
