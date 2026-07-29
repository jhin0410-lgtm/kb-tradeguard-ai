# KB TradeGuard 거래 사전진단 데모 앱

## 목적

`assessment_app.py`는 기존의 결정론적 단일 거래 파이프라인을 공모전 시연용 화면으로 연결한다. 앱은 새로운 금융판단을 만들지 않으며, 검토된 Package를 실행하고 이미 생성된 Finding, RiskSignal, Calculation, ProductCandidate, Decision Brief와 Action Plan을 표시한다.

## 설치 및 실행

```powershell
py -3.13 -m pip install -r requirements.txt
streamlit run assessment_app.py
```

기존 `app.py`와 `copilot_app.py`는 유지된다. 새 진입점은 JSON Package 기반의 단일 거래 사전진단에 집중한다.

## 입력 방식

### 대표 시나리오

1. 필수정보 부족
2. O/A 90일 고위험 수출
3. 복합 Acceptance L/C
4. 검토완료 정상 근접 사례

대표 시나리오는 모두 합성·검수 Fixture이며 실제 고객 사례가 아니다. 공식 데이터처럼 보이는 국가·재무·스크리닝 값도 `synthetic_official_snapshot`으로 명시하며 실제 기관 결론으로 표현하지 않는다.

### JSON Package 업로드

`single-transaction-package/1.0` 계약을 만족하는 UTF-8 JSON만 허용한다. Case와 Request의 거래 ID, 입력 Case hash, 중첩된 재무·상품 Request의 거래 연결을 기존 Pydantic 계약으로 검증한다.

## 화면 구성

- 요약: 거래 개요, disposition, 누락정보, 5단계 Trace
- 위험·근거: 상위 Concern, 심각도 분포, Reference ID
- 문서: 문서 목록, 조항 Finding, 전문가 Review 상태
- 재무: 공시형 Snapshot, 거래 규모·유동성 비교, 구조적 비율
- 상품: KB·K-SURE 상담 후보와 미확인 조건
- 실행계획: 담당자, 선행 Action, 준비서류, 근거 RiskSignal
- 감사·다운로드: Markdown, Decision Brief JSON, 전체 ZIP
- Live AI: Grounding Packet 생성, OpenAI 호출, Reference ID 검증

## OpenAI Live AI 설정

Live AI는 기본 OFF이며 결정론적 분석과 다운로드에는 API Key가 필요하지 않다. 실제 호출을 사용할 때 저장소 루트의 `.env.example`을 참고해 PowerShell 환경변수를 설정한다.

```powershell
$env:OPENAI_API_KEY="사용자 API Key"
$env:OPENAI_MODEL="gpt-5-mini"
$env:OPENAI_LIVE_AI_TIMEOUT_SECONDS="45"
$env:OPENAI_LIVE_AI_MAX_OUTPUT_TOKENS="1400"

streamlit run assessment_app.py
```

API Key를 코드, JSON Package, Streamlit 업로드 또는 Git commit에 기록하지 않는다. `.env`, `.env.*`, `.streamlit/secrets.toml`은 Git에서 제외된다.

## Live AI 실행 경계

Live AI는 완료된 결정론적 결과에서 다음 정보만 Grounding Packet으로 묶는다.

- Case hash
- Brief ID
- 거래정보
- Concern과 Action
- Stage Trace
- Finding Review
- 허용된 Reference ID

모델은 strict JSON 형태로 `answer_markdown`, `cited_reference_ids`, `limitations`를 반환해야 한다. 답변의 사실·행동 문장은 `[REF:<id>]`를 포함해야 하며 다음 조건 중 하나라도 충족하지 못하면 UI는 답변을 신뢰 결과로 표시하지 않는다.

- 허용목록 밖 Reference ID 사용
- inline citation과 선언된 ID 불일치
- citation이 전혀 없음
- 제한사항 누락
- JSON 계약 위반
- API 응답 미완료 또는 빈 응답

Provider 응답은 Case나 Brief를 수정하지 않는다. 검증된 응답도 `decision_status=explanation_only`로 저장되며 Provider request ID, 모델명, 생성시각, 인용 ID와 제한사항을 함께 다운로드할 수 있다.

Live AI는 다음을 할 수 없다.

- 거래 승인·거절
- 금융 계산 생성 또는 수정
- Finding·RiskSignal 변경
- 법률의견 제공
- 제재·AML 해소
- KB 신용승인이나 K-SURE 인수판정
- 금리·한도·실행조건 확정
- 누락정보 추정

## 데이터 전송 주의

Live AI 실행 시 Grounding Packet 내용이 설정된 OpenAI API로 전송된다. 실제 고객·계약·은행정보를 사용하기 전 다음을 확인한다.

- 개인정보와 영업비밀 비식별화
- 회사의 외부 AI 사용정책
- 데이터 보존 및 접근 정책
- API Project와 Key 권한
- 데모에서는 합성 시나리오 우선 사용

## 감사 ZIP

앱은 다음 파일을 ZIP으로 묶는다.

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
```

`artifact_manifest.json`은 기존 Package Export가 계산한 파일별 SHA-256과 입력·출력 Case hash를 보존한다. 검증된 Live AI 응답은 별도 `validated_live_ai_response.json`으로 내려받으며 결정론적 감사 ZIP의 authoritative artifact로 혼입하지 않는다.

## 비목표

- OCR
- 원본 PDF 자동승인
- 멀티거래 Case
- 실시간 기관 승인·금리·한도
- 실제 고객정보가 포함된 공개 데모
- 범용 법률·관세·반덤핑 판단
