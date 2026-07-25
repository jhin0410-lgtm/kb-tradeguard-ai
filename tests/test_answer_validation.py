from src.advisor_models import AdvisoryAnswer, IntentClassification, NumericalClaim
from src.answer_validation import validate_advisory_answer
from src.citation_models import CalculationCitation, DocumentCitation

INTENT = IntentClassification(
    primary_intent="fx_exposure",
    required_tools=["get_exposure_by_currency"],
    confidence=1,
)


def _answer(text, calculations=None, documents=None, claims=None):
    return AdvisoryAnswer(
        provider_mode="test",
        intent=INTENT,
        direct_answer=text,
        calculations_used=calculations or [],
        documents_used=documents or [],
        numerical_claims=claims or [],
        risk_notice="Professional review required.",
    )


def test_uncited_numerical_claim_fails():
    report = validate_advisory_answer(_answer("Expected exposure is USD 225,000."))
    assert not report.validation_result
    assert any("Uncited numerical claim" in error for error in report.errors)


def test_cited_structured_numerical_claim_passes():
    citation = CalculationCitation(
        calculation_id="CALC-EXP-ABC123",
        calculation_name="Exposure",
    )
    claim = NumericalClaim(
        description="Expected exposure",
        value=225000,
        unit="USD",
        calculation_id="CALC-EXP-ABC123",
        analysis_basis="Expected transaction exposure",
        as_of_date="2026-08-31",
    )
    report = validate_advisory_answer(
        _answer(
            "Expected exposure is USD 225,000 (CALC-EXP-ABC123).",
            [citation],
            claims=[claim],
        )
    )
    assert report.validation_result


def test_policy_claim_without_document_fails_and_citation_passes():
    failed = validate_advisory_answer(_answer("Export financing can be reviewed."))
    assert not failed.validation_result
    document = DocumentCitation(
        document_id="DOC-1",
        title="Guide",
        excerpt_id="working-capital",
        issuing_organization="Official organization",
        retrieval_date="2026-07-25",
        source_url="https://example.gov",
    )
    passed = validate_advisory_answer(
        _answer(
            "Export financing can be reviewed [DOC-1, Guide, working-capital].",
            documents=[document],
        )
    )
    assert passed.validation_result


def test_actual_quote_eligibility_approval_and_guarantees_fail():
    for text in (
        "This theoretical forward is an actual KB quote.",
        "You are eligible for this product.",
        "대출이 승인됩니다.",
        "손실이 발생하지 않습니다.",
    ):
        assert not validate_advisory_answer(_answer(text)).validation_result


def test_policy_document_record_without_inline_citation_still_fails():
    document = DocumentCitation(
        document_id="DOC-1",
        title="Guide",
        excerpt_id="working-capital",
        issuing_organization="Official organization",
        retrieval_date="2026-07-25",
        source_url="https://example.gov",
    )
    report = validate_advisory_answer(
        _answer("Export financing can be reviewed.", documents=[document])
    )
    assert not report.validation_result
    assert any("inline citation" in error for error in report.errors)


def test_selected_cashflow_view_and_hedge_basis_contradictions_fail():
    cash_intent = IntentClassification(
        primary_intent="cashflow_risk",
        required_tools=["get_cashflow_view"],
        extracted_parameters={"cash_flow_view": "expected"},
        confidence=1,
    )
    hedge_intent = IntentClassification(
        primary_intent="hedge_comparison",
        required_tools=["compare_hedge_ratios"],
        extracted_parameters={"analysis_basis": "Expected transaction exposure"},
        confidence=1,
    )
    citation = CalculationCitation(
        calculation_id="CALC-TEST-1",
        calculation_name="Test",
    )
    cash_answer = _answer(
        "Shortfall is KRW 1 (CALC-TEST-1).",
        calculations=[citation],
        claims=[
            NumericalClaim(
                description="Shortfall",
                value=1,
                unit="KRW",
                calculation_id="CALC-TEST-1",
                analysis_basis="confirmed cash-flow view",
            )
        ],
    ).model_copy(update={"intent": cash_intent})
    hedge_answer = _answer(
        "Value is KRW 1 (CALC-TEST-1).",
        calculations=[citation],
        claims=[
            NumericalClaim(
                description="Value",
                value=1,
                unit="KRW",
                calculation_id="CALC-TEST-1",
                analysis_basis="Nominal transaction exposure",
            )
        ],
    ).model_copy(update={"intent": hedge_intent})
    assert not validate_advisory_answer(cash_answer).validation_result
    assert not validate_advisory_answer(hedge_answer).validation_result
