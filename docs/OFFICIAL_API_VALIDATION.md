# 공식 API 검증 매트릭스

## 원칙

공식 API 연결 여부와 분석 사용 여부를 분리한다.

- `public`: API key 없이 읽기 전용 조회 가능
- `configured`: 저장소 또는 Streamlit Secret이 설정됨
- `missing`: 어댑터는 존재하지만 실행 환경에 Secret이 없음
- `available`: 실제 응답을 수신하고 스키마·hash 검증을 통과함
- `partial`: 일부 응답만 유효하며 제한사항이 기록됨
- `error`: 요청 또는 응답 검증 실패

`missing` 또는 `error` 값을 합성 수치로 대체하지 않으며 live 성공으로 표시하지 않는다.

## Provider별 검증

| Provider | 역할 | Secret | 공개 데모 기본 상태 | 거래판정 자동 반영 |
|---|---|---|---|---|
| World Bank | 국가 거시지표 | 없음 | 공개 조회 가능 | 검토 Snapshot 전에는 미반영 |
| UN Comtrade | 국가·품목 무역통계 | 없음 | 공개 Preview 가능 | 검토 Snapshot 전에는 미반영 |
| 한국수출입은행 | 공식 참고환율 | `KEXIM_API_KEY` | Secret 필요 | 검토된 환율 Snapshot만 사용 |
| 관세청 | 국가·HS 월별 무역통계 | `KCS_TRADE_API_KEY` 또는 `DATA_GO_KR_SERVICE_KEY` | Secret 필요 | 집계 맥락이며 기업실적 아님 |
| 한국은행 ECOS | 거시·금융지표 | `BOK_ECOS_API_KEY` | Secret 필요 | 검토 Snapshot 전에는 미반영 |
| OpenDART | 기업·재무제표 | `OPENDART_API_KEY` | Secret 필요 | 회사 식별·회계기간 결합 필수 |
| 국세청 | 국내 사업자 상태 | `NTS_BUSINESS_API_KEY` | Secret 필요 | 수출입 통계가 아님 |

## 실행 절차

GitHub Actions의 `official-data-live-smoke` workflow를 수동 실행한다.

1. Repository Settings → Secrets and variables → Actions에서 필요한 Secret을 설정한다.
2. 실제 고객 식별자는 사용하지 않는다.
3. OpenDART와 국세청 테스트는 공개적으로 검토 가능한 별도 테스트 식별자를 사용한다.
4. `require_configured=false`로 먼저 실행해 공개 endpoint와 설정된 provider만 확인한다.
5. 모든 대상 Secret이 설정된 폐쇄 환경에서만 `require_configured=true`를 사용한다.
6. 생성된 `official-data-live-evidence` artifact에서 provider 상태, 조회시각, 관측기준일, response hash를 확인한다.

## 공모전 주장 경계

현재 공개 증거로 주장 가능한 내용:

- World Bank와 UN Comtrade 실제 공개 조회 경로
- KEXIM·관세청·ECOS·OpenDART·국세청 어댑터와 fail-soft 상태 모델
- Secret이 없는 provider를 live 성공으로 표시하지 않는 UI와 smoke 계약

Secret 기반 성공 artifact가 없는 상태에서 다음을 주장하지 않는다.

- 국내 공식 API 전체 연결 완료
- 실시간 환율 기반 체결 가능 가격
- 특정 기업의 실제 수출입 실적
- 특정 기업의 금융상품 적격성·한도·승인
