from __future__ import annotations

import re
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{label}: expected one regex match, found {count}")
    return updated


executive_path = Path("src/competition_executive_ui.py")
executive = executive_path.read_text(encoding="utf-8")

executive = replace_once(
    executive,
    "    net_exposure_krw: Decimal | None\n    worst_stress_krw: Decimal | None\n    minimum_cash_krw: Decimal | None\n",
    "",
    "remove portfolio fields from executive model",
)
executive = replace_once(
    executive,
    "def build_executive_model(run, assessment: PortfolioAssessment) -> ExecutiveModel:\n    summary = build_risk_first_summary(run)\n    stress_values = [item.estimated_fx_value_change_krw for item in assessment.stress_points if item.estimated_fx_value_change_krw is not None]\n    liquidity_values = [item.ending_cash_krw for item in assessment.liquidity_buckets if item.ending_cash_krw is not None]\n",
    "def build_executive_model(run) -> ExecutiveModel:\n    summary = build_risk_first_summary(run)\n",
    "separate executive model from portfolio assessment",
)
executive = replace_once(
    executive,
    "        net_exposure_krw=assessment.net_exposure_krw,\n        worst_stress_krw=min(stress_values) if stress_values else None,\n        minimum_cash_krw=min(liquidity_values) if liquidity_values else None,\n",
    "",
    "remove portfolio metric assignments",
)
executive = regex_once(
    executive,
    r"def render_mobile_stage_nav\(active_stage: str, scenario_id: str\) -> None:\n.*?\n\ndef render_decision_cockpit",
    '''def render_mobile_stage_nav(active_stage: str, scenario_id: str) -> None:\n    study_value = _query_value("study", "").strip().lower()\n    study_enabled = study_value in {"1", "true", "yes", "on"}\n    links = []\n    for code, label in STAGE_LABELS.items():\n        short = label.split("·", 1)[1].strip()\n        study_query = "&study=true" if study_enabled else ""\n        links.append(\n            f'<a href="?scenario={escape(scenario_id)}&stage={code}{study_query}" '\n            f'data-active="{str(code == active_stage).lower()}">{escape(short)}</a>'\n        )\n    st.markdown(\n        '<nav class="tg-mobile-stage-nav" aria-label="TradeGuard guided stages">'\n        + "".join(links)\n        + "</nav>",\n        unsafe_allow_html=True,\n    )\n\n\ndef render_decision_cockpit''',
    "preserve study mode in mobile links",
)
executive = regex_once(
    executive,
    r"    st\.markdown\(f\"\"\"\n    <div class=\"tg-cockpit\">.*?\n    \"\"\", unsafe_allow_html=True\)\n    action_text =",
    '''    risk_count = len(model.summary.top_risks)\n    action_count = len(model.summary.next_actions)\n    candidate_count = len(model.product_cards)\n    st.markdown(f"""\n    <div class="tg-cockpit"><section class="tg-decision-card" data-tone="{escape(presentation.tone)}"><small>{escape(model.transaction_label)} · {escape(presentation.eyebrow)}</small><h2>{escape(model.disposition_headline)}</h2><p>{escape(model.disposition_explanation)}</p><p><strong>가장 먼저 볼 위험</strong> · {escape(model.top_risk_title)}</p><p><strong>추가 확인</strong> · {model.missing_information_count}개 정보</p></section><div class="tg-cockpit-metrics"><div class="tg-cockpit-metric"><small>상위 위험</small><strong>{risk_count}건</strong><span>현재 단일 거래 Decision Brief 기준</span></div><div class="tg-cockpit-metric"><small>추가 확인</small><strong>{model.missing_information_count}건</strong><span>거래 확정 전 보완할 정보</span></div><div class="tg-cockpit-metric"><small>우선 행동</small><strong>{action_count}건</strong><span>의존관계를 반영한 실행 순서</span></div><div class="tg-cockpit-metric"><small>상담 후보</small><strong>{candidate_count}건</strong><span>가입·승인이 아닌 상담 준비 후보</span></div></div></div>\n    """, unsafe_allow_html=True)\n    action_text =''',
    "keep decision cockpit transaction scoped",
)
executive = replace_once(
    executive,
    "    exposure = max(candidates, key=lambda item: abs(item.net_exposure_fc))\n",
    "    exposure = max(\n        candidates,\n        key=lambda item: (\n            abs(item.net_exposure_krw)\n            if item.net_exposure_krw is not None\n            else Decimal(\"-1\")\n        ),\n    )\n",
    "select waterfall currency by comparable KRW exposure",
)
executive = replace_once(
    executive,
    "def build_handoff_payload(run, model: ExecutiveModel) -> dict[str, Any]:\n    brief = run.assessment_result.brief\n    return {\n",
    "def build_handoff_payload(run, model: ExecutiveModel) -> dict[str, Any]:\n    brief = run.assessment_result.brief\n    identity = getattr(run.updated_case, \"identity\", None)\n    case_id = str(getattr(identity, \"case_id\", \"\"))\n    brief_reference_ids = list(\n        dict.fromkeys(\n            [\n                *brief.country_fact_ids,\n                *brief.compliance_screening_ids,\n                *brief.calculation_ids,\n                *brief.product_candidate_ids,\n                *brief.consultation_requirement_ids,\n            ]\n        )\n    )\n    return {\n",
    "prepare traceable handoff identifiers",
)
executive = replace_once(
    executive,
    '        "case_id": str(getattr(run.updated_case, "case_id", "")),\n',
    '        "case_id": case_id,\n',
    "use governed case identity",
)
executive = replace_once(
    executive,
    '        "brief_reference_ids": list(getattr(brief, "reference_ids", []) or []),\n',
    '        "brief_reference_ids": brief_reference_ids,\n',
    "use real brief reference fields",
)
executive = replace_once(
    executive,
    '("국세청", "configured" if os.getenv("NTS_BUSINESS_API_KEY") else "missing", "NTS_BUSINESS_API_KEY"),',
    '("국세청", "configured" if (os.getenv("NTS_BUSINESS_API_KEY") or os.getenv("DATA_GO_KR_SERVICE_KEY")) else "missing", "NTS_BUSINESS_API_KEY 또는 DATA_GO_KR_SERVICE_KEY"),',
    "recognize shared data.go.kr key for NTS",
)
executive_path.write_text(executive, encoding="utf-8")

streamlit_path = Path("streamlit_app.py")
streamlit = streamlit_path.read_text(encoding="utf-8")
streamlit = regex_once(
    streamlit,
    r"def _render_decision_stage\(\n    run,\n    assessment,\n    \*,\n    presentation_mode: bool,\n    portfolio_label: str,\n\):\n.*?\n    return model\n",
    '''def _render_decision_stage(run, *, presentation_mode: bool):\n    st.markdown(\n        '<div class="tg-chart-note"><strong>분석 범위</strong> · 이 단계의 판정, 위험, 행동, 상담 후보는 선택된 단일 거래 Fixture만 사용합니다. 다중 거래 포트폴리오의 외환노출·유동성 수치는 2단계 시나리오에서 별도 예시로 표시하며 이 판정을 덮어쓰지 않습니다.</div>',\n        unsafe_allow_html=True,\n    )\n    model = render_decision_cockpit(run)\n    app._render_risks(run, presentation_mode=presentation_mode)\n    app._render_actions(run, presentation_mode=presentation_mode)\n    return model\n''',
    "separate decision renderer from portfolio",
)
streamlit = replace_once(
    streamlit,
    "    portfolio_case, assessment = resolve_active_portfolio()\n    portfolio_label = portfolio_case.identity.company_name or portfolio_case.identity.case_id\n    model = build_executive_model(run, assessment)\n",
    "    _, assessment = resolve_active_portfolio()\n    model = build_executive_model(run)\n",
    "separate executive model construction",
)
streamlit = regex_once(
    streamlit,
    r"        model = _render_decision_stage\(\n            run,\n            assessment,\n            presentation_mode=True,\n            portfolio_label=portfolio_label,\n        \)",
    "        model = _render_decision_stage(run, presentation_mode=True)",
    "simplify presentation decision call",
)
streamlit = regex_once(
    streamlit,
    r"            _render_decision_stage\(\n                run,\n                assessment,\n                presentation_mode=False,\n                portfolio_label=portfolio_label,\n            \)",
    "            _render_decision_stage(run, presentation_mode=False)",
    "simplify interactive decision call",
)
streamlit_path.write_text(streamlit, encoding="utf-8")

executive_test_path = Path("tests/test_competition_executive_ui.py")
executive_test = executive_test_path.read_text(encoding="utf-8")
executive_test = executive_test.replace("build_executive_model(run, assessment)", "build_executive_model(run)")
executive_test = replace_once(
    executive_test,
    '    assert "노출" in exposure.layout.title.text\n',
    '    assert exposure.layout.title.text == "EUR 노출 구성"\n',
    "test comparable currency selection",
)
executive_test = replace_once(
    executive_test,
    '    assert payload["top_risks"]\n',
    '    assert payload["case_id"] == run.updated_case.identity.case_id\n    assert payload["brief_reference_ids"]\n    assert payload["top_risks"]\n',
    "test traceable handoff identifiers",
)
executive_test = replace_once(
    executive_test,
    '    assert by_provider["OpenDART"]["state"] == "missing"\n',
    '    assert by_provider["OpenDART"]["state"] == "missing"\n\n    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "configured-for-test")\n    configured = {row["provider"]: row for row in provider_configuration_status()}\n    assert configured["국세청"]["state"] == "configured"\n',
    "test shared NTS key",
)
executive_test = replace_once(
    executive_test,
    '    assert "render_mobile_stage_nav" in source\n',
    '    assert "render_mobile_stage_nav" in source\n    assert "study=true" in Path("src/competition_executive_ui.py").read_text(encoding="utf-8")\n',
    "test study query preservation",
)
executive_test_path.write_text(executive_test, encoding="utf-8")

usability_test_path = Path("tests/test_competition_usability_study.py")
usability_test = usability_test_path.read_text(encoding="utf-8")
usability_test = replace_once(
    usability_test,
    "from src.competition_usability_study import evaluate_usability_response\n",
    "from pathlib import Path\n\nfrom src.assessment_app_v2 import build_risk_first_summary\nfrom src.competition_topic6 import prepare_topic6_demo_package\nfrom src.competition_usability_study import (\n    build_neutral_study_options,\n    evaluate_usability_response,\n)\nfrom src.demo_scenarios import load_demo_scenario\nfrom src.intelligence.single_transaction_package import run_single_transaction_package\n",
    "import usability option helpers",
)
usability_test += '''\n\ndef test_study_options_hide_governed_rank_and_require_explicit_selection():\n    package = prepare_topic6_demo_package(load_demo_scenario("oa_high_risk"))\n    run = run_single_transaction_package(package)\n    summary = build_risk_first_summary(run)\n    risk_options, action_options = build_neutral_study_options(summary)\n\n    assert risk_options\n    assert action_options\n    assert all(not label[:1].isdigit() for label in risk_options)\n    assert all(not label[:1].isdigit() for label in action_options)\n\n    source = Path("src/competition_usability_study.py").read_text(encoding="utf-8")\n    assert source.count("index=None") == 2\n    assert "disabled=not selections_complete" in source\n'''
usability_test_path.write_text(usability_test, encoding="utf-8")

print("Applied UI review fixes")
