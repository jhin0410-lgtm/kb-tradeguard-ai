from src.competition_case_study_view import build_official_case_study_summaries
from src.official_case_studies import load_pinned_official_context_dataset


def test_pinned_official_context_dataset_has_three_real_public_cases():
    dataset = load_pinned_official_context_dataset()

    assert dataset.dataset_version == "official-context-snapshots/1.0"
    assert len(dataset.cases) == 3
    assert len({case.case_id for case in dataset.cases}) == 3
    assert all(len(source.response_hash) == 64 for case in dataset.cases for source in case.sources)
    assert all(source.payload for case in dataset.cases for source in case.sources)


def test_case_study_summaries_preserve_observation_years_and_trade_values():
    summaries = {item["case_id"]: item for item in build_official_case_study_summaries()}

    vietnam = summaries["VN-ELECTRONICS-EXPORT-CONTEXT"]
    united_states = summaries["US-COSMETICS-EXPORT-CONTEXT"]
    japan = summaries["JP-MACHINERY-IMPORT-CONTEXT"]

    assert vietnam["trade_value_usd"] == 36046410320
    assert united_states["trade_value_usd"] == 1830509584
    assert japan["trade_value_usd"] == 8782011825
    assert vietnam["flow_label"] == "수출"
    assert japan["flow_label"] == "수입"

    vietnam_metrics = {item["indicator_code"]: item for item in vietnam["metrics"]}
    assert vietnam_metrics["NY.GDP.MKTP.KD.ZG"]["observation_year"] == 2025
    assert vietnam_metrics["FI.RES.TOTL.MO"]["observation_year"] == 2024
    assert all(item["macro_response_hash"] for item in summaries.values())
    assert all(item["trade_response_hash"] for item in summaries.values())
