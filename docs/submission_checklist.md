# KB TradeGuard AI 공모전 최종 제출 체크리스트

## 1. 코드와 Release Gate

- [ ] 최종 변경 PR이 `main`에 병합됨
- [ ] 작업 트리와 원격 `main`이 일치함
- [ ] 전체 pytest 통과
- [ ] `compileall`, 앱 Import, 공개 저장소 안전검사 통과
- [ ] `competition_readiness_check.py`가 `ready`
- [ ] 최종 제출 커밋에 Release Tag 생성
- [ ] 열린 임시 Audit PR과 대체된 브랜치 정리

```powershell
git switch main
git pull --ff-only
py -3.13 -m pytest -q
py -3.13 -m compileall -q app.py copilot_app.py assessment_app.py assessment_app_v2.py assessment_app_v2_mobile.py competition_app.py streamlit_app.py pages src tests scripts
py -3.13 -c "import app; import copilot_app; import assessment_app; import assessment_app_v2; import assessment_app_v2_mobile; import competition_app; import streamlit_app; import src"
py -3.13 scripts/public_repo_safety_check.py
py -3.13 scripts/competition_readiness_check.py
```

## 2. 공개 데모

- [ ] 배포 진입점이 `streamlit_app.py`
- [ ] 공개 주소가 HTTPS이며 QR과 일치
- [ ] 공개 앱은 합성 거래만 사용
- [ ] 업로드·API Key 입력·고객정보 저장·실행형 주문 기능이 없음
- [ ] 기본 시나리오가 자동 실행됨
- [ ] 시나리오 변경 시 차트와 금융지원 후보도 실제 결과에 따라 변경됨
- [ ] 누락 입력에서는 가짜 차트를 표시하지 않음

로컬 확인:

```powershell
py -3.13 -m streamlit run streamlit_app.py
```

## 3. 3분 발표 화면

`?presentation=1`에서는 다음 네 단계만 확인합니다.

1. 거래 판정과 핵심 위험·행동
2. 실제 거래값 기반 FX·노출·현금흐름
3. Decision Brief가 선택한 상위 금융지원 후보 3개
4. Rule·Gold Case·Mutation·Case hash

포트폴리오, 공식 API 조회, AI 역할 구조는 일반 화면의 `상세 분석·공식 데이터·AI 구조` 부록에서 질의응답 시만 엽니다.

## 4. 실제 사용성 검증

- [ ] 익명 참여자 5명 이상 테스트
- [ ] 원자료 CSV 보존
- [ ] 자동 집계 JSON 생성
- [ ] 성공·실패 결과를 그대로 제출자료에 반영
- [ ] 어려운 용어와 중복 화면 피드백 반영

```powershell
py -3.13 scripts/summarize_usability_results.py data/usability_test_results.csv --output outputs/usability_test_summary.json
```

## 5. 공식 데이터 증거

- [ ] World Bank·UN Comtrade 고정 Snapshot의 기준일과 hash 확인
- [ ] Secret이 필요한 API는 키를 노출하지 않은 Smoke 결과만 보존
- [ ] 실시간 응답을 검토 없이 거래 판정에 자동 반영하지 않음
- [ ] 국세청 사업자 상태와 관세청 수출입 통계의 역할을 혼동하지 않음

## 6. 필수 캡처

1. 공개 Hero와 거래 판정
2. 핵심 위험과 근거 열기
3. 실제 FX 스트레스·순노출 차트
4. 다음 행동 3개
5. 동적 금융지원 후보 3개
6. 검증 현황과 Case hash
7. 모바일 네 단계 하단 메뉴
8. 공개 QR
9. 감사 JSON·발표 HTML 다운로드
10. 일반 화면의 상세 부록

브라우저 툴바, 개인 계정정보, API Key, 실제 고객·바이어 정보는 캡처하지 않습니다.

## 7. 제출 표현

사용 가능:

- 결정론적 거래 사전진단
- 근거 기반 상담 준비
- 공개조건 기반 상담 후보
- 거래 확정 전 조건 보완 필요
- 검토된 입력 기반 FX 민감도

사용 금지:

- KB 승인 완료
- 대출·보험·보증 가능 확정
- 실시간 체결환율 또는 한도 보장
- 법률 검토 완료
- 거래 안전성 인증
- 실제 기업 데이터로 정확도 검증 완료
- AI가 최종 거래 여부 결정

## 8. 완료 기준

```text
main 검증 성공
+ HTTPS 데모와 모바일 확인
+ 실제 계산 기반 차트
+ 동적 상담 후보
+ 익명 사용성 결과
+ 최신 발표자료·캡처
+ 임시 PR 정리
+ 최종 Release Tag
```
