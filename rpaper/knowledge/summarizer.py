"""참고문헌 요약 생성. LLM 가능하면 사용, 아니면 abstract 앞부분으로 폴백."""
from __future__ import annotations

from ..integrations import llm


def summarize_reference(ref: dict, *, api_key: str = "", model: str = "claude-fable-5") -> str:
    abstract = ref.get("abstract", "")
    if not abstract:
        return "_abstract 없음 — 원문 확인 필요_"
    prompt = (
        "다음 논문 초록을 연구 위키용으로 한국어 4~6문장으로 요약하라. "
        "연구 목적, 방법, 핵심 결과, 한계/시사점을 포함하라.\n\n"
        f"제목: {ref.get('title','')}\n초록: {abstract}"
    )
    out = llm.complete(prompt, api_key=api_key, model=model, max_tokens=600)
    if out:
        return out.strip()
    # 폴백: 초록 앞 2문장
    sents = abstract.replace("\n", " ").split(". ")
    return ". ".join(sents[:2]).strip() + ("." if sents else "")
