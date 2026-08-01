# KB TradeGuard AI 공모전 최종 제출 체크리스트

## 1. 코드와 Release Gate

- [ ] 통합 제품 PR이 `main`에 병합됨
- [ ] `streamlit_app.py`가 유일한 사용자 실행 진입점으로 문서화됨
- [ ] 전체 pytest 통과
- [ ] `compileall`, 앱 Import, 공개 저장소 안전검사 통과
- [ ] `competition_readiness_check.py`가 `ready`
- [ ] CI가 깨끗한 제출 ZIP을 생성함
- [ ] 제출 ZIP을 새 폴더에서 설치·실행 검증
- [ ] 최종 제출 커밋에 Release Tag 생성

```powershell
git switch main
git pull --ff-only
python -m pytest -q
python -m compileall -q app.py copilot_app.py assessment_app.py assessment_app_v2.py assessment_app_v2_mobile.py competition_app.py streamlit_app.py pages src tests scripts
python -c "import app; import copilot_app; import assessment_app; import assessment_app_v2; import assessment_app_v2_mobile; import competition_app; import streamlit_app; import src"
python scripts/public_repo_safety_check.py
python scripts/competition_readiness_check.py
python scripts/build_submission_package.py --output dist/KB-TradeGuard-AI-prototype.zip
```

## 2. 단일 실행 확인

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

### 공개 기본 모드

- [ ] Decision Desk
- [ ] Portfolio & Official Data
- [ ] Evidence & Submission

```text
/?mode=decision
/?mode=portfolio
/?mode=evidence
/?presentation=1&scenario=oa_high_risk
```

### Private Workspace

공개 배포에서는 비활성화합니다. 로컬 확인 시에만:

```powershell
$env:TRADEGUARD_ENABLE_PRIVATE_WORKSPACE="1"
python -m streamlit run streamlit_app.py
```

- [ ] Analyst Workspace가 메뉴에 나타남
- [ ] 검토된 JSON Package 실행 가능
- [ ] 이후 Portfolio와 Evidence가 해당 reviewed Case를 이어받음

## 3. 연결성 확인

- [ ] Decision Desk에서 선택한 Scenario와 Case가 Session에 유지됨
- [ ] 공개 문서 탭이 현재 Case의 계약·L/C·정합성 Finding을 표시함
- [ ] 재무 탭이 현재 Case의 거래·재무 감내도를 표시함
- [ ] Action Plan 탭이 담당·선행조건·필요서류를 표시함
- [ ] Portfolio가 별도 샘플이 아니라 현재 `run.updated_case`를 분석함
- [ ] KB Handoff가 현재 Brief의 위험·Candidate·첫 Action을 표시함
- [ ] 금융지원 Top 3가 Decision Brief Candidate에서 생성됨
- [ ] 공식 데이터 화면이 현재 Package의 거래국을 기본값으로 사용함
- [ ] Evidence가 동일 Case의 hash와 Snapshot을 다운로드함

## 4. 공개 데모 안전성

- [ ] Streamlit Cloud Main file path가 `streamlit_app.py`
- [ ] 배포 커밋이 최신 `main`과 일치
- [ ] `TRADEGUARD_ENABLE_PRIVATE_WORKSPACE=false`
- [ ] 공개 주소가 HTTPS이며 QR과 일치
- [ ] 합성 거래만 사용
- [ ] 문서 업로드와 Live AI 입력이 보이지 않음
- [ ] 실제 고객정보·개인정보·API Key 입력을 요구하지 않음
- [ ] 기본 시나리오가 자동 실행됨
- [ ] 시나리오 변경 시 위험·차트·상품 Candidate가 함께 변경됨
- [ ] 누락 입력에서는 값을 추정하지 않고 차트를 생략함

## 5. 발표 모드

```text
https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/?presentation=1&scenario=oa_high_risk
```

확인 순서:

1. 거래 판정과 현재 Case
2. 핵심 위험과 Evidence
3. 현재 Case 기반 FX·순노출·현금흐름
4. 동적 금융지원 Candidate와 KB Handoff
5. Rule·Gold Case·Mutation·Case hash

- [ ] 사이드바와 모드 선택이 숨겨짐
- [ ] 시나리오 선택 컨트롤이 숨겨짐
- [ ] 화면이 3분 발표 동선으로 압축됨

## 6. 질의응답 화면

### Decision Desk 상세 탭

- [ ] 계약서·L/C Finding
- [ ] 문서 정합성
- [ ] 거래·재무 감내도
- [ ] Action dependency와 필요서류

### Private Analyst Workspace

- [ ] reviewed Package 입력
- [ ] Human Review Overlay
- [ ] Candidate 상세
- [ ] 감사 ZIP
- [ ] 선택형 Grounded Live AI 경계

### Portfolio & Official Data

- [ ] 통화별 노출
- [ ] 자연헤지
- [ ] 월별 유동성
- [ ] FX Stress
- [ ] 현재 Case 기반 상품 후보
- [ ] 고정 공식 Snapshot
- [ ] 선택형 공식 API 조회 경로

### Evidence & Submission

- [ ] Validation status
- [ ] 내부 합성 회귀평가
- [ ] Package/Input/Output hash
- [ ] HTML Snapshot
- [ ] 감사 JSON
- [ ] Markdown·Brief JSON·감사 ZIP

## 7. 사용자 검증 표현

실제 참여자를 구하지 못했으므로:

- [ ] 사용자 테스트 완료라고 주장하지 않음
- [ ] `not_run` 상태 유지
- [ ] 프로토콜·템플릿·자동 집계 도구가 준비됐다고만 설명
- [ ] 사용성 성과 수치를 PPT에서 제거

## 8. 공식 데이터 표현

- [ ] 고정 Snapshot과 Live 조회를 구분
- [ ] World Bank·UN Comtrade 기준일 또는 관측연도 표시
- [ ] Secret이 필요한 API Key를 노출하지 않음
- [ ] 실시간 응답을 검토 없이 거래 판정에 자동 반영하지 않음
- [ ] 국세청 사업자 상태와 관세청 수출입 통계를 구분

## 9. 제출 ZIP 구조

```text
KB-TradeGuard-AI/
├─ streamlit_app.py
├─ competition_app.py
├─ assessment_app.py
├─ assessment_app_v2.py
├─ assessment_app_v2_mobile.py
├─ app.py
├─ copilot_app.py
├─ requirements.txt
├─ README.md
├─ LICENSE
├─ SECURITY.md
├─ .env.example
├─ .streamlit/config.toml
├─ src/
├─ pages/
├─ data/
├─ docs/
├─ scripts/
├─ tests/
└─ submission-manifest.json
```

제외:

```text
.git/
.github/
.venv/
.env
.streamlit/secrets.toml
__pycache__/
*.pyc
.pytest_cache/
outputs/
기존 ZIP·로그·임시파일
실제 개인정보·고객문서·API Key
```

## 10. 제출자료

- [ ] 참가신청서 PDF
- [ ] 참가 서약서 PDF
- [ ] 개인정보 동의서 PDF
- [ ] 기술설명서 PDF
- [ ] 발표자료 PPTX
- [ ] 발표자료 PDF
- [ ] CI 검증 프로토타입 ZIP
- [ ] 실행안내 PDF 또는 TXT
- [ ] 공개 URL
- [ ] GitHub URL
- [ ] 오프라인 HTML Snapshot
- [ ] 감사 JSON Sample

## 11. 표현 기준

사용:

- 결정론적 거래 사전진단
- 현재 Case 기반 계산
- 공개조건 기반 금융지원 상담 Candidate
- 거래 확정 전 조건 보완
- Evidence ID 기반 설명
- Human Review 선행

사용 금지:

- KB 승인 완료
- 대출·보험·보증 가능 확정
- 확정 금리·한도·체결환율
- 법률 검토 완료
- 거래 안전성 인증
- 실제 기업 데이터 정확도 검증 완료
- 실제 사용자 검증 완료
- AI가 최종 거래 여부 결정

## 12. 완료 기준

```text
통합 main CI 성공
+ 단일 streamlit_app.py 실행
+ 공개 3개 모드 연결
+ Private Analyst Workspace opt-in
+ 현재 Case 연결성 검증
+ HTTPS 최신 배포 확인
+ CI 생성 ZIP 실행 성공
+ 실제 UI 기반 PPT·PDF
+ 최종 Release Tag
```
