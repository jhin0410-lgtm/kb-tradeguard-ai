# KB TradeGuard AI

중소 수출입기업의 **기업정보·무역문서·거래조건·바이어·국가위험·외환노출·재무여력**을 단일 거래 단위로 결합하여, 거래 확정 전에 위험과 금융·보험·보증 상담 준비사항을 근거 기반으로 제시하는 무역금융 의사결정 코파일럿입니다.

> 분석 단위: `기업 × 거래 × 바이어 × 국가 × 계약조건`

이 저장소는 Python 3.11+ 기반 공모전 프로토타입입니다. 핵심 판단은 결정론적 룰·계산·검증된 입력이 담당하며, AI는 선택형 설명 계층으로만 배치됩니다.

## 핵심 문제

중소 수출입기업은 신규 바이어 거래를 검토할 때 다음 정보를 서로 다른 문서와 기관에 나누어 확인해야 합니다.

- 계약서·Purchase Order·L/C의 독소조항과 누락조건
- 문서 간 통화·금액·날짜·결제조건 불일치
- 바이어와 국가위험의 분리된 확인
- 거래 규모 대비 유동성·선적 전 자금부담
- 무역금융·보험·보증 상담 후보와 준비서류
- 누가 무엇을 먼저 확인해야 하는지에 대한 실행 순서

KB TradeGuard AI는 이 정보를 하나의 `Decision Brief`, 근거 ID, 의존형 Action Plan, 감사 패키지로 연결합니다.

## 공모전 데모 앱

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 -m streamlit run assessment_app.py
```

대표 데모는 `O/A 90일 고위험 수출` 시나리오입니다. 앱은 다음 순서로 구성됩니다.

1. 요약 및 통합 사전진단 상태
2. 위험·근거와 Reference ID
3. 계약서·L/C Finding 및 전문가 검토 상태
4. 거래 규모와 재무 감내능력
5. KB·K-SURE 상담 후보
6. 담당자·선행조건이 포함된 Action Plan
7. Markdown·JSON·Manifest·감사 ZIP
8. 선택형 Grounded Live AI

입력은 합성 대표 시나리오 또는 `single-transaction-package/1.0` JSON Package를 사용합니다. 입력값을 자동 보정하거나 누락값을 추정하지 않습니다.

## 결정론적 5단계 파이프라인

```text
검토된 거래 Package
  → 1. 계약서·L/C 사전검사
  → 2. 문서 간 정합성
  → 3. 거래-재무 감내능력
  → 4. 금융·보험·보증 상담 후보
  → 5. 통합 Decision Brief와 Action Plan
```

각 단계는 생성 레코드 ID와 실행 상태를 `Stage Trace`에 남깁니다. 동일한 Package는 동일한 정규화 입력과 결정론적 결과를 생성하도록 설계했습니다.

## 신뢰 경계

### 결정론적 엔진

다음 항목은 룰·계산·검증된 도메인 레코드만 생성합니다.

- 계약서 및 L/C Rule Finding
- 문서 간 불일치
- 외환·유동성·거래 감내 계산
- 상담 필요와 공개 상품 후보 연결
- 최종 disposition과 Action Plan

### Human Review Overlay

전문가 검토는 원본 Finding을 수정하지 않고 append-only Review 기록으로 남깁니다.

- `confirmed`
- `dismissed`
- `needs_more_information`

### 선택형 Grounded Live AI

Live AI는 기본 OFF입니다. 설정된 경우에도 완료된 결정론적 결과만 설명하며 다음을 수행하지 않습니다.

- 거래 승인·거절
- 계산 또는 Finding 변경
- 법률의견 제공
- 제재·AML 해소
- KB 신용승인 또는 K-SURE 인수판정
- 금리·한도·실행조건 확정
- 누락정보 추정

모델 응답은 허용된 `[REF:ID]`만 사용할 수 있고, 로컬 검증에 실패하면 화면에 신뢰 결과로 표시되지 않습니다. 외부 API가 없어도 전체 분석·보고서·다운로드는 정상적으로 독립 실행됩니다.

## Gold Dataset과 공격 테스트

`data/gold/trade_document_gold_v1.json`은 실제 고객 결론이 아닌 `synthetic_gold` 검증 데이터입니다.

- 명시적 Gold Case 30개
- 계약서 Case 10개
- L/C Case 20개
- `trade-document-rules/1.1`의 22개 Rule ID 전체 Coverage
- 정상 입력 Negative Control
- 복합 독소계약·복합 고위험 L/C
- 의미를 보존하는 자동 Mutation 150개

Mutation은 ID 재명명, 거래 재연결, Source metadata 변경, 상태 변경, 무관 필드 삽입이 Rule 결과를 바꾸지 않는지 검사합니다.

```powershell
py -3.13 -m pytest -q tests/test_trade_document_gold_dataset.py
py -3.13 scripts/trade_document_gold_summary.py
```

## 감사 가능한 산출물

단일 거래 실행은 다음 산출물을 제공합니다.

```text
input_package.json
updated_case.json
updated_case_canonical.json
assessment_result.json
decision_brief.json
decision_brief.md
stage_trace.json
audit_summary.json
artifact_manifest.json
competition-presentation-snapshot.json
```

입력 Package hash, 입력 Case hash, 출력 Case hash와 파일별 SHA-256을 함께 보존합니다. Hash는 변경 추적 식별자이며 결과의 법적·업무적 정확성을 보증하지 않습니다.

## 전체 실행 진입점

### 공모전 단일 거래 사전진단

```powershell
py -3.13 -m streamlit run assessment_app.py
```

### Global Trade Copilot workspace

```powershell
py -3.13 -m streamlit run copilot_app.py
```

### 상세 포트폴리오·외환 대시보드

```powershell
py -3.13 -m streamlit run app.py
```

## 검증

```powershell
py -3.13 scripts/public_repo_safety_check.py
py -3.13 scripts/competition_readiness_check.py
py -3.13 -m pytest -q
py -3.13 -m compileall -q app.py copilot_app.py assessment_app.py pages src tests scripts
py -3.13 -c "import app; import copilot_app; import assessment_app; import src"
```

검증 스크립트는 네트워크 호출 없이 다음을 확인합니다.

- 공개 저장소에 포함되면 안 되는 경로와 credential-shaped text
- 필수 제출·데모·공개운영 파일 존재
- 대표 시나리오 4개의 예상 disposition 유지
- Presentation Snapshot 생성
- Gold Case 30개와 Mutation 150개 구성
- Rule Registry 22개 전체 Coverage

Pattern scan이 통과해도 과거 Git history, fork, cache, Actions log 또는 외부 시스템에 비밀정보가 없음을 보증하지는 않습니다. 노출된 credential은 파일 삭제와 별개로 발급기관에서 즉시 폐기·회전해야 합니다.

## 발표·제출 문서

- `docs/competition_demo_script.md`: 3분 발표 동선과 발표 문장
- `docs/submission_checklist.md`: 캡처·제출 파일·금지 표현 점검
- `docs/assessment_demo_app.md`: 데모 앱 입력·화면·Live AI 경계
- `docs/trade_document_gold_dataset.md`: Gold Dataset과 Mutation 설계
- `docs/competition_hardening_and_live_ai.md`: 검증 및 Live AI 아키텍처

## 공개 저장소 운영

- 실제 고객·바이어·직원·개인정보와 원본 계약·송장·L/C·재무자료를 커밋하지 않습니다.
- `.env`, Streamlit secrets, API key, service-account 파일, 인증서와 로컬 데이터 디렉터리는 `.gitignore`로 차단합니다.
- CI는 `contents: read` 최소 권한으로 실행되며 checkout credential을 보존하지 않습니다.
- 보안 문제는 공개 Issue에 credential이나 원문서를 첨부하지 말고 `SECURITY.md` 절차를 따릅니다.
- 기관명과 공개자료 링크는 출처 식별 목적이며 제휴·승인·공식 연동을 의미하지 않습니다.

상세 권한·데이터·상표 경계는 `NOTICE.md`를 참고하십시오.

## 비목표와 제한

이 프로토타입은 다음을 제공하지 않습니다.

- 실시간 환율·금리·한도 또는 실제 KB 내부 시스템 연동
- OCR 기반 원본 PDF 자동승인
- 공식 신용등급·대출승인·상품 적격성 확정
- 법률·세무·관세·제재 회피 판단
- ICC 상업용 Rule text 재현
- 실제 고객정보가 포함된 공개 데모
- 자동 거래 실행 또는 업무 차단

모든 결과는 사전검사와 상담 준비를 위한 보조정보이며, 실제 거래 확정에는 은행·보험기관·법무·물류·컴플라이언스 담당자의 확인이 필요합니다.

## 라이선스와 보안

원본 코드와 프로젝트 작성 문서는 별도 표기가 없는 한 `LICENSE`의 MIT License를 따릅니다. 제3자 상표·출판물·데이터의 권리는 각 권리자에게 있으며, 상세 고지사항은 `NOTICE.md`에 정리되어 있습니다.

취약점 또는 실수로 노출된 비밀정보는 공개 Issue에 게시하지 말고 `SECURITY.md`의 신고·회전 절차를 따르십시오.
