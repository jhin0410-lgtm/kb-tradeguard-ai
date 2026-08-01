"""Compact top-three consultation summary for the public competition journey."""
from __future__ import annotations

import streamlit as st

_TOP_THREE = {
    "oa_high_risk": [
        ("단기수출보험 상담", "90일 외상수출과 거래상대방 미확인 위험", "바이어 신용·인수한도", "K-SURE 신용조사와 보험 상담"),
        ("선물환 상담", "USD 순수취 노출의 원화가치 변동", "체결환율·한도·만기", "KB 외환 담당자에게 예상 수금일 전달"),
        ("수출환어음 매입·추심", "선적 후 수금 전 운전자금 공백", "서류 적합성·상환청구 조건", "인보이스·운송서류 준비"),
    ],
    "complex_lc": [
        ("수출신용장 조건 검토", "복합 조건과 서류 불일치 가능성", "원문 조항·제시기한", "전문가와 L/C 원문 확인"),
        ("수출환어음 매입 상담", "적합 서류 제시 후 조기 현금화 수요", "매입 가능 서류·은행 한도", "필요서류 사전 점검"),
        ("선물환 상담", "결제통화 환율 변동", "금액·만기·체결조건", "결제 예정일 기준 헤지비율 검토"),
    ],
    "missing_information": [
        ("거래정보 보완", "금액·통화·기일 등 필수정보 부족", "계약서·인보이스", "상품 상담 전 입력 완성"),
        ("국외기업 신용조사", "거래상대방 근거 부족", "회사명·주소·등록정보", "K-SURE 조사 가능 범위 확인"),
        ("외환상담 준비", "노출 통화와 만기 미확정", "예상 수취·지급 일정", "현금흐름표 작성"),
    ],
    "reviewed_clean": [
        ("환율 모니터링", "중대한 문서 경고는 없으나 환율 변동은 잔존", "목표환율·결제일", "분할환전·주문관리 검토"),
        ("거래기록 보존", "향후 상담과 감사 재현성", "최종 계약·결제증빙", "Case snapshot 저장"),
        ("정기 재검토", "국가·거래상대방 정보는 변할 수 있음", "최신 공식자료", "결제 전 상태 재확인"),
    ],
}

CSS = """
<style>
.tg-top-products{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.55rem;margin:.6rem 0 .9rem}
.tg-top-product{border:1px solid #dce4ef;border-top:5px solid #f2c94c;border-radius:17px;padding:.82rem;background:#fff;box-shadow:0 7px 20px rgba(15,36,68,.045)}
.tg-top-product small{font-size:.62rem;color:#748198;font-weight:900}.tg-top-product h4{font-size:.92rem;margin:.32rem 0;color:#172033}.tg-top-product p{font-size:.7rem;color:#647084;line-height:1.42;margin:.25rem 0}.tg-top-product b{color:#33435b}
@media(max-width:760px){.tg-top-products{grid-template-columns:1fr}}
</style>
"""


def render_top_product_candidates(scenario_id: str) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div id="products" class="tg-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="tg-section-title">03 · 우선 금융지원 상담 후보</div>', unsafe_allow_html=True)
    rows = _TOP_THREE.get(scenario_id, _TOP_THREE["oa_high_risk"])
    cards = []
    for index, (name, reason, unknown, action) in enumerate(rows, start=1):
        cards.append(
            f'''<article class="tg-top-product"><small>PRIORITY {index}</small><h4>{name}</h4><p><b>선정 이유</b> · {reason}</p><p><b>미확인</b> · {unknown}</p><p><b>다음 행동</b> · {action}</p></article>'''
        )
    st.markdown('<div class="tg-top-products">' + ''.join(cards) + '</div>', unsafe_allow_html=True)
    st.caption("상담 후보이며 가입 가능성·승인·금리·한도·보험 인수를 확정하지 않습니다. 전체 registry 후보는 아래 상세영역에서 확인합니다.")
