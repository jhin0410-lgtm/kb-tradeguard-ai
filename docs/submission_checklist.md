# KB TradeGuard AI 공모전 제출 체크리스트

## 1. 제출 전 코드 상태

- [ ] 작업 브랜치가 `feature/global-trade-copilot-v2`인지 확인
- [ ] `git pull --ff-only` 완료
- [ ] 전체 pytest 통과 로그 보관
- [ ] `compileall` 성공
- [ ] `competition_app`, `streamlit_app` 포함 전체 import 성공
- [ ] `scripts/competition_readiness_check.py`의 `status`가 `ready`
- [ ] API Key·실제 고객정보·로컬 `.env`가 Git에 포함되지 않음

검증 명령:

```powershell
git branch --show-current
git pull --ff-only
py -3.13 -m pytest -q
py -3.13 -m compileall -q app.py copilot_app.py assessment_app.py assessment_app_v2.py assessment_app_v2_mobile.py competition_app.py streamlit_app.py pages src tests scripts
py -3.13 -c "import app; import copilot_app; import assessment_app; import assessment_app_v2; import assessment_app_v2_mobile; import competition_app; import streamlit_app; import src"
py -3.13 scripts/competition_readiness_check.py
```

## 2. 공개 데모 상태

- [ ] 배포 앱 파일이 `streamlit_app.py`
- [ ] 공개 주소가 HTTPS
- [ ] `TRADEGUARD_PUBLIC_DEMO_URL` 설정 완료
- [ ] 공개 앱에 JSON·원본문서 업로드가 없음
- [ ] 공개 앱에 Live AI·API Key 입력이 없음
- [ ] 공개 앱은 합성 시나리오만 사용
- [ ] QR이 공개 HTTPS 주소를 여는지 확인

로컬 실행:

```powershell
py -3.13 -m streamlit run competition_app.py
```

휴대폰 같은-Wi-Fi 실행:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run-mobile-demo.ps1
```

## 3. 대표 시나리오

메인 발표는 `O/A 90일 고위험 수출`을 사용한다. 공개 앱에서는 첫 접속 시 자동 실행된다.

확인할 핵심 흐름:

1. 거래 확정 전 조건 보완 필요 판정
2. 상위 위험 3개와 근거 ID
3. 문서 불일치와 계약조건 Finding
4. 거래 규모 대비 유동성·선적 전 자금부담
5. KB·K-SURE 상담 후보
6. 담당자와 선행조건이 연결된 Action Plan
7. Case hash와 발표·감사 Snapshot

보조 시나리오:

- 필수정보 부족: 누락값을 추정하지 않는 fail-closed 동작
- 복합 Acceptance L/C: 전문가 확인 Gate
- 검토완료 정상 근접: 무조건 경고하지 않는 Negative Control

## 4. 필수 캡처

- [ ] HTTPS 공개 Hero와 통합 판정
- [ ] KPI와 5단계 Pipeline
- [ ] 상위 위험 3개
- [ ] 첫 번째 위험의 `판단 근거 열기`
- [ ] 다음 행동 3개
- [ ] 검증 현황 `22 / 30 / 150 / 4`
- [ ] 공개 QR
- [ ] 휴대폰 하단 고정 메뉴 `요약 | 근거 | 실행 | 감사`
- [ ] Case hash와 Snapshot 다운로드
- [ ] `?presentation=1` 전체 화면

캡처 원칙:

- 브라우저 주소창·북마크바·개인 계정정보는 제외
- 화면 배율은 카드와 문장이 잘리지 않게 조정
- 실제 API Key나 환경변수 화면은 캡처하지 않음
- 실제 고객명·사업자번호·계약금액을 사용하지 않음
- 합성 데이터임을 발표 또는 설명문에 명시

권장 파일명:

```text
01_public_hero_verdict.png
02_pipeline_kpi.png
03_top_risks.png
04_evidence_open.png
05_next_actions.png
06_validation_status.png
07_public_qr.png
08_mobile_bottom_nav.png
09_audit_snapshot.png
10_presentation_mode.png
```

## 5. 제출 자료에 넣을 핵심 문장

### 한 문장 정의

> 중소 수출입기업의 기업정보·무역문서·거래조건·바이어·국가위험·외환노출을 결합하여, 거래 전 위험과 자금조달·보험·보증 대안을 근거 기반으로 제시하는 무역금융 의사결정 코파일럿입니다.

### 차별점

> 생성형 AI가 금융판단을 대신하는 구조가 아니라, 결정론적 Rule·Calculation·Evidence가 판단을 만들고 AI는 검증된 근거를 설명하는 후단 계층으로 제한했습니다.

### 검증

> 계약서·L/C Rule Registry 전체를 포괄하는 30개 Gold Case와 의미 보존 Mutation 150개를 구성해, 위험조건 탐지와 정상조건 비탐지를 함께 검증합니다.

### 실무 활용

> 단순 위험점수 대신 원인별 Finding, 근거 ID, 담당자, 선행조건과 준비서류를 연결한 Action Plan을 제공합니다.

### 권한 경계

> 결과는 거래 승인·법률의견·제재 해소·은행 신용승인 또는 보험 인수판정이 아니라, 전문가 상담과 거래조건 보완을 위한 사전검사입니다.

## 6. 사용하면 안 되는 표현

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

## 7. 최종 제출 파일

- [ ] README 최신화
- [ ] GitHub 저장소 링크
- [ ] 발표자료
- [ ] 서비스 화면 캡처
- [ ] 공개 HTTPS 데모 링크
- [ ] 3분 시연 스크립트
- [ ] 기술설명서 또는 구현 요약
- [ ] 개인정보·API Key 제거 확인
- [ ] 실행 방법과 Python 버전 명시
- [ ] 제한사항과 비목표 명시

앱에서 다운로드할 증빙:

```text
kb-tradeguard-competition-snapshot.html
kb-tradeguard-competition-snapshot.json
kb-tradeguard-audit-package.zip
```

## 8. 발표 직전 점검

- [ ] `?presentation=1` 화면이 정상인지 확인
- [ ] O/A 90일 시나리오가 자동 실행되는지 확인
- [ ] `판단 근거 열기`가 정상 작동하는지 확인
- [ ] 공개 QR이 모바일 앱 화면으로 연결되는지 확인
- [ ] 실행 후 모든 5단계가 의도대로 완료·생략되는지 확인
- [ ] Snapshot 다운로드 버튼이 정상 작동하는지 확인
- [ ] 발표 PC에서 브라우저 확대율과 창 크기 고정
- [ ] 실패 시 사용할 오프라인 HTML을 별도 저장

## 9. 완료 기준

```text
코드 검증 성공
+ HTTPS 공개 데모 성공
+ 대표 시나리오 자동 실행
+ 모바일 QR 연결
+ 캡처와 발표자료 준비
+ 권한 경계·합성 데이터 표시
+ 비밀정보 제거
```

이는 실제 서비스 운영준비, 법률 적합성, 금융기관 승인 또는 모델 정확도 인증을 의미하지 않는다.
