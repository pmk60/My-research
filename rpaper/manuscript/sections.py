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


def pair_figure_stats(figures: list[dict], stats_data: list[dict]) -> list[dict]:
    """figures.json 과 stats_all.json 의 캐시를 value(변수명) 기준으로 짝짓기.

    각 항목은 ``{"figure": <figures.json 항목 또는 None>, "stats": <stats_all.json 항목 또는 None>}``.
    - value 가 같은 통계 후보가 여러 개면 figure 의 group 컬럼이 일치하는 것을 우선.
    - 도표만 있거나 통계만 있는 항목도 그대로 포함(Results 가 놓치지 않도록).
    """
    by_value: dict[str, list[dict]] = {}
    for s in stats_data or []:
        by_value.setdefault(s.get("value") or "", []).append(s)

    pairs: list[dict] = []
    consumed: set[int] = set()
    for f in figures or []:
        value = f.get("value") or ""
        s = None
        cands = [c for c in by_value.get(value, []) if id(c) not in consumed]
        if len(cands) == 1:
            s = cands[0]
        elif len(cands) > 1:
            g = f.get("group") or ""
            s = next((c for c in cands if (c.get("group") or "") == g), cands[0])
        if s is not None:
            consumed.add(id(s))
        pairs.append({"figure": f, "stats": s})

    for s in stats_data or []:
        if id(s) not in consumed:
            pairs.append({"figure": None, "stats": s})
    return pairs


def _fmt_stats_desc(s: dict | None) -> list[str]:
    """통계 항목(또는 오류 항목)을 사람이 읽는 줄들로."""
    if not s:
        return ["- **통계 검정**: (analyze 캐시 없음 — `rpaper analyze` 실행 후 재작성)"]
    if s.get("error"):
        return [f"- **통계 검정**: 오류 — {s['error']}"]
    sig = s.get("significant")
    sig_txt = ("유의함" if sig else "유의하지 않음") if sig is not None else "판정 없음"
    lines = [f"- **통계 검정**: {s.get('test', '검정 미확인')}"
             f" — 통계량={s.get('statistic', '?')}, p={s.get('p_value', '?')} → **{sig_txt}**"]
    means = s.get("means") or {}
    if means:
        m = ", ".join(f"{k}={v:.3g}" for k, v in means.items())
        lines.append(f"- **그룹별 평균**: {m}")
    if s.get("engine"):
        lines.append(f"- (엔진: {s['engine']})")
    return lines


def _fmt_pair_for_prompt(i: int, fig: dict | None, s: dict | None) -> str:
    lines = []
    if fig:
        lines.append(f"Figure {i} [{fig.get('value') or '변수 미지정'}]:")
        lines.append(f"  - 도표: {fig.get('kind', 'plot')} (파일: {fig.get('figure', '')})")
        if fig.get("caption"):
            lines.append(f"  - 캡션: {fig['caption']}")
        if fig.get("group"):
            lines.append(f"  - 그룹 컬럼: {fig['group']}")
    else:
        lines.append(f"[Figure 없음] 통계만 캐시된 변수 [{(s or {}).get('value') or '?'}]:")
    lines.extend("  " + ln for ln in _fmt_stats_desc(s))
    return "\n".join(lines)


def write_results(title: str, pairs: list[dict], *,
                  api_key: str = "", model: str = "claude-fable-5") -> str:
    """Results 섹션 작성. ``pairs`` 는 ``pair_figure_stats`` 의 결과(figure+통계 캐시 매칭).

    LLM 있음: Figure별 도표 설명과 대응 통계(검정 방법/통계량/p값/그룹별 평균)를
    짝지어 서술하도록 정교화된 프롬프트로 초안 생성.
    LLM 없음: 각 Figure마다 마크다운 이미지 + 매핑된 통계 검정 결과가 담긴 골격 반환.
    """
    ctx = "\n\n".join(
        _fmt_pair_for_prompt(i, p.get("figure"), p.get("stats"))
        for i, p in enumerate(pairs, start=1)
    ) or "(analyze/figure 산출물 없음)"

    prompt = (
        f"연구 제목: {title}\n\n"
        f"아래는 도표(figure)와 통계분석 결과를 변수명 기준으로 짝지어 놓은 목록입니다. "
        f"Results 본문을 작성하라:\n"
        f"1. Figure 가 있는 항목은 각 Figure 를 순서대로 서술하고, 같은 짝의 통계분석 결과"
        f"(검정 방법, 검정통계량, p-value, 그룹별 평균)를 함께 문장으로 녹일 것.\n"
        f"2. 유의성(p값)을 정확히 명시하고, 해석은 최소화(객관적 기술).\n"
        f"3. 도표 없이 통계만 있는 항목도 본문에서 함께 보고할 것.\n\n"
        f"짝지어진 결과:\n{ctx}"
    )
    out = llm.complete(prompt, api_key=api_key, model=model, max_tokens=2500)
    if out:
        return f"# Results\n\n{out.strip()}\n"

    # 폴백: 체계적으로 매핑된 마크다운 골격
    parts = ["# Results\n",
             "_LLM 미설정 — analyze/figure 캐시를 자동 매칭한 골격입니다. "
             "각 항목의 해석 문장을 직접 추가하세요._\n"]
    n = 0
    stats_only: list[dict] = []
    for p in pairs:
        fig, s = p.get("figure"), p.get("stats")
        if fig:
            n += 1
            parts.append(f"### Figure {n} — {fig.get('value') or '변수 미지정'}\n")
            if fig.get("figure"):
                parts.append(f"![Figure {n}]({fig['figure']})\n")
            desc = fig.get("caption") or fig.get("kind", "plot")
            parts.append(f"- **도표**: {desc}")
            if fig.get("group"):
                parts.append(f"- **그룹/비교**: {fig['group']} 기준 비교")
            parts.extend(_fmt_stats_desc(s))
            parts.append("")
        else:
            stats_only.append(s)
    if stats_only:
        parts.append("### 통계 결과만 있는 항목 (도표 미생성)\n")
        for s in stats_only:
            parts.append(f"**{s.get('value') or '?'}**:")
            parts.extend(_fmt_stats_desc(s))
            parts.append("")
    if n == 0 and not stats_only:
        parts.append("(analyze/figure 산출물이 없습니다. `rpaper analyze` 와 `rpaper figure` 를 먼저 실행하세요.)\n")
    return "\n".join(parts) + "\n"


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
