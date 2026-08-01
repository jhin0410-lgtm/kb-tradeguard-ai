# KB TradeGuard AI

중소 수출입기업의 **기업정보·무역문서·거래조건·바이어·국가위험·외환노출·재무여력·금융지원 후보**를 하나의 거래 Case로 연결하여, 거래 확정 전에 보완조건과 실행 순서를 근거 기반으로 제시하는 무역금융 의사결정 코파일럿입니다.

> 분석 단위: `기업 × 거래 × 바이어 × 국가 × 계약조건`

핵심 판단은 결정론적 Rule·Calculation·검토된 입력이 담당합니다. AI는 문서 구조화와 근거 설명을 지원할 수 있지만 Finding, 금액 계산, ProductCandidate 상태, 최종 사전진단과 Action Plan을 변경하지 않습니다.

## 1. 하나의 실행 진입점

제출·시연·일반 사용은 `streamlit_app.py` 하나만 실행합니다.

```powershell
git clone https://github.com/jhin0410-lgtm/kb-tradeguard-ai.git
cd kb-tradeguard-ai
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

기본 주소:

```text
http://localhost:8501
```

발표 모드:

```text
http://localhost:8501/?presentation=1&scenario=oa_high_risk
```

기존 `competition_app.py`, `assessment_app.py`, `app.py`, `copilot_app.py`는 개발·회귀 확인용 호환 진입점입니다. 최종 제품 동선에서는 직접 실행하지 않습니다.

## 2. 통합 제품 모드

### Decision Desk — 공개 기본 화면

합성 거래를 같은 5단계 결정론적 Pipeline으로 자동 분석합니다.

- 현재 거래 사전진단 상태와 판단 근거
- 상위 위험 및 Evidence ID
- 담당자·선행조건이 있는 Action Plan
- 계약서·L/C Finding과 문서 정합성 상세
- 거래·재무 감내도
- 현재 거래 원금액·통화·일정 기반 FX Stress
- 자연헤지 후 통화별 순노출
- 월별 예상 기말현금
- Decision Brief가 선택한 금융지원 상담 후보 Top 3
- 현재 Case 기반 KB 상담 Handoff
- Case hash, HTML Snapshot, 감사 JSON

직접 링크:

```text
/?mode=decision
```

### Portfolio & Official Data — 동일 Case 확장 분석

Decision Desk 또는 Private Workspace의 현재 `run.updated_case`를 그대로 이어받습니다. 별도 샘플을 다시 선택하지 않습니다.

- 통화별 수출채권·수입채무·외화현금
- 자연헤지와 순외환노출
- 월별 유동성
- FX 민감도
- 동일 Case의 금융지원 후보
- Case에 고정된 공식 데이터 Snapshot 상태
- World Bank·UN Comtrade·한국수출입은행·관세청 선택형 읽기 전용 조회
- AI·결정론 엔진·Human Review 역할 경계

```text
/?mode=portfolio
```

### Evidence & Submission — 검증·감사·제출 산출물

- 22개 Rule Registry
- 30개 Gold Case
- 150개 의미보존 Mutation
- 4개 대표 시나리오
- Package/Input/Output hash
- Stage Trace와 Artifact Manifest
- 발표용 HTML과 감사 JSON
- Markdown·Decision Brief JSON·감사 ZIP
- Public Repository Safety와 Competition Readiness

```text
/?mode=evidence
```

### Analyst Workspace — 로컬·Private 환경 전용

문서 업로드와 Live AI가 포함된 상세 업무 화면은 공개 배포에서 기본 비활성화됩니다.

PowerShell에서 명시적으로 활성화합니다.

```powershell
$env:TRADEGUARD_ENABLE_PRIVATE_WORKSPACE="1"
python -m streamlit run streamlit_app.py
```

활성화 후:

```text
/?mode=analyst
```

기능:

- 대표 합성 시나리오 또는 검토된 JSON Package 입력
- 계약서·L/C Rule Finding
- 문서 간 금액·통화·날짜·결제조건 정합성
- 거래금액 대비 재무 감내도
- Human Review Overlay
- 금융지원 후보와 미확인 적격조건
- Action dependency와 필요서류
- Markdown·JSON·감사 ZIP
- 선택형 Grounded Live AI

실제 개인정보·고객문서·API Key는 공개 Streamlit 배포에 입력하지 않습니다.

## 3. 결정론적 5단계 Pipeline

```text
검토된 거래 Package
  → 1. 계약서·L/C 사전검사
  → 2. 문서 간 정합성
  → 3. 거래-재무 감내능력
  → 4. 금융·보험·보증 상담 후보
  → 5. 통합 Decision Brief와 Action Plan
```

동일한 정규화 입력은 동일한 Case·Brief 결과를 생성하도록 설계했습니다. 각 단계는 생성 레코드 ID와 실행 상태를 Stage Trace에 남깁니다.

## 4. 구현 기능

### 문서·거래 검토

- 계약서와 L/C의 22개 governed Rule
- 금액·통화·날짜·결제조건 불일치
- 복합 위험조건과 정상 Negative Control
- Amendment와 superseded document 처리
- 누락정보 fail-closed 처리
- Human Review 기록을 원본 Finding과 분리

### 외환·유동성

- 수출채권·수입채무·외화현금
- 자연헤지와 통화별 순노출
- 만기 Bucket과 월별 현금흐름
- 환율 충격 민감도
- 이론 선물환과 헤지 비교 기반 구조
- 입력이 부족하면 차트를 숨기고 누락값을 표시

### 기업·재무

- 거래금액 대비 매출·자산·현금·운전자금 부담
- Financial Health와 Financial Trends
- 다중 거래·다중 통화 포트폴리오 집계
- OpenDART·국세청 Provider 계약

### 바이어·국가·공식 데이터

구현된 Provider surface:

- 한국수출입은행 환율
- World Bank 국가 거시지표
- UN Comtrade Preview
- 관세청 국가·품목 수출입 통계
- 국세청 사업자 상태
- OpenDART 기업·재무정보
- 한국은행 ECOS

공식 데이터는 기준일, 출처, 조회시각과 응답 hash를 별도 Evidence로 관리합니다. 검토되지 않은 실시간 응답은 거래 판정에 자동 반영하지 않습니다.

### 금융지원 매칭

21개 공개 상품 Registry를 거래 목적, 현금흐름, 결제조건, 위험 Finding과 대조합니다.

Candidate 상태:

- `consultation_candidate`
- `insufficient_information`
- `not_applicable`
- `blocked`

각 Candidate에는 기관, 상품명, 연결 거래, 필요 목적, 공식 출처, 미확인 조건과 다음 행동이 포함됩니다. 결과는 승인·적격성·금리·한도·보험 인수를 확정하지 않습니다.

## 5. AI와 책임 경계

### 결정론적 엔진이 고정하는 항목

- 계약서·L/C Finding
- 문서 불일치
- 외환·유동성 계산
- ProductCandidate 상태
- 최종 disposition
- Action Plan

### AI Assist

Private 환경에서만 다음을 지원합니다.

- 문서 구조화 후보
- Evidence ID 기반 설명
- 상담용 요약
- 누락정보 질문 정리

AI 응답은 완료된 결정론적 결과에 Grounding되며 실패 시 deterministic fallback을 사용합니다.

### Human Review

전문가 검토는 원본 Finding을 수정하지 않고 append-only Overlay로 기록합니다.

- `confirmed`
- `dismissed`
- `needs_more_information`

## 6. 공개 배포

Streamlit Cloud의 Main file path는 반드시 다음으로 설정합니다.

```text
streamlit_app.py
```

공개 배포에서는 다음 설정을 유지합니다.

```text
TRADEGUARD_ENABLE_PRIVATE_WORKSPACE=false
```

공개 URL:

```text
https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/
```

발표 URL:

```text
https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/?presentation=1&scenario=oa_high_risk
```

## 7. 검증

```powershell
python scripts/public_repo_safety_check.py
python scripts/competition_readiness_check.py
python -m pytest -q
python -m compileall -q app.py copilot_app.py assessment_app.py assessment_app_v2.py assessment_app_v2_mobile.py competition_app.py streamlit_app.py pages src tests scripts
python -c "import app; import copilot_app; import assessment_app; import assessment_app_v2; import assessment_app_v2_mobile; import competition_app; import streamlit_app; import src"
```

저장소 검증은 내부 일관성, 결정론적 회귀와 공개 안전성을 확인합니다. 실제 사용자 효과, 법률 정확성, 라이브 API 가용성, 은행 승인, 상품 적격성 또는 운영 준비도를 증명하지 않습니다.

## 8. 주요 산출물

```text
input_package.json
updated_case.json
assessment_result.json
decision_brief.json
decision_brief.md
stage_trace.json
audit_summary.json
artifact_manifest.json
kb-tradeguard-competition-snapshot.html
kb-tradeguard-competition-snapshot.json
kb-tradeguard-audit-package.zip
```

## 9. 문서

- `docs/UNIFIED_PRODUCT_GUIDE.md`
- `docs/public_competition_demo.md`
- `docs/competition_demo_script.md`
- `docs/submission_checklist.md`
- `docs/FINAL_HUMAN_VALIDATION.md`

## 10. 비목표

이 프로토타입은 다음을 제공하지 않습니다.

- 실제 KB 내부 승인 시스템 연동
- 자동 대출·보증·보험 승인
- 확정 금리·한도·체결 환율
- 실제 선물환 주문
- 법률·세무·관세 의견
- 제재·AML 해소 판단
- 실제 고객정보가 포함된 공개 데모

기관명과 공개자료 링크는 출처 식별 목적이며 제휴·승인·공식 연동을 의미하지 않습니다.
