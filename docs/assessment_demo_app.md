# KB TradeGuard 거래 사전진단 데모 앱

## 목적

`assessment_app.py`는 기존의 결정론적 단일 거래 파이프라인을 공모전 시연용 화면으로 연결한다. 앱은 새로운 금융판단을 만들지 않으며, 검토된 Package를 실행하고 이미 생성된 Finding, RiskSignal, Calculation, ProductCandidate, Decision Brief와 Action Plan을 표시한다.

## 실행

```powershell
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
- Live AI: Provider 호출 전 Grounding Packet 미리보기

## Live AI 경계

Live AI 기본값은 OFF다. ON으로 전환해도 현재 앱은 외부 모델을 호출하지 않고, 완료된 결정론적 결과에서 다음 정보만 묶어 Grounding Packet을 생성한다.

- Case hash
- Brief ID
- 거래정보
- Concern과 Action
- Stage Trace
- Finding Review
- 허용된 Reference ID

향후 Provider를 연결할 때 응답은 모든 핵심 문장에 `[REF:<id>]`를 포함해야 한다. 허용목록 밖 ID, 누락된 inline citation, 근거 없는 답변은 `validate_grounded_live_ai_response`에서 거부해야 한다.

Live AI는 다음을 할 수 없다.

- 거래 승인·거절
- 금융 계산 생성 또는 수정
- Finding·RiskSignal 변경
- 법률의견 제공
- 제재·AML 해소
- KB 신용승인이나 K-SURE 인수판정
- 금리·한도·실행조건 확정
- 누락정보 추정

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

`artifact_manifest.json`은 기존 Package Export가 계산한 파일별 SHA-256과 입력·출력 Case hash를 보존한다.

## 비목표

- OCR
- 원본 PDF 자동승인
- 멀티거래 Case
- 실시간 기관 승인·금리·한도
- 실제 고객정보가 포함된 공개 데모
- 범용 법률·관세·반덤핑 판단
