# KB TradeGuard AI 공모전 제출 체크리스트

## 1. 제출 전 코드 상태

- [ ] 작업 브랜치가 `feature/global-trade-copilot-v2`인지 확인
- [ ] `git pull --ff-only` 완료
- [ ] 전체 pytest 통과 로그 보관
- [ ] `compileall` 성공
- [ ] `app`, `copilot_app`, `assessment_app`, `src` import 성공
- [ ] `scripts/competition_readiness_check.py`의 `status`가 `ready`
- [ ] API Key·실제 고객정보·로컬 `.env`가 Git에 포함되지 않음

검증 명령:

```powershell
git branch --show-current
git pull --ff-only
py -3.13 -m pytest -q
py -3.13 -m compileall -q app.py copilot_app.py assessment_app.py src tests scripts
py -3.13 -c "import app; import copilot_app; import assessment_app; import src"
py -3.13 scripts/competition_readiness_check.py
```

## 2. 대표 시나리오

메인 발표는 `O/A 90일 고위험 수출`을 사용한다.

확인할 핵심 흐름:

1. 거래 확정 전 조건 보완 필요 판정
2. Critical·High 우려 건수
3. 문서 불일치와 계약조건 Finding
4. 거래 규모 대비 유동성·선적 전 자금부담
5. KB·K-SURE 상담 후보
6. 담당자와 선행조건이 연결된 Action Plan
7. Case hash와 감사 ZIP

보조 시나리오:

- 필수정보 부족: 누락값을 추정하지 않는 fail-closed 동작
- 복합 Acceptance L/C: 전문가 확인 Gate
- 검토완료 정상 근접: 무조건 경고하지 않는 Negative Control

## 3. 필수 캡처

### 화면 캡처

- [ ] 첫 화면 Hero와 신뢰 경계
- [ ] O/A 90일 대표 시나리오 카드
- [ ] 상단 Verdict Banner와 KPI
- [ ] 5단계 Pipeline Stepper
- [ ] 가장 먼저 볼 위험 + 첫 번째 실행 행동
- [ ] 위험·근거 탭의 Reference ID
- [ ] 문서 탭의 Finding과 전문가 역할
- [ ] 재무 탭의 거래 규모·유동성 비교
- [ ] 상담 후보 탭의 미확인 조건
- [ ] 실행계획 탭의 담당자·선행 Action
- [ ] 감사 탭의 Input·Output hash와 다운로드 버튼

### 캡처 원칙

- 브라우저 주소창·북마크바·개인 계정정보는 제외
- 화면 배율은 표와 문장이 잘리지 않게 조정
- 실제 API Key나 환경변수 화면은 캡처하지 않음
- 실제 고객명·사업자번호·계약금액을 사용하지 않음
- 합성 데이터임을 발표 또는 설명문에 명시

권장 파일명:

```text
01_hero.png
02_scenario.png
03_verdict_pipeline.png
04_executive_snapshot.png
05_risk_evidence.png
06_document_findings.png
07_financial_capacity.png
08_product_candidates.png
09_action_plan.png
10_audit_export.png
```

## 4. 제출 자료에 넣을 핵심 문장

### 한 문장 정의

> 중소 수출입기업의 기업정보·무역문서·거래조건·바이어·국가위험·외환노출을 결합하여, 거래 전 위험과 자금조달·보험·보증 대안을 근거 기반으로 제시하는 무역금융 의사결정 코파일럿입니다.

### 차별점

> 생성형 AI가 금융판단을 대신하는 구조가 아니라, 결정론적 Rule·Calculation·Evidence가 판단을 만들고 AI는 검증된 근거를 설명하는 후단 계층으로 제한했습니다.

### 검증

> 계약서·L/C Rule Registry 전체를 포괄하는 30개 Gold Case와 의미 보존 Mutation 150개를 구성해, 위험조건 탐지와 정상조건 비탐지를 함께 검증합니다.

### 실무 활용

> 단순 위험점수 대신 원인별 Finding, Reference ID, 담당자, 선행조건과 준비서류를 연결한 Action Plan을 제공합니다.

### 권한 경계

> 결과는 거래 승인·법률의견·제재 해소·은행 신용승인 또는 보험 인수판정이 아니라, 전문가 상담과 거래조건 보완을 위한 사전검사입니다.

## 5. 사용하면 안 되는 표현

- `KB 승인 완료`
- `대출 가능 확정`
- `K-SURE 인수 가능`
- `제재 문제 없음 보장`
- `법률 검토 완료`
- `거래 안전성 인증`
- `AI가 최종 거래 여부 결정`
- `실시간 KB 내부 데이터 연동`
- `정확도 100%`
- `실제 기업 데이터로 검증 완료`

대체 표현:

- 승인 → `상담 후보`, `전문가 확인 필요`
- 적격 → `미확인 적격조건이 남은 상담 후보`
- 안전 → `현재 검토자료에서 중대한 사전검사 경보 없음`
- 판정 → `사전진단 상태`, `검토 우선순위`
- 실제 데이터 → `합성·검수 Fixture`, `공식 출처형 합성 Snapshot`

## 6. 최종 제출 파일

- [ ] README 최신화
- [ ] 소스코드 또는 GitHub 저장소 링크
- [ ] 발표자료
- [ ] 서비스 화면 캡처
- [ ] 3분 시연 스크립트
- [ ] 기술설명서 또는 구현 요약
- [ ] 개인정보·API Key 제거 확인
- [ ] 실행 방법과 Python 버전 명시
- [ ] 제한사항과 비목표 명시

앱에서 다운로드할 증빙:

```text
decision_brief.md
decision_brief.json
kb-tradeguard-audit-package.zip
competition-presentation-snapshot.json
```

## 7. 발표 직전 점검

- [ ] 인터넷 없이도 결정론적 데모가 동작하는지 확인
- [ ] Live AI 토글은 기본 OFF 유지
- [ ] O/A 90일 시나리오가 기본 선택되는지 확인
- [ ] 실행 후 모든 5단계가 의도대로 완료·생략되는지 확인
- [ ] 다운로드 버튼이 정상 작동하는지 확인
- [ ] 발표 PC에서 브라우저 확대율과 창 크기 고정
- [ ] 동일 시나리오를 한 번 미리 실행해 로딩 지연 확인
- [ ] 실패 시 보여줄 캡처본과 감사 ZIP을 별도 보관

## 8. 완료 기준

제출 준비 완료는 다음을 의미한다.

```text
코드 검증 성공
+ 네트워크 없는 데모 성공
+ 대표 시나리오 동선 확인
+ 캡처와 발표자료 준비
+ 권한 경계·합성 데이터 표시
+ 비밀정보 제거
```

이는 실제 서비스 운영준비, 법률 적합성, 금융기관 승인 또는 모델 정확도 인증을 의미하지 않는다.
