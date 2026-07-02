"""1단계: 사용자의 원시 아이디어를 특허 검토용 구조로 변환."""

from __future__ import annotations

from ..llm import LLM
from ..models import Idea

SYSTEM = """당신은 한국 변리사이자 특허 명세서 작성 전문가입니다.
사용자가 자유롭게 적은 발명 아이디어를 받아, 선행기술 조사와 특허성 판단에
사용할 수 있도록 핵심 요소를 구조화합니다.

원칙:
- 사용자가 명시하지 않은 사실을 지어내지 마세요. 추론한 부분은 보수적으로 적습니다.
- 핵심 구성요소(key_features)는 청구항으로 이어질 수 있는 '구성요소(element)' 단위로 분해합니다.
- 검색 키워드는 실제 KIPRIS 검색에 쓰일 것이므로, 너무 일반적이지 않고
  발명의 기술적 특징을 좁혀 줄 수 있는 명사구로 만듭니다.
- 한글 키워드와 영문 키워드를 모두 제공합니다(영문은 해당 분야 표준 용어).
- IPC 힌트는 알고 있는 범위에서만 제시하고, 모르면 빈 배열로 둡니다."""

USER_TEMPLATE = """다음은 발명자가 작성한 아이디어 원문입니다.

\"\"\"
{raw}
\"\"\"

이 아이디어를 구조화해 주세요."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "description": "발명의 명칭(간결하게)"},
        "technical_field": {"type": "string", "description": "기술분야"},
        "problem": {"type": "string", "description": "해결하고자 하는 과제"},
        "solution": {"type": "string", "description": "과제 해결 수단의 요지"},
        "key_features": {
            "type": "array",
            "items": {"type": "string"},
            "description": "청구항 구성요소 단위의 핵심 특징",
        },
        "effects": {"type": "array", "items": {"type": "string"}},
        "keywords_ko": {"type": "array", "items": {"type": "string"}},
        "keywords_en": {"type": "array", "items": {"type": "string"}},
        "ipc_hints": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title",
        "technical_field",
        "problem",
        "solution",
        "key_features",
        "effects",
        "keywords_ko",
        "keywords_en",
        "ipc_hints",
    ],
}


def structure_idea(llm: LLM, raw_text: str) -> Idea:
    data = llm.complete_json(
        system=SYSTEM,
        user=USER_TEMPLATE.format(raw=raw_text.strip()),
        schema=SCHEMA,
        max_tokens=4000,
    )
    return Idea(
        raw_text=raw_text,
        title=data.get("title", ""),
        technical_field=data.get("technical_field", ""),
        problem=data.get("problem", ""),
        solution=data.get("solution", ""),
        key_features=data.get("key_features", []),
        effects=data.get("effects", []),
        keywords_ko=data.get("keywords_ko", []),
        keywords_en=data.get("keywords_en", []),
        ipc_hints=data.get("ipc_hints", []),
    )
