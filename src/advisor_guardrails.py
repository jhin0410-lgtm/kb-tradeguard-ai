"""Guardrails for advisory scope and prohibited claims."""

from __future__ import annotations

import re

PROHIBITED_PATTERNS = {
    "loan_approval": [
        r"대출(?:이|은|을)?\s*(?:반드시\s*)?승인",
        r"loan\s+(?:will\s+be\s+)?approved",
    ],
    "official_credit_rating": [
        r"공식\s*신용\s*등급",
        r"official\s+credit\s+rating",
    ],
    "product_suitability": [
        r"(?:귀사|고객|당신)(?:에게|은|는)?\s*(?:이\s*)?상품(?:이|은)?\s*(?:가장\s*)?적합",
        r"(?:이용|가입)\s*자격(?:이|을)?\s*(?:있|충족)",
        r"best\s+(?:product|option)",
        r"\b(?:you|customer)\s+(?:are|is)\s+eligible\b",
        r"\bI\s+am\s+eligible\b",
    ],
    "guarantee": [
        r"(?:손실|위험)(?:이|은)?\s*(?:절대\s*)?발생하지\s*않",
        r"guaranteed?\s+(?:savings|approval|risk reduction)",
    ],
    "actual_quote": [
        r"KB(?:의|가)?\s*실제\s*견적",
        r"actual\s+KB\s+quote",
    ],
    "document_falsification": [
        r"문서.*(?:위조|조작)",
        r"(?:falsify|forge|manipulate).*(?:invoice|document)",
    ],
    "sanctions_evasion": [
        r"제재.*(?:회피|우회)",
        r"(?:evade|bypass).*(?:sanction|financial control)",
    ],
    "guaranteed_forecast": [
        r"(?:환율|예측).*(?:확실|보장)",
        r"guaranteed\s+(?:exchange|fx)\s+(?:rate|forecast)",
    ],
    "definitive_legal_tax": [
        r"(?:법률|세무).*(?:확정|결론)",
        r"definitive\s+(?:legal|tax)",
    ],
    "portfolio_mutation": [
        r"(?:포트폴리오|거래).*(?:삭제|지워)",
        r"(?:추출|등록).*(?:승인|approve)",
        r"(?:delete|remove).*(?:portfolio|transaction)",
        r"approve.*(?:extracted|transaction)",
    ],
    "fabricated_policy": [
        r"(?:정책|상품|제도).*(?:지어|날조|없는\s*근거)",
        r"(?:fabricate|invent|make\s+up).*(?:policy|product|guidance)",
    ],
}


def detect_prohibited_wording(text: str) -> list[str]:
    """Return categories whose prohibited patterns appear in ``text``."""
    return [
        category
        for category, patterns in PROHIBITED_PATTERNS.items()
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
    ]


def is_sensitive_request(text: str) -> bool:
    """Identify requests that require a bounded refusal or professional redirect."""
    return bool(
        set(detect_prohibited_wording(text))
        & {
            "loan_approval",
            "official_credit_rating",
            "document_falsification",
            "sanctions_evasion",
            "guaranteed_forecast",
            "definitive_legal_tax",
            "product_suitability",
            "portfolio_mutation",
            "fabricated_policy",
        }
    )


SAFE_RISK_NOTICE = (
    "정보·시뮬레이션·의사결정 고려사항을 구분해야 하며, 실제 거래·대출·보험·"
    "보증·법률·세무 결정은 해당 기관 및 관련 전문가의 확인이 필요합니다."
)
