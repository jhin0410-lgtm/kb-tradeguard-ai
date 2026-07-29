from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected patch anchor not found in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "competition_app.py",
    "The app is intentionally synthetic-demo-only: it auto-runs a governed showcase case,\n"
    "hides development pages and upload controls, presents a Korean risk-first workflow,\n"
    "and exposes only read-only evidence, action, validation, snapshot, and QR surfaces.",
    "The app uses synthetic transaction and company fixtures while presenting separately\n"
    "labelled pinned public-data context. It hides development pages and upload controls,\n"
    "presents a Korean risk-first workflow, and exposes read-only evidence and audit surfaces.",
)
replace_once(
    "competition_app.py",
    "from src.competition_portfolio_view import render_portfolio_section, render_workflow_map\n",
    "from src.competition_case_study_view import render_official_case_study_section\n"
    "from src.competition_portfolio_view import render_portfolio_section, render_workflow_map\n",
)
replace_once(
    "competition_app.py",
    "'<div class=\"tg-section-title\">07 · 검증 현황과 감사 Snapshot</div>'",
    "'<div class=\"tg-section-title\">08 · 검증 현황과 감사 Snapshot</div>'",
)
replace_once(
    "competition_app.py",
    "    render_product_consultation_section(run, presentation_mode=presentation_mode)\n"
    "    render_official_data_section(presentation_mode=presentation_mode)\n",
    "    render_product_consultation_section(run, presentation_mode=presentation_mode)\n"
    "    render_official_case_study_section(presentation_mode=presentation_mode)\n"
    "    render_official_data_section(presentation_mode=presentation_mode)\n",
)
replace_once(
    "src/competition_real_data_view.py",
    "'<div class=\"tg-section-title\">06 · 실제 공식 데이터 연결</div>'",
    "'<div class=\"tg-section-title\">07 · 선택형 live 공식 데이터 조회</div>'",
)
replace_once(
    "src/competition_readiness.py",
    "from .portfolio_demo import build_demo_company_workspace\n",
    "from .official_case_studies import load_pinned_official_context_dataset\n"
    "from .portfolio_demo import build_demo_company_workspace\n",
)
replace_once(
    "src/competition_readiness.py",
    '    "docs/un_comtrade_preview.md",\n',
    '    "docs/un_comtrade_preview.md",\n'
    '    "docs/official_data_case_studies.md",\n'
    '    ".github/workflows/official-data-smoke.yml",\n',
)
replace_once(
    "src/competition_readiness.py",
    '    "data/reference/trade_finance_product_registry_v2.json",\n',
    '    "data/reference/trade_finance_product_registry_v2.json",\n'
    '    "data/case_studies/official_context_queries_v1.json",\n'
    '    "data/case_studies/official_context_snapshots_v1.json",\n',
)
replace_once(
    "src/competition_readiness.py",
    '    "scripts/live_ai_provider_smoke_test.py",\n',
    '    "scripts/live_ai_provider_smoke_test.py",\n'
    '    "scripts/official_data_smoke_test.py",\n'
    '    "src/official_case_studies.py",\n'
    '    "src/competition_case_study_view.py",\n',
)
replace_once(
    "src/competition_readiness.py",
    "    product_registry = load_product_registry()\n",
    "    pinned_context = load_pinned_official_context_dataset()\n"
    "    pinned_source_count = sum(len(case.sources) for case in pinned_context.cases)\n"
    "    if len(pinned_context.cases) != 3:\n"
    "        failures.append(\"Pinned official-context dataset must contain three cases\")\n"
    "    if pinned_source_count != 6:\n"
    "        failures.append(\"Pinned official-context cases must preserve six source bundles\")\n"
    "    if any(\n"
    "        len(source.response_hash) != 64\n"
    "        for case in pinned_context.cases\n"
    "        for source in case.sources\n"
    "    ):\n"
    "        failures.append(\"Pinned official-context sources require SHA-256 hashes\")\n\n"
    "    product_registry = load_product_registry()\n",
)
replace_once(
    "src/competition_readiness.py",
    '        "report_version": "competition-readiness/1.5",\n',
    '        "report_version": "competition-readiness/1.6",\n',
)
replace_once(
    "src/competition_readiness.py",
    '            "synthetic_transaction_and_portfolio_with_read_only_official_context"\n',
    '            "synthetic_transactions_with_pinned_and_optional_live_official_context"\n',
)
replace_once(
    "src/competition_readiness.py",
    '        "official_data_network_verified": False,\n',
    '        "official_data_network_verified": False,\n'
    '        "pinned_official_context_live_collected": True,\n'
    '        "pinned_official_context_dataset_version": pinned_context.dataset_version,\n'
    '        "pinned_official_context_case_count": len(pinned_context.cases),\n'
    '        "pinned_official_context_source_count": pinned_source_count,\n'
    '        "pinned_official_context_generated_at": pinned_context.generated_at.isoformat(),\n',
)
replace_once(
    "tests/test_competition_readiness.py",
    '    assert report["report_version"] == "competition-readiness/1.5"\n',
    '    assert report["report_version"] == "competition-readiness/1.6"\n',
)
replace_once(
    "tests/test_competition_readiness.py",
    '    assert report["public_demo_data_mode"] == "synthetic_transaction_and_portfolio_with_read_only_official_context"\n',
    '    assert report["public_demo_data_mode"] == "synthetic_transactions_with_pinned_and_optional_live_official_context"\n',
)
replace_once(
    "tests/test_competition_readiness.py",
    '    assert report["official_data_network_verified"] is False\n',
    '    assert report["official_data_network_verified"] is False\n'
    '    assert report["pinned_official_context_live_collected"] is True\n'
    '    assert report["pinned_official_context_dataset_version"] == "official-context-snapshots/1.0"\n'
    '    assert report["pinned_official_context_case_count"] == 3\n'
    '    assert report["pinned_official_context_source_count"] == 6\n',
)

readme = ROOT / "README.md"
text = readme.read_text(encoding="utf-8")
marker = "## Real public-data evidence pack"
if marker not in text:
    text += (
        "\n\n## Real public-data evidence pack\n\n"
        "Three competition case studies combine synthetic transaction questions with pinned "
        "World Bank and UN Comtrade public observations collected on 2026-07-29. Each source "
        "preserves its retrieval timestamp, observation year, payload, and SHA-256 response hash. "
        "The manual `official-data-live-smoke` workflow can refresh sanitized evidence without "
        "printing credentials. See `docs/official_data_case_studies.md`.\n"
    )
    readme.write_text(text, encoding="utf-8")
