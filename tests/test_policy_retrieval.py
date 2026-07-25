from datetime import date

from src.policy_retrieval import BundledPolicyRetriever


def test_retrieval_searches_approved_manifest_and_preserves_metadata():
    retriever = BundledPolicyRetriever("data/policy_docs")
    results = retriever.search("은행 상담 필요 서류 송장 결제조건", limit=3)
    assert results
    first = results[0]
    assert first.document_id
    assert first.excerpt
    assert first.citation.source_url.startswith("https://")
    assert first.citation.retrieval_date == "2026-07-25"
    assert first.citation.format().startswith("[")
    assert first.information_boundary.startswith("General information")


def test_missing_effective_date_and_staleness_are_warned():
    result = BundledPolicyRetriever("data/policy_docs").search(
        "trade finance", limit=1, as_of_date=date(2028, 1, 1)
    )[0]
    assert "Official effective date is not stated" in result.citation.stale_warning
    assert "not been independently verified" in result.citation.stale_warning
    assert "more than 365 days old" in result.citation.stale_warning
