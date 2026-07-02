"""5단계: 특허 명세서 초안 작성.

특허성 판단에서 도출된 '차별점(등록 포인트)'을 독립항에 반드시 반영하여,
신규성·진보성을 확보한 청구항 중심의 한국 특허 명세서를 생성한다.
"""

from __future__ import annotations

from ..llm import LLM
from ..models import Idea, PatentabilityAssessment, PriorArtAnalysis, PatentDraft

SYSTEM = """당신은 한국 특허 명세서를 작성하는 베테랑 변리사입니다.
주어진 발명 아이디어, 특허성 판단, 선행문헌 분석을 바탕으로
특허청에 출원 가능한 수준의 명세서 초안을 작성합니다.

작성 원칙(특허법 제42조 기재요건 준수):
- 독립항은 발명의 핵심 구성요소만으로 간결하게 작성하되, 특허성 판단에서 도출된
  '차별점(distinguishing_features)'을 반드시 한정사항으로 포함하여 선행문헌과 구별되게 합니다.
- 종속항은 독립항을 인용하며 바람직한 실시형태(부가적 한정)를 단계적으로 추가합니다.
  ("제1항에 있어서, ...")
- 청구항은 단일 문장의 명료한 구성요소 나열 형식으로 작성합니다.
- 가능하면 물건(장치/시스템) 청구항과 방법 청구항을 함께 제시해 권리범위를 넓힙니다.
- 배경기술은 선행문헌이 가진 한계를 서술하되, 특정 문헌을 비방하지 않습니다.
- '발명을 실시하기 위한 구체적인 내용'은 통상의 기술자가 재현할 수 있을 만큼 구체적으로 씁니다.
- 명세서 전체에서 청구항에 사용된 용어와 상세설명의 용어를 일치시킵니다.
- 한국어로 작성합니다.

반드시 지정된 JSON 스키마로만 응답하세요."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "description": "발명의 명칭"},
        "technical_field": {"type": "string"},
        "background": {"type": "string", "description": "배경기술"},
        "problem": {"type": "string", "description": "발명이 해결하려는 과제"},
        "solution": {"type": "string", "description": "과제의 해결 수단"},
        "effects": {"type": "string", "description": "발명의 효과"},
        "detailed_description": {
            "type": "string",
            "description": "발명을 실시하기 위한 구체적인 내용",
        },
        "independent_claims": {
            "type": "array",
            "items": {"type": "string"},
            "description": "독립항(장치/방법 등)",
        },
        "dependent_claims": {
            "type": "array",
            "items": {"type": "string"},
            "description": "종속항",
        },
        "abstract": {"type": "string", "description": "요약서"},
    },
    "required": [
        "title",
        "technical_field",
        "background",
        "problem",
        "solution",
        "effects",
        "detailed_description",
        "independent_claims",
        "dependent_claims",
        "abstract",
    ],
}


def draft_specification(
    llm: LLM,
    idea: Idea,
    assessment: PatentabilityAssessment,
    analyses: list[PriorArtAnalysis],
) -> PatentDraft:
    feats = "\n".join(f"  - {f}" for f in idea.key_features)
    diff = "\n".join(f"  - {f}" for f in assessment.distinguishing_features)
    recs = "\n".join(f"  - {f}" for f in assessment.recommendations)
    prior_titles = "\n".join(
        f"  - {a.prior_art.title} ({a.prior_art.identifier}): "
        f"차별 구성 {', '.join(a.distinguishing_features) or '미상'}"
        for a in analyses[:8]
    )

    user = (
        f"# 발명 아이디어\n"
        f"명칭(가안): {idea.title}\n"
        f"기술분야: {idea.technical_field}\n"
        f"해결과제: {idea.problem}\n"
        f"해결수단: {idea.solution}\n"
        f"핵심 구성요소:\n{feats}\n"
        f"기대 효과: {', '.join(idea.effects)}\n\n"
        f"# 특허성 판단\n"
        f"신규성: {assessment.novelty_conclusion}\n"
        f"진보성: {assessment.inventive_step_conclusion}\n"
        f"등록 포인트(독립항에 반드시 반영할 차별점):\n{diff}\n"
        f"보정 권고:\n{recs}\n\n"
        f"# 주요 선행문헌\n{prior_titles or '(없음)'}\n\n"
        "위 정보를 바탕으로 출원 가능한 한국 특허 명세서 초안을 작성하세요. "
        "독립항에는 등록 포인트를 반드시 한정으로 포함하세요."
    )

    # 명세서는 출력이 길 수 있으므로 JSON 스키마 + 넉넉한 토큰.
    data = llm.complete_json(SYSTEM, user, SCHEMA, max_tokens=20000)

    return PatentDraft(
        title=data.get("title", idea.title),
        technical_field=data.get("technical_field", ""),
        background=data.get("background", ""),
        problem=data.get("problem", ""),
        solution=data.get("solution", ""),
        effects=data.get("effects", ""),
        detailed_description=data.get("detailed_description", ""),
        independent_claims=data.get("independent_claims", []),
        dependent_claims=data.get("dependent_claims", []),
        abstract=data.get("abstract", ""),
    )
