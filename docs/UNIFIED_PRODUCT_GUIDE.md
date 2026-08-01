# KB TradeGuard AI 통합 제품 가이드

## 1. 제품 정의

KB TradeGuard AI는 기업정보, 계약·송장·L/C, 바이어·국가위험, 외환노출, 유동성, 금융·보험·보증 후보를 하나의 거래 Case로 묶어 거래 확정 전에 보완조건과 실행 순서를 제시하는 무역금융 의사결정 코파일럿입니다.

핵심 분석 단위:

```text
기업 × 거래 × 바이어 × 국가 × 계약조건
```

## 2. 단일 실행

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

별도의 `competition_app.py`, `assessment_app.py`, `app.py`, `copilot_app.py` 실행은 개발·회귀 확인을 위한 호환 진입점입니다. 제출·시연·일반 사용은 `streamlit_app.py` 하나만 사용합니다.

## 3. 공개 기본 모드

### Decision Desk

대회 공개 시연의 기본 화면입니다.

- 합성 거래 시나리오 선택
- 현재 사전진단 상태
- 상위 위험과 근거 ID
- 우선 Action Plan
- 계약서·L/C·문서 정합성 상세
- 거래·재무 감내도
- 현재 거래값 기반 FX Stress
- 자연헤지 후 순노출
- 월별 예상 현금
- 동적 금융지원 Candidate
- 현재 Case 기반 KB 상담 Handoff

### Portfolio & Official Data

Decision Desk의 `run.updated_case`를 그대로 이어받습니다.

- 통화별 수출채권·수입채무·외화현금
- 자연헤지와 순외환노출
- 월별 유동성
- FX 민감도
- 동일 Case의 금융지원 후보
- 고정 공식 데이터 Snapshot
- 선택형 공식 API 조회
- AI·결정론 엔진·Human Review 역할 구분

### Evidence & Submission

현재 Case와 Package를 그대로 이어받습니다.

- 검증 현황
- Rule·Gold Case·Mutation
- Package/Input/Output hash
- HTML Snapshot
- 감사 JSON
- Markdown 보고서
- Decision Brief JSON
- 전체 감사 ZIP

공개 직접 링크:

```text
/?mode=decision
/?mode=portfolio
/?mode=evidence
/?presentation=1&scenario=oa_high_risk
```

## 4. Analyst Workspace — Private 전용

문서 업로드와 선택형 Live AI가 포함된 화면은 공개 배포에서 기본 비활성화됩니다.

PowerShell:

```powershell
$env:TRADEGUARD_ENABLE_PRIVATE_WORKSPACE="1"
python -m streamlit run streamlit_app.py
```

활성화 후:

```text
/?mode=analyst
```

기능:

- 검토된 JSON Package 입력
- 계약서·L/C Rule Finding
- 문서 정합성
- 거래·재무 감내도
- Human Review Overlay
- 상품 Candidate 상세
- Action dependency와 필요서류
- 감사 ZIP과 보고서
- 선택형 Grounded Live AI

Private Workspace에서 Package를 실행하면 Portfolio와 Evidence 모드도 해당 reviewed Case를 이어받습니다.

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

모든 통합 화면은 같은 Case, Finding, Calculation, ProductCandidate, Evidence ID와 hash를 참조합니다.

## 6. 공개와 Private 경계

공개 환경:

- 합성 거래만 사용
- 고객문서 업로드 비활성화
- 개인정보 입력 금지
- API Key 입력 UI 없음
- Live AI 입력 비활성화
- `TRADEGUARD_ENABLE_PRIVATE_WORKSPACE=false`

Private 또는 로컬 환경:

- 검토된 JSON Package
- Human Review
- 선택형 공식 API
- 선택형 Grounded AI
- `TRADEGUARD_ENABLE_PRIVATE_WORKSPACE=true`

## 7. 금융지원 매칭

21개 공개 상품 Registry를 거래 목적, 현금흐름, 결제조건과 위험 Finding에 대조합니다.

각 ProductCandidate에는 다음이 포함됩니다.

- 기관과 상품·서비스명
- 연결된 거래와 필요 목적
- Candidate 상태
- 공식 출처
- 미확인 적격조건
- 다음 상담 행동

표현은 단순 링크 목록이 아니라 **공개조건 기반 상담 우선순위**이지만, 승인·금리·한도·보험 인수를 확정하지 않습니다.

## 8. AI와 책임 구조

### 결정론적 엔진

- 계약서·L/C Finding
- 문서 불일치
- 외환·유동성 계산
- ProductCandidate 상태
- 최종 disposition
- Action Plan

### AI Assist

- 문서 구조화 후보
- Evidence ID 기반 설명
- 상담용 요약
- 누락정보 질문 정리

AI는 완료된 결정론적 결과에 Grounding되며 Finding과 계산을 변경하지 않습니다.

### Human Review

원본 Finding을 수정하지 않고 append-only Overlay를 남깁니다.

- `confirmed`
- `dismissed`
- `needs_more_information`

## 9. 표현 기준

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

## 10. 실행 확인

```powershell
python scripts/public_repo_safety_check.py
python scripts/competition_readiness_check.py
python -m pytest -q
python -m compileall -q app.py copilot_app.py assessment_app.py assessment_app_v2.py assessment_app_v2_mobile.py competition_app.py streamlit_app.py pages src tests scripts
python -c "import app; import copilot_app; import assessment_app; import assessment_app_v2; import assessment_app_v2_mobile; import competition_app; import streamlit_app; import src"
python scripts/build_submission_package.py --output dist/KB-TradeGuard-AI-prototype.zip
```
