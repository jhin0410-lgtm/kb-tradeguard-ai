from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match in {path}, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def append_once(path: str, marker: str, addition: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if marker in text:
        raise RuntimeError(f"Patch marker already exists in {path}: {marker}")
    target.write_text(text.rstrip() + "\n\n\n" + addition.strip() + "\n", encoding="utf-8")


replace_once(
    "src/trade_finance_domain.py",
    '''class ProductCandidate(EvidenceBackedRecord):
    """A consultation candidate, never an eligibility or approval decision."""

    product_candidate_id: str
    provider: str
''',
    '''class ProductCandidate(EvidenceBackedRecord):
    """A consultation candidate, never an eligibility or approval decision."""

    product_candidate_id: str
    linked_transaction_ids: list[str] = Field(default_factory=list)
    provider: str
''',
)
replace_once(
    "src/trade_finance_domain.py",
    '''class ConsultationRequirement(EvidenceBackedRecord):
    requirement_id: str
    consultation_route: Literal[
''',
    '''class ConsultationRequirement(EvidenceBackedRecord):
    requirement_id: str
    linked_transaction_ids: list[str] = Field(default_factory=list)
    consultation_route: Literal[
''',
)

replace_once(
    "src/intelligence/product_matching.py",
    '''    candidate = ProductCandidate(
        product_candidate_id=_candidate_id(product, profile),
        provider=product.provider,
''',
    '''    candidate = ProductCandidate(
        product_candidate_id=_candidate_id(product, profile),
        linked_transaction_ids=[profile.transaction_id],
        provider=product.provider,
''',
)
replace_once(
    "src/intelligence/product_matching.py",
    '''        requirement = ConsultationRequirement(
            requirement_id=_requirement_id(product, profile),
            consultation_route=product.consultation_route,
''',
    '''        requirement = ConsultationRequirement(
            requirement_id=_requirement_id(product, profile),
            linked_transaction_ids=[profile.transaction_id],
            consultation_route=product.consultation_route,
''',
)

replace_once(
    "src/intelligence/transaction_decision_brief.py",
    '''def _select_by_ids(records: list, ids: list[str], attribute: str, label: str) -> list:
    by_id = {getattr(item, attribute): item for item in records}
    missing = [identifier for identifier in ids if identifier not in by_id]
    if missing:
        raise ValueError(f"Unknown {label} IDs: " + ", ".join(missing))
    return [by_id[identifier] for identifier in ids]


''',
    '''def _select_by_ids(records: list, ids: list[str], attribute: str, label: str) -> list:
    by_id = {getattr(item, attribute): item for item in records}
    missing = [identifier for identifier in ids if identifier not in by_id]
    if missing:
        raise ValueError(f"Unknown {label} IDs: " + ", ".join(missing))
    return [by_id[identifier] for identifier in ids]


def _select_transaction_linked_by_ids(
    records: list,
    ids: list[str],
    attribute: str,
    label: str,
    transaction_id: str,
) -> list:
    selected = _select_by_ids(records, ids, attribute, label)
    mismatched = [
        getattr(item, attribute)
        for item in selected
        if transaction_id not in item.linked_transaction_ids
    ]
    if mismatched:
        raise ValueError(
            f"Selected {label} IDs are not linked to transaction {transaction_id}: "
            + ", ".join(mismatched)
        )
    return selected


''',
)
replace_once(
    "src/intelligence/transaction_decision_brief.py",
    '''    candidates = _select_by_ids(
        case.trade_finance.product_candidates,
        request.product_candidate_ids,
        "product_candidate_id",
        "product candidate",
    )
    requirements = _select_by_ids(
        case.trade_finance.consultation_requirements,
        request.consultation_requirement_ids,
        "requirement_id",
        "consultation requirement",
    )
''',
    '''    candidates = _select_transaction_linked_by_ids(
        case.trade_finance.product_candidates,
        request.product_candidate_ids,
        "product_candidate_id",
        "product candidate",
        request.transaction_id,
    )
    requirements = _select_transaction_linked_by_ids(
        case.trade_finance.consultation_requirements,
        request.consultation_requirement_ids,
        "requirement_id",
        "consultation requirement",
        request.transaction_id,
    )
''',
)

replace_once(
    "src/intelligence/finding_review.py",
    '''def latest_finding_review_decisions(
    case: UnifiedCopilotCase,
) -> dict[str, FindingReviewDecision]:
    """Return the unsuperseded review decision for each finding."""

    by_id = {item.review_id: item for item in case.finding_reviews}
    superseded = {
        item.supersedes_review_id
        for item in case.finding_reviews
        if item.supersedes_review_id is not None
    }
    latest: dict[str, FindingReviewDecision] = {}
    for decision in case.finding_reviews:
        if decision.review_id in superseded:
            continue
        existing = latest.get(decision.finding_id)
        if existing is not None:
            raise ValueError(
                "Finding review ledger has multiple unsuperseded decisions for "
                f"{decision.finding_id}: {existing.review_id}, {decision.review_id}"
            )
        latest[decision.finding_id] = decision

    unknown_superseded = sorted(identifier for identifier in superseded if identifier not in by_id)
    if unknown_superseded:
        raise ValueError(
            "Finding review ledger references unknown superseded review IDs: "
            + ", ".join(unknown_superseded)
        )
    return latest
''',
    '''def latest_finding_review_decisions(
    case: UnifiedCopilotCase,
) -> dict[str, FindingReviewDecision]:
    """Validate each append-only review chain and return its latest decision."""

    by_id: dict[str, FindingReviewDecision] = {}
    latest: dict[str, FindingReviewDecision] = {}
    for decision in case.finding_reviews:
        if decision.review_id in by_id:
            raise ValueError(f"Finding review ID is duplicated: {decision.review_id}")

        current = latest.get(decision.finding_id)
        superseded_id = decision.supersedes_review_id
        if superseded_id is None:
            if current is not None:
                raise ValueError(
                    "Finding review ledger has multiple unsuperseded decisions for "
                    f"{decision.finding_id}: {current.review_id}, {decision.review_id}"
                )
        else:
            superseded = by_id.get(superseded_id)
            if superseded is None:
                raise ValueError(
                    "Finding review supersession must reference a prior review ID: "
                    f"{superseded_id}"
                )
            if superseded.finding_id != decision.finding_id:
                raise ValueError(
                    "Finding review cannot supersede a review for a different finding: "
                    f"{superseded_id} belongs to {superseded.finding_id}, "
                    f"not {decision.finding_id}"
                )
            if current is None or current.review_id != superseded_id:
                expected = current.review_id if current is not None else "none"
                raise ValueError(
                    "Finding review must supersede the latest review for the same finding; "
                    f"expected {expected}, received {superseded_id}"
                )

        by_id[decision.review_id] = decision
        latest[decision.finding_id] = decision
    return latest
''',
)

replace_once(
    "src/intelligence/financial_trends.py",
    '''def _last_three_consecutive(values: list[tuple[int, float]]) -> list[float] | None:
    if len(values) < 3:
        return None
    last = values[-3:]
    if last[1][0] - last[0][0] != 1 or last[2][0] - last[1][0] != 1:
        return None
    return [item[1] for item in last]


''',
    '''def _last_three_consecutive(values: list[tuple[int, float]]) -> list[float] | None:
    if len(values) < 3:
        return None
    last = values[-3:]
    if last[1][0] - last[0][0] != 1 or last[2][0] - last[1][0] != 1:
        return None
    return [item[1] for item in last]


def _last_two_consecutive(values: list[tuple[int, float]]) -> list[float] | None:
    if len(values) < 2:
        return None
    last = values[-2:]
    if last[1][0] - last[0][0] != 1:
        return None
    return [item[1] for item in last]


''',
)
replace_once(
    "src/intelligence/financial_trends.py",
    '''    net_income = _series_values(annual_accounts, "account_key", "net_income")
    if len(net_income) >= 2 and net_income[-2][1] >= 0 > net_income[-1][1]:
        add(
            "net_income",
            "high",
            "최근 사업연도 당기순이익이 전년 흑자에서 적자로 전환했습니다.",
            net_income[-1][1],
        )

    operating_cash_flow = _series_values(
        annual_accounts, "account_key", "operating_cash_flow"
    )
    if operating_cash_flow and operating_cash_flow[-1][1] < 0:
        severity = (
            "high"
            if len(operating_cash_flow) >= 2 and operating_cash_flow[-2][1] < 0
            else "review"
        )
''',
    '''    net_income = _series_values(annual_accounts, "account_key", "net_income")
    consecutive_net_income = _last_two_consecutive(net_income)
    if (
        consecutive_net_income
        and consecutive_net_income[-2] >= 0 > consecutive_net_income[-1]
    ):
        add(
            "net_income",
            "high",
            "최근 사업연도 당기순이익이 전년 흑자에서 적자로 전환했습니다.",
            consecutive_net_income[-1],
        )

    operating_cash_flow = _series_values(
        annual_accounts, "account_key", "operating_cash_flow"
    )
    if operating_cash_flow and operating_cash_flow[-1][1] < 0:
        consecutive_cash_flow = _last_two_consecutive(operating_cash_flow)
        severity = (
            "high"
            if consecutive_cash_flow and all(value < 0 for value in consecutive_cash_flow)
            else "review"
        )
''',
)

append_once(
    "tests/test_financial_trends.py",
    "test_nonconsecutive_net_income_does_not_claim_prior_year_transition",
    '''def test_nonconsecutive_net_income_does_not_claim_prior_year_transition():
    common = dict(
        assets="100",
        current_assets="50",
        liabilities="50",
        current_liabilities="25",
        equity="50",
        revenue="100",
        operating_profit="10",
        finance_costs="2",
        operating_cash_flow="8",
    )
    snapshots = {
        2022: _snapshot(2022, _statement(net_income="10", **common)),
        2023: _snapshot(2023, _statement(net_income=None, **common)),
        2024: _snapshot(2024, _statement(net_income="(5)", **common)),
    }

    result = analyze_financial_trends(snapshots)

    assert "net_income" not in set(result.flags["series"])


def test_nonconsecutive_negative_cash_flow_is_not_called_two_year_streak():
    common = dict(
        assets="100",
        current_assets="50",
        liabilities="50",
        current_liabilities="25",
        equity="50",
        revenue="100",
        operating_profit="10",
        net_income="5",
        finance_costs="2",
    )
    snapshots = {
        2022: _snapshot(2022, _statement(operating_cash_flow="(10)", **common)),
        2023: _snapshot(2023, _statement(operating_cash_flow=None, **common)),
        2024: _snapshot(2024, _statement(operating_cash_flow="(20)", **common)),
    }

    result = analyze_financial_trends(snapshots)
    flag = result.flags[result.flags["series"] == "operating_cash_flow"].iloc[0]

    assert flag["severity"] == "review"
    assert flag["message"] == "최근 사업연도 영업현금흐름이 음수입니다."
''',
)

append_once(
    "tests/test_finding_review.py",
    "test_imported_ledger_rejects_cross_finding_supersession",
    '''def test_imported_ledger_rejects_cross_finding_supersession():
    case = _case()
    other_finding = _finding().model_copy(
        update={
            "clause_finding_id": "CLAUSE-OTHER-DOC-LC-001",
            "clause_locator": "Other clause",
        }
    )
    domain = case.trade_finance.model_copy(
        update={"clause_findings": [*case.trade_finance.clause_findings, other_finding]}
    )
    first = _decision()
    cross_finding = _decision(
        review_id="REVIEW-002",
        finding_id=other_finding.clause_finding_id,
        supersedes_review_id="REVIEW-001",
        reviewer_id="reviewer-02",
        reviewed_at=datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
    )
    malformed = case.model_copy(
        update={
            "trade_finance": domain,
            "finding_reviews": [first, cross_finding],
        }
    )

    with pytest.raises(ValueError, match="different finding"):
        latest_finding_review_decisions(malformed)


def test_imported_ledger_rejects_nonlatest_same_finding_supersession():
    first = _decision()
    second = _decision(
        review_id="REVIEW-002",
        supersedes_review_id="REVIEW-001",
        reviewer_id="reviewer-02",
        reviewed_at=datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
    )
    stale_branch = _decision(
        review_id="REVIEW-003",
        supersedes_review_id="REVIEW-001",
        reviewer_id="reviewer-03",
        reviewed_at=datetime(2026, 7, 27, 11, 0, tzinfo=timezone.utc),
    )
    malformed = _case().model_copy(
        update={"finding_reviews": [first, second, stale_branch]}
    )

    with pytest.raises(ValueError, match="latest review"):
        latest_finding_review_decisions(malformed)


def test_imported_ledger_rejects_cycles_and_forward_references():
    first = _decision(supersedes_review_id="REVIEW-002")
    second = _decision(
        review_id="REVIEW-002",
        supersedes_review_id="REVIEW-001",
        reviewer_id="reviewer-02",
        reviewed_at=datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
    )
    cyclic = _case().model_copy(update={"finding_reviews": [first, second]})

    with pytest.raises(ValueError, match="prior review ID"):
        latest_finding_review_decisions(cyclic)
''',
)

append_once(
    "tests/test_transaction_decision_brief.py",
    "test_brief_rejects_product_records_linked_to_another_transaction",
    '''@pytest.mark.parametrize("record_kind", ["candidate", "requirement"])
def test_brief_rejects_product_records_linked_to_another_transaction(record_kind):
    case = _case()
    other_profile = TradeFinanceNeedProfile(
        profile_id="NEED-EXP-002",
        transaction_id="EXP-002",
        transaction_direction="export",
        transaction_stage="pre_shipment",
        declared_needs=["buyer_credit_investigation", "pre_shipment_working_capital"],
        company_size="sme",
        tenor_days=90,
        preferred_bank="KB국민은행",
        available_documents=["수출계약 또는 발주서"],
    )
    other_products = match_trade_finance_products([other_profile])
    domain = case.trade_finance.model_copy(
        update={
            "product_candidates": [
                *case.trade_finance.product_candidates,
                *other_products.product_candidates,
            ],
            "consultation_requirements": [
                *case.trade_finance.consultation_requirements,
                *other_products.consultation_requirements,
            ],
        }
    )
    multi_case = case.model_copy(
        update={
            "approved_transactions": [
                *case.approved_transactions,
                {
                    "transaction_id": "EXP-002",
                    "transaction_type": "export",
                    "currency": "USD",
                    "amount_fc": 250000,
                    "expected_date": "2026-12-15",
                },
            ],
            "trade_finance": domain,
        }
    )
    if record_kind == "candidate":
        request = _request(
            multi_case,
            product_candidate_ids=[other_products.product_candidates[0].product_candidate_id],
            consultation_requirement_ids=[],
        )
    else:
        request = _request(
            multi_case,
            product_candidate_ids=[],
            consultation_requirement_ids=[
                other_products.consultation_requirements[0].requirement_id
            ],
        )

    with pytest.raises(ValueError, match="not linked to transaction EXP-001"):
        build_transaction_decision_brief(multi_case, request)
''',
)

append_once(
    "tests/test_product_matching.py",
    "test_product_outputs_preserve_transaction_linkage",
    '''def test_product_outputs_preserve_transaction_linkage():
    profile = TradeFinanceNeedProfile(
        profile_id="NEED-LINK-001",
        transaction_id="EXP-LINK-001",
        transaction_direction="export",
        transaction_stage="pre_shipment",
        declared_needs=["buyer_credit_investigation"],
        company_size="sme",
    )

    result = match_trade_finance_products([profile])

    assert result.product_candidates
    assert all(
        item.linked_transaction_ids == ["EXP-LINK-001"]
        for item in result.product_candidates
    )
    assert all(
        item.linked_transaction_ids == ["EXP-LINK-001"]
        for item in result.consultation_requirements
    )
''',
)
