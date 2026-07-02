"""2~3단계: 선행문헌 스크리닝과 개별 비교 분석."""

from __future__ import annotations

import concurrent.futures as futures

from ..llm import LLM
from ..models import Idea, PriorArt, PriorArtAnalysis

# ---- 스크리닝(관련도 점수) ----

SCREEN_SYSTEM = """당신은 선행기술 조사 전문가입니다. 발명 아이디어와 선행문헌 목록을 보고,
각 문헌이 그 아이디어의 신규성·진보성 판단에 얼마나 중요한지를 0~100 점으로 평가합니다.
명칭과 초록만으로 판단하되, 기술적 구성요소의 유사성을 기준으로 합니다.
표면적 키워드 일치가 아니라 '같은 문제를 같은 방식으로 푸는가'를 봅니다."""

SCREEN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "index": {"type": "integer"},
                    "score": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["index", "score", "reason"],
            },
        }
    },
    "required": ["scores"],
}


def _idea_brief(idea: Idea) -> str:
    feats = "\n".join(f"  - {f}" for f in idea.key_features)
    return (
        f"발명의 명칭: {idea.title}\n"
        f"기술분야: {idea.technical_field}\n"
        f"해결과제: {idea.problem}\n"
        f"해결수단: {idea.solution}\n"
        f"핵심 구성요소:\n{feats}"
    )


SCREEN_BATCH_SIZE = 40  # 프롬프트 크기를 안정적인 범위로 유지하기 위한 배치 단위


def screen_prior_art(llm: LLM, idea: Idea, arts: list[PriorArt], top_n: int) -> list[PriorArt]:
    """명칭/초록 기준으로 관련도 점수를 매겨 상위 N건을 고른다.

    선행문헌이 많을 때 한 번의 LLM 호출에 전부 담으면 프롬프트가 비대해져
    시간초과·실패 위험이 커지므로, SCREEN_BATCH_SIZE 단위로 나눠 채점한다.
    """
    if not arts:
        return []

    for start in range(0, len(arts), SCREEN_BATCH_SIZE):
        batch = arts[start : start + SCREEN_BATCH_SIZE]
        listing = "\n".join(
            f"[{i}] {a.title}\n    초록: {(a.abstract or '(없음)')[:400]}"
            for i, a in enumerate(batch)
        )
        user = (
            f"# 발명 아이디어\n{_idea_brief(idea)}\n\n"
            f"# 선행문헌 목록 ({len(batch)}건)\n{listing}\n\n"
            "각 문헌의 index 와 score(0~100), 한 줄 reason 을 매겨 주세요."
        )
        data = llm.complete_json(SCREEN_SYSTEM, user, SCREEN_SCHEMA, max_tokens=8000)
        for entry in data.get("scores", []):
            idx = entry.get("index")
            if isinstance(idx, int) and 0 <= idx < len(batch):
                batch[idx].score = float(entry.get("score", 0))

    ranked = sorted(arts, key=lambda a: a.score, reverse=True)
    return ranked[:top_n]


# ---- 개별 비교 분석 ----

ANALYZE_SYSTEM = """당신은 한국 변리사입니다. 발명 아이디어 1건과 선행문헌 1건을 비교하여,
특허법 제29조의 신규성·진보성 관점에서 분석합니다.

판단 기준:
- 신규성(제29조 제1항): 선행문헌이 우리 발명의 모든 구성요소를 그대로 개시하는가?
  하나라도 개시되지 않은 구성요소가 있으면 신규성은 인정될 여지가 있습니다.
- 진보성(제29조 제2항): 통상의 기술자가 선행문헌으로부터 우리 발명을 '용이하게'
  도출할 수 있는가? 구성의 곤란성, 효과의 현저성을 함께 봅니다.
- overlapping_features 에는 선행문헌과 겹치는 구성을, distinguishing_features 에는
  우리 발명만이 갖는 차별적 구성을 구체적으로 적습니다.
- novelty_risk / inventive_step_risk 는 그 선행문헌이 우리 발명의 등록을 위협하는 정도입니다
  (high = 강하게 위협, low = 거의 위협 안 됨).

근거 없는 단정은 피하고, 청구항 구성요소 단위로 대비하세요."""

ANALYZE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "relevance": {"type": "string"},
        "overlapping_features": {"type": "array", "items": {"type": "string"}},
        "distinguishing_features": {"type": "array", "items": {"type": "string"}},
        "novelty_risk": {"type": "string", "enum": ["high", "medium", "low"]},
        "inventive_step_risk": {"type": "string", "enum": ["high", "medium", "low"]},
        "notes": {"type": "string"},
    },
    "required": [
        "relevance",
        "overlapping_features",
        "distinguishing_features",
        "novelty_risk",
        "inventive_step_risk",
        "notes",
    ],
}


def _analyze_one(llm: LLM, idea: Idea, art: PriorArt) -> PriorArtAnalysis:
    user = (
        f"# 우리 발명 아이디어\n{_idea_brief(idea)}\n\n"
        f"# 선행문헌\n"
        f"명칭: {art.title}\n"
        f"출원번호: {art.application_number} / 등록번호: {art.registration_number}\n"
        f"출원인: {art.applicant}\n"
        f"법적상태: {art.status}\n"
        f"초록: {art.abstract or '(없음)'}\n"
        f"청구범위: {(art.claims or '(미조회)')[:3000]}\n\n"
        "위 선행문헌을 우리 발명과 구성요소 단위로 대비 분석해 주세요."
    )
    data = llm.complete_json(ANALYZE_SYSTEM, user, ANALYZE_SCHEMA, max_tokens=6000)
    return PriorArtAnalysis(
        prior_art=art,
        relevance=data.get("relevance", ""),
        overlapping_features=data.get("overlapping_features", []),
        distinguishing_features=data.get("distinguishing_features", []),
        novelty_risk=data.get("novelty_risk", "medium"),
        inventive_step_risk=data.get("inventive_step_risk", "medium"),
        notes=data.get("notes", ""),
    )


def analyze_prior_art(
    llm: LLM,
    idea: Idea,
    arts: list[PriorArt],
    concurrency: int = 4,
) -> list[PriorArtAnalysis]:
    """상위 선행문헌들을 병렬로 비교 분석한다."""
    if not arts:
        return []
    results: list[PriorArtAnalysis] = []
    with futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        jobs = {pool.submit(_analyze_one, llm, idea, art): art for art in arts}
        for fut in futures.as_completed(jobs):
            try:
                results.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                art = jobs[fut]
                results.append(
                    PriorArtAnalysis(
                        prior_art=art,
                        relevance=f"(분석 실패: {exc})",
                        novelty_risk="medium",
                        inventive_step_risk="medium",
                    )
                )
    # 위협도 높은 순으로 정렬(high>medium>low)
    order = {"high": 0, "medium": 1, "low": 2}
    results.sort(key=lambda a: order.get(a.inventive_step_risk, 1))
    return results
