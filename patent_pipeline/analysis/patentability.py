"""4단계: 신규성·진보성 종합 판단 및 등록 전략 제시."""

from __future__ import annotations

from ..llm import LLM
from ..models import Idea, PriorArtAnalysis, PatentabilityAssessment

SYSTEM = """당신은 한국 특허 등록 전략에 정통한 변리사입니다.
발명 아이디어와, 여러 선행문헌에 대한 개별 비교 분석 결과를 종합하여
특허성(신규성·진보성)을 최종 판단하고, 실제 '등록'까지 갈 수 있도록 전략을 제시합니다.

판단 원칙:
- 신규성(특허법 제29조 제1항): 단일 선행문헌이 발명의 모든 구성요소를 개시하면 신규성 부정.
- 진보성(특허법 제29조 제2항): 가장 가까운 선행문헌(주인용발명)을 기준으로,
  복수 선행문헌의 결합 용이성과 효과의 현저성을 함께 판단. 사후적 고찰(hindsight)을 경계.
- distinguishing_features 에는 '등록 포인트'가 될 핵심 차별 구성을 구체적으로 적습니다.
  이는 독립항에 반드시 반영되어야 하는 한정사항입니다.
- recommendations 에는 등록 가능성을 높이기 위한 청구항 보정 방향
  (한정 추가, 구성 결합, 효과 강조, 카테고리 분리 등)을 실무적으로 제시합니다.
- registration_likelihood 는 현재 아이디어 상태에서의 등록 가능성입니다.
- 과장하지 말고, 위협이 큰 선행문헌이 있으면 risks 에 분명히 기재합니다."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "novelty_conclusion": {"type": "string"},
        "inventive_step_conclusion": {"type": "string"},
        "closest_prior_art": {"type": "array", "items": {"type": "string"}},
        "distinguishing_features": {"type": "array", "items": {"type": "string"}},
        "registration_likelihood": {"type": "string", "enum": ["high", "medium", "low"]},
        "risks": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": [
        "novelty_conclusion",
        "inventive_step_conclusion",
        "closest_prior_art",
        "distinguishing_features",
        "registration_likelihood",
        "risks",
        "recommendations",
        "rationale",
    ],
}


def _format_analyses(analyses: list[PriorArtAnalysis]) -> str:
    blocks = []
    for a in analyses:
        art = a.prior_art
        blocks.append(
            f"## {art.title} ({art.identifier})\n"
            f"- 출원인: {art.applicant} / 상태: {art.status}\n"
            f"- 관련성: {a.relevance}\n"
            f"- 겹치는 구성: {', '.join(a.overlapping_features) or '없음'}\n"
            f"- 차별 구성: {', '.join(a.distinguishing_features) or '없음'}\n"
            f"- 신규성 위협: {a.novelty_risk} / 진보성 위협: {a.inventive_step_risk}\n"
            f"- 비고: {a.notes}"
        )
    return "\n\n".join(blocks)


def assess_patentability(
    llm: LLM,
    idea: Idea,
    analyses: list[PriorArtAnalysis],
) -> PatentabilityAssessment:
    feats = "\n".join(f"  - {f}" for f in idea.key_features)
    user = (
        f"# 발명 아이디어\n"
        f"명칭: {idea.title}\n"
        f"해결과제: {idea.problem}\n"
        f"해결수단: {idea.solution}\n"
        f"핵심 구성요소:\n{feats}\n\n"
        f"# 선행문헌 비교 분석 ({len(analyses)}건)\n"
        f"{_format_analyses(analyses) or '(분석된 선행문헌 없음)'}\n\n"
        "위 자료를 종합하여 신규성·진보성을 최종 판단하고 등록 전략을 제시해 주세요."
    )
    data = llm.complete_json(SYSTEM, user, SCHEMA, max_tokens=10000)
    return PatentabilityAssessment(
        novelty_conclusion=data.get("novelty_conclusion", ""),
        inventive_step_conclusion=data.get("inventive_step_conclusion", ""),
        closest_prior_art=data.get("closest_prior_art", []),
        distinguishing_features=data.get("distinguishing_features", []),
        registration_likelihood=data.get("registration_likelihood", "medium"),
        risks=data.get("risks", []),
        recommendations=data.get("recommendations", []),
        rationale=data.get("rationale", ""),
    )
