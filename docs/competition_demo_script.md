# KB TradeGuard AI · 3분 최종 시연 스크립트

## 시연 URL

```text
https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/?presentation=1&scenario=oa_high_risk
```

일반 통합 제품:

```text
https://kb-tradeguard-ai-gcfcxw7cdmfcbxe4y4zsbl.streamlit.app/?mode=decision
```

공개 데모는 합성 거래를 사용하며 승인·법률의견·금리·한도·보험 인수를 확정하지 않습니다.

## 0:00–0:25 · 문제와 제품 정의

> 중소 수출입기업은 계약조건, 문서 불일치, 바이어·국가위험, 환노출, 운전자금과 금융지원 정보를 서로 다른 문서와 기관에서 확인합니다. KB TradeGuard AI는 이를 `기업 × 거래 × 바이어 × 국가 × 계약조건` Case로 묶어 거래 확정 전에 보완조건과 실행 순서를 근거와 함께 제시합니다.

## 0:25–0:55 · Decision Desk

화면에서 현재 거래, 사전진단 상태, 핵심 위험, 연결 근거 수와 우선 행동을 보여줍니다.

> 이 결과는 생성형 AI가 만든 종합점수가 아닙니다. 검토된 입력을 계약·L/C 사전검사, 문서 정합성, 거래-재무 감내도, 금융지원 Candidate, Decision Brief의 5단계 결정론적 Pipeline으로 처리합니다.

## 0:55–1:25 · 위험과 Evidence

첫 번째 위험의 근거를 엽니다.

> 위험 문장은 Rule Finding, Calculation ID, 공식 데이터 Snapshot, Case hash로 내려갑니다. 누락정보는 추정하지 않고 추가 확인 항목으로 남기며 원본 Finding은 UI나 AI가 변경하지 않습니다.

## 1:25–1:55 · 현재 Case 기반 FX·유동성

FX Stress, 자연헤지 후 순노출, 월별 예상 기말현금을 보여줍니다.

> 이 차트는 설명용 지수가 아니라 현재 선택된 합성 거래의 원금액·통화·결제일, 검토된 환율과 명시적 현금 가정으로 계산됩니다. 필요한 입력이 없으면 가짜 값을 만들지 않고 해당 결과를 생략합니다.

## 1:55–2:25 · 금융지원 Candidate와 KB Handoff

상위 Candidate 3개와 현재 Case 기반 Handoff를 보여줍니다.

> 21개 공개 상품 Registry를 거래 목적, 현금흐름, 결제조건과 위험 Finding에 대조합니다. Decision Brief가 선택한 Candidate마다 미확인 조건, 공식 출처와 다음 행동을 제시하며 승인·금리·한도를 확정하지 않습니다.

## 2:25–2:45 · 통합 제품 연결

일반 화면 또는 준비된 캡처로 공개 사이드바의 세 모드를 보여줍니다.

> 하나의 `streamlit_app.py` 안에서 Decision Desk, Portfolio & Official Data, Evidence & Submission으로 이동하며 같은 Case와 Pipeline을 공유합니다. 문서 업로드와 선택형 Live AI가 포함된 Analyst Workspace는 공개 사이트가 아니라 로컬·Private 환경에서만 별도로 활성화합니다.

## 2:45–3:00 · 검증과 결론

> 22개 Rule, 30개 Gold Case, 150개 의미보존 Mutation, 4개 대표 시나리오와 전체 회귀 테스트로 내부 일관성을 검증합니다. TradeGuard AI는 금융판단을 AI에게 맡기는 것이 아니라 결정론적 Rule·Calculation·Evidence와 제한된 AI Assist를 연결해 더 준비된 무역금융 상담을 만듭니다.

## 질의응답용 공개 화면

### Decision Desk 상세 탭

- 계약서·L/C Finding
- 문서 정합성
- 거래·재무 감내도
- Action dependency와 필요서류

### Portfolio & Official Data

- Decision Desk의 동일 Case 연결
- 통화별 노출·자연헤지·유동성·FX Stress
- 현재 Case 기반 금융지원 후보
- 공식 Snapshot 상태
- World Bank·UN Comtrade·한국수출입은행·관세청 조회 경로

### Evidence & Submission

- Validation status
- Package/Input/Output hash
- HTML Snapshot
- 감사 JSON
- 전체 감사 패키지

## 질의응답용 Private 화면

사전에 로컬에서 다음 환경변수로 활성화합니다.

```powershell
$env:TRADEGUARD_ENABLE_PRIVATE_WORKSPACE="1"
python -m streamlit run streamlit_app.py
```

Analyst Workspace:

- reviewed JSON Package 입력
- Human Review Overlay
- Candidate 상세
- 감사 ZIP
- 선택형 Grounded Live AI

실제 개인정보·고객문서는 사용하지 않습니다.

## 발표 실패 대비

발표 전 `Evidence & Submission`에서 아래 파일을 저장합니다.

```text
kb-tradeguard-competition-snapshot.html
kb-tradeguard-competition-snapshot.json
kb-tradeguard-audit-package.zip
```

네트워크 장애 시 HTML Snapshot으로 동일한 판정, 위험, Action과 Case hash를 설명합니다.
