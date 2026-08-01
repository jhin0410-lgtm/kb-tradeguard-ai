# KB TradeGuard AI 통합 제품 가이드

## 1. 제품 정의

KB TradeGuard AI는 기업정보, 계약·송장·L/C, 바이어·국가위험, 외환노출, 유동성, 금융·보험·보증 후보를 하나의 거래 Case로 묶어 거래 확정 전에 보완조건과 실행 순서를 제시하는 무역금융 의사결정 코파일럿입니다.

핵심 분석 단위는 다음과 같습니다.

```text
기업 × 거래 × 바이어 × 국가 × 계약조건
```

## 2. 단일 실행

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

별도의 `competition_app.py`, `assessment_app.py`, `app.py` 실행은 개발·회귀 확인을 위한 호환 진입점입니다. 제출·시연·일반 사용은 `streamlit_app.py` 하나만 사용합니다.

## 3. 통합 모드

### Decision Desk

대회 공개 시연의 기본 화면입니다.

- 합성 거래 시나리오 선택
- 현재 사전진단 상태
- 상위 위험과 근거 ID
- 우선 Action Plan
- 현재 거래값 기반 FX Stress
- 자연헤지 후 순노출
- 월별 예상 현금
- 동적 금융지원 Candidate
- KB 상담 Handoff

### Analyst Workspace

동일한 결정론적 엔진을 상세 검토 화면에서 사용합니다.

- 검토된 JSON Package 입력
- 계약서·L/C Rule Finding
- 문서 정합성
- 거래·재무 감내도
- Human Review Overlay
- 상품 Candidate 상세
- Action dependency
- 감사 ZIP과 보고서
- 선택형 Grounded Live AI

### Portfolio & Official Data

Decision Desk의 `run.updated_case`를 그대로 이어받습니다.

- 통화별 수출채권·수입채무·외화현금
- 자연헤지와 순외환노출
- 월별 유동성
- FX 민감도
- 동일 Case의 금융지원 후보
- 고정 공식 데이터 Snapshot
- 선택형 공식 API 조회

### Evidence & Submission

- 검증 현황
- Rule·Gold Case·Mutation
- Package/Input/Output hash
- HTML Snapshot
- 감사 JSON
- 상세 감사 패키지

## 4. URL

```text
/?mode=decision
/?mode=analyst
/?mode=portfolio
/?mode=evidence
/?presentation=1&scenario=oa_high_risk
```

발표 모드에서는 Decision Desk의 핵심 네 단계만 표시합니다.

## 5. 데이터 흐름

```text
검토된 거래 Package
  → 계약서·L/C 사전검사
  → 문서 간 정합성
  → 거래-재무 감내능력
  → 금융·보험·보증 Candidate
  → Decision Brief
  → Action Plan
  → Portfolio·Official Data·Audit
```

모든 화면은 같은 Case, Finding, Calculation, ProductCandidate, Evidence ID를 참조합니다.

## 6. 공개와 Private 경계

공개 환경:

- 합성 거래만 사용
- 고객문서 업로드 금지
- 개인정보 입력 금지
- API Key 입력 금지
- Live AI 기본 OFF

Private 또는 로컬 환경:

- 검토된 JSON Package
- Human Review
- 선택형 공식 API
- 선택형 Grounded AI

## 7. 표현 기준

사용:

- 결정론적 거래 사전진단
- 거래 조건 보완
- 금융지원 상담 Candidate
- 검토 완료 입력 거래
- 현재 Case 기반 계산
- 전문가 확인 필요

사용 금지:

- KB 승인 완료
- 대출 가능 확정
- 보험 인수 확정
- 확정 금리·한도
- 실시간 환율 예측
- 법률 검토 완료
- 실제 기업 정확도 검증 완료

## 8. 실행 확인

```powershell
python scripts/public_repo_safety_check.py
python scripts/competition_readiness_check.py
python -m pytest -q
python -m compileall -q app.py copilot_app.py assessment_app.py assessment_app_v2.py assessment_app_v2_mobile.py competition_app.py streamlit_app.py pages src tests scripts
python -c "import app; import copilot_app; import assessment_app; import assessment_app_v2; import assessment_app_v2_mobile; import competition_app; import streamlit_app; import src"
```
