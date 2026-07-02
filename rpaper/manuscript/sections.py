"""원고 섹션 작성 — Introduction -> Methods -> Results -> Discussion -> Conclusion.

각 섹션은 위키(참고문헌 요약 + figure 결과)를 근거로 LLM 초안을 생성합니다.
LLM 미설정 시, 인용 골격과 체크리스트가 담긴 템플릿을 반환합니다.
"""
from __future__ import annotations

from ..integrations import llm


def _refs_context(refs: list[dict], summaries: list[str]) -> str:
    lines = []
    for i, (r, s) in enumerate(zip(refs, summaries), start=1):
        lines.append(f"[{i}] {r.get('title','')} ({r.get('year','')}) — {s}")
    return "\n".join(lines)


def write_introduction(title: str, keywords: list[str], refs: list[dict],
                       summaries: list[str], *, api_key: str = "",
                       model: str = "claude-fable-5") -> str:
    ctx = _refs_context(refs, summaries)
    prompt = (
        f"연구 제목: {title}\n키워드: {', '.join(keywords)}\n\n"
        f"아래 참고문헌 요약을 근거로 학술 논문 Introduction 을 작성하라. "
        f"각 주장 뒤에 [번호] 로 인용하라. 배경 -> 문제정의 -> 연구공백 -> 본 연구 목적 순서.\n\n"
        f"참고문헌:\n{ctx}"
    )
    out = llm.complete(prompt, api_key=api_key, model=model, max_tokens=2500)
    if out:
        return f"# Introduction\n\n{out.strip()}\n"
    return ("# Introduction\n\n"
            "_LLM 미설정 — 아래 골격을 직접 채우세요._\n\n"
            "1. 배경 (인용: [1], [2])\n2. 문제 정의\n3. 연구 공백\n4. 본 연구 목적/가설\n")


def write_methods(title: str, refs: list[dict], summaries: list[str],
                  protocol_notes: str = "", *, api_key: str = "",
                  model: str = "claude-fable-5") -> str:
    ctx = _refs_context(refs, summaries)
    prompt = (
        f"연구 제목: {title}\n\n"
        f"아래 참고문헌에서 확인된 최신 실험기법/방법을 근거로 Materials & Methods 를 작성하라. "
        f"재현 가능하도록 시약/장비/통계분석(유의수준 포함)을 구체적으로. 방법 출처는 [번호] 인용.\n\n"
        f"연구자 메모: {protocol_notes or '(없음)'}\n\n참고문헌:\n{ctx}"
    )
    out = llm.complete(prompt, api_key=api_key, model=model, max_tokens=2500)
    if out:
        return f"# Materials and Methods\n\n{out.strip()}\n"
    return ("# Materials and Methods\n\n_LLM 미설정 — 골격._\n\n"
            "## Study design\n## Materials\n## Procedures (인용 [n])\n## Statistical analysis\n")


def write_results(title: str, figures: list[dict], stats_summary: str, *,
                  api_key: str = "", model: str = "claude-fable-5") -> str:
    fig_lines = "\n".join(
        f"Figure {i}: {f.get('caption','')} (파일: {f.get('figure','')})"
        for i, f in enumerate(figures, start=1)
    )
    prompt = (
        f"연구 제목: {title}\n\nFigure 순서와 통계 결과를 바탕으로 Results 를 작성하라. "
        f"각 Figure 를 순서대로 서술하고 유의성(p값)을 명시. 해석은 최소화(객관적 기술).\n\n"
        f"Figures:\n{fig_lines}\n\n통계 결과:\n{stats_summary}"
    )
    out = llm.complete(prompt, api_key=api_key, model=model, max_tokens=2500)
    if out:
        return f"# Results\n\n{out.strip()}\n"
    return f"# Results\n\n_LLM 미설정._\n\n{fig_lines}\n\n{stats_summary}\n"


def write_discussion(title: str, refs: list[dict], summaries: list[str],
                     results_text: str, *, api_key: str = "",
                     model: str = "claude-fable-5") -> str:
    ctx = _refs_context(refs, summaries)
    prompt = (
        f"연구 제목: {title}\n\nResults 와 선행연구를 비교하여 Discussion 을 작성하라. "
        f"(Conclusion 은 쓰지 말 것 — 별도 섹션) "
        f"핵심 발견 -> 선행연구와 비교([번호]) -> 기전/해석 -> 한계 순서.\n\n"
        f"Results:\n{results_text}\n\n참고문헌:\n{ctx}"
    )
    out = llm.complete(prompt, api_key=api_key, model=model, max_tokens=3000)
    if out:
        return f"# Discussion\n\n{out.strip()}\n"
    return ("# Discussion\n\n_LLM 미설정 — 골격._\n\n"
            "## 핵심 발견\n## 선행연구 비교 [n]\n## 기전/해석\n## 한계\n")


def write_conclusion(title: str, results_text: str, discussion_text: str, *,
                     api_key: str = "", model: str = "claude-fable-5") -> str:
    prompt = (
        f"연구 제목: {title}\n\n아래 Results 와 Discussion 을 근거로 간결한 Conclusion 을 "
        f"작성하라(3~5문장). 핵심 발견의 의의와 향후 연구 방향을 포함하되 과장하지 말 것.\n\n"
        f"Results:\n{results_text}\n\nDiscussion:\n{discussion_text}"
    )
    out = llm.complete(prompt, api_key=api_key, model=model, max_tokens=800)
    if out:
        return f"# Conclusion\n\n{out.strip()}\n"
    return ("# Conclusion\n\n_LLM 미설정 — 골격._\n\n"
            "핵심 발견 요약 / 의의 / 향후 연구 방향을 3~5문장으로.\n")
