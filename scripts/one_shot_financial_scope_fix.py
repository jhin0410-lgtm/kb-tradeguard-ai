from pathlib import Path

source_path = Path("src/intelligence/financial_trends.py")
source = source_path.read_text(encoding="utf-8")
old_normalize = '''def _normalize_snapshot(year: str, value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return {"business_year": year, "results": value}
    if not isinstance(value, Mapping):
        raise TypeError("each financial trend snapshot must be a mapping or result list")
'''
new_normalize = '''def _normalize_snapshot(year: str, value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        raise ValueError(
            "raw financial result lists lack required comparison metadata; "
            "provide corp_code, report_code, fs_div, and results for every year"
        )
    if not isinstance(value, Mapping):
        raise TypeError("each financial trend snapshot must be a mapping")
'''
if old_normalize not in source:
    raise SystemExit("normalize snapshot block not found")
source = source.replace(old_normalize, new_normalize, 1)

old_scope = '''def _validate_consistent_scope(snapshots: list[dict[str, Any]]) -> None:
    labels = {
        "corp_code": "corporation code",
        "report_code": "report type",
        "fs_div": "financial-statement scope",
    }
    for field, label in labels.items():
        values = {
            str(snapshot.get(field)).strip()
            for snapshot in snapshots
            if snapshot.get(field) not in {None, ""}
        }
        if len(values) > 1:
            raise ValueError(f"multi-year comparison requires one consistent {label}")
'''
new_scope = '''def _validate_consistent_scope(snapshots: list[dict[str, Any]]) -> None:
    labels = {
        "corp_code": "corporation code",
        "report_code": "report type",
        "fs_div": "financial-statement scope",
    }
    for field, label in labels.items():
        missing_years = [
            str(snapshot["business_year"])
            for snapshot in snapshots
            if snapshot.get(field) in {None, ""}
        ]
        if missing_years:
            raise ValueError(
                f"multi-year comparison requires {label} metadata for every snapshot; "
                f"missing for: {', '.join(missing_years)}"
            )
        values = {str(snapshot[field]).strip() for snapshot in snapshots}
        if len(values) != 1:
            raise ValueError(f"multi-year comparison requires one consistent {label}")
'''
if old_scope not in source:
    raise SystemExit("scope validation block not found")
source = source.replace(old_scope, new_scope, 1)
source_path.write_text(source, encoding="utf-8")

test_path = Path("tests/test_financial_trends.py")
tests = test_path.read_text(encoding="utf-8")
marker = '''def test_snapshot_year_mismatch_is_rejected():
'''
insert = '''@pytest.mark.parametrize(
    ("field", "label"),
    [
        ("corp_code", "corporation code"),
        ("report_code", "report type"),
        ("fs_div", "financial-statement scope"),
    ],
)
def test_missing_comparison_scope_metadata_is_rejected(field, label):
    rows = _statement(
        assets="100",
        current_assets="50",
        liabilities="50",
        current_liabilities="25",
        equity="50",
        revenue="100",
        operating_profit="10",
        net_income="5",
        finance_costs="2",
        operating_cash_flow="8",
    )
    incomplete = _snapshot(2025, rows)
    incomplete.pop(field)

    with pytest.raises(ValueError, match=label):
        analyze_financial_trends(
            {
                2024: _snapshot(2024, rows),
                2025: incomplete,
            }
        )


def test_raw_result_lists_without_scope_metadata_are_rejected():
    rows = _statement(
        assets="100",
        current_assets="50",
        liabilities="50",
        current_liabilities="25",
        equity="50",
        revenue="100",
        operating_profit="10",
        net_income="5",
        finance_costs="2",
        operating_cash_flow="8",
    )

    with pytest.raises(ValueError, match="raw financial result lists"):
        analyze_financial_trends({2024: rows, 2025: rows})


'''
if marker not in tests:
    raise SystemExit("test insertion marker not found")
tests = tests.replace(marker, insert + marker, 1)
test_path.write_text(tests, encoding="utf-8")
