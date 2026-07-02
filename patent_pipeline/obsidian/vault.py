"""파이프라인 결과를 Obsidian 마크다운 노트로 출력.

각 발명마다 하나의 폴더를 만들고, 그 안에 서로 위키링크([[...]])로 연결된
- 개요(MOC), 아이디어, 선행문헌(각 1노트), 비교분석, 특허성 판단, 명세서 초안
노트를 생성한다. 프론트매터의 태그/속성으로 그래프 뷰와 검색이 가능하다.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ..models import (
    Idea,
    PatentabilityAssessment,
    PatentDraft,
    PipelineResult,
    PriorArt,
    PriorArtAnalysis,
)


def _safe_filename(name: str, max_len: int = 80) -> str:
    name = re.sub(r"[\\/:*?\"<>|#\^\[\]]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name[:max_len].strip() or "untitled")


def _frontmatter(props: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in props.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


_RISK_BADGE = {"high": "🔴 높음", "medium": "🟡 보통", "low": "🟢 낮음"}


class VaultWriter:
    def __init__(self, vault_path: str | Path, folder: str = "Patents"):
        self.root = Path(vault_path).expanduser()
        self.folder = folder

    def write(self, result: PipelineResult) -> list[str]:
        idea = result.idea
        case_name = _safe_filename(idea.title or "발명")
        stamp = datetime.now().strftime("%Y%m%d")
        case_dir = self.root / self.folder / f"{stamp} {case_name}"
        case_dir.mkdir(parents=True, exist_ok=True)

        written: list[str] = []

        idea_note = self._idea_note(idea)
        written.append(self._save(case_dir, f"{case_name} - 아이디어", idea_note))

        prior_links: list[str] = []
        for art in result.prior_art:
            analysis = next(
                (a for a in result.analyses if a.prior_art.identifier == art.identifier),
                None,
            )
            note_title = f"선행문헌 - {_safe_filename(art.title or art.identifier, 60)}"
            written.append(self._save(case_dir, note_title, self._prior_art_note(art, analysis)))
            prior_links.append(note_title)

        if result.assessment:
            written.append(
                self._save(
                    case_dir,
                    f"{case_name} - 특허성 판단",
                    self._assessment_note(idea, result.assessment),
                )
            )

        if result.draft:
            written.append(
                self._save(
                    case_dir,
                    f"{case_name} - 명세서 초안",
                    self._draft_note(idea, result.draft),
                )
            )

        moc = self._moc_note(result, case_name, prior_links)
        written.append(self._save(case_dir, f"{case_name} - 개요 (MOC)", moc))

        return written

    # ---- 저장 ----
    def _save(self, directory: Path, title: str, content: str) -> str:
        path = directory / f"{_safe_filename(title)}.md"
        path.write_text(content, encoding="utf-8")
        return str(path)

    # ---- 노트 본문 ----
    def _moc_note(self, result: PipelineResult, case_name: str, prior_links: list[str]) -> str:
        a = result.assessment
        likelihood = _RISK_BADGE.get(a.registration_likelihood, a.registration_likelihood) if a else "미평가"
        fm = _frontmatter(
            {
                "type": "patent-moc",
                "발명": case_name,
                "생성일": result.created_at,
                "등록가능성": a.registration_likelihood if a else "unknown",
                "tags": ["특허", "MOC"],
            }
        )
        lines = [
            fm,
            "",
            f"# {case_name} — 개요",
            "",
            "> 이 노트는 발명 1건의 특허 검토 결과를 묶는 지도(Map of Content)입니다.",
            "",
            "## 핵심 노트",
            f"- [[{case_name} - 아이디어]]",
            f"- [[{case_name} - 특허성 판단]]"
            + (f" — 등록 가능성: **{likelihood}**" if a else ""),
            f"- [[{case_name} - 명세서 초안]]" if result.draft else "",
            "",
            f"## 선행문헌 ({len(prior_links)}건)",
        ]
        lines += [f"- [[{t}]]" for t in prior_links] or ["- (검색 결과 없음)"]
        if a:
            lines += ["", "## 등록 포인트(차별점)"]
            lines += [f"- {d}" for d in a.distinguishing_features] or ["- (없음)"]
        return "\n".join([ln for ln in lines if ln is not None])

    def _idea_note(self, idea: Idea) -> str:
        fm = _frontmatter(
            {
                "type": "patent-idea",
                "명칭": idea.title,
                "기술분야": idea.technical_field,
                "tags": ["특허", "아이디어"] + [f"kw/{k}" for k in idea.keywords_ko[:6]],
            }
        )
        feats = "\n".join(f"- {f}" for f in idea.key_features) or "- (없음)"
        effects = "\n".join(f"- {e}" for e in idea.effects) or "- (없음)"
        return "\n".join(
            [
                fm,
                "",
                f"# {idea.title}",
                "",
                "## 기술분야",
                idea.technical_field,
                "",
                "## 해결하려는 과제",
                idea.problem,
                "",
                "## 과제 해결 수단",
                idea.solution,
                "",
                "## 핵심 구성요소",
                feats,
                "",
                "## 기대 효과",
                effects,
                "",
                "## 검색 키워드",
                f"- 국문: {', '.join(idea.keywords_ko) or '(없음)'}",
                f"- 영문: {', '.join(idea.keywords_en) or '(없음)'}",
                f"- IPC 추정: {', '.join(idea.ipc_hints) or '(없음)'}",
                "",
                "## 원문",
                "```",
                idea.raw_text.strip(),
                "```",
            ]
        )

    def _prior_art_note(self, art: PriorArt, analysis: PriorArtAnalysis | None) -> str:
        is_paper = art.source == "OpenAlex"
        kind_tag = "논문" if is_paper else "특허"
        fm = _frontmatter(
            {
                "type": "prior-art",
                "출처": art.source,
                "출원번호": art.application_number or "-",
                "등록번호": art.registration_number or "-",
                "저자_출원인" if is_paper else "출원인": art.applicant or "-",
                "법적상태": art.status or "-",
                "관련도점수": art.score,
                "tags": ["선행문헌", kind_tag],
            }
        )
        if is_paper:
            meta = [
                f"- 출처: {art.source} (학술 논문)",
                f"- 저자: {art.applicant or '-'}",
                f"- 발행연도: {art.application_date or '-'}",
                f"- 유형: {art.status or '-'}",
                f"- 원문/DOI: {art.url}" if art.url else "",
            ]
        else:
            meta = [
                f"- 출처: {art.source}",
                f"- 출원번호: {art.application_number or '-'}",
                f"- 등록번호: {art.registration_number or '-'}",
                f"- 공개번호: {art.publication_number or '-'}",
                f"- 출원인: {art.applicant or '-'}",
                f"- 출원일: {art.application_date or '-'}",
                f"- IPC: {art.ipc or '-'}",
                f"- 법적상태: {art.status or '-'}",
                f"- 원문 링크: {art.url}" if art.url else "",
            ]
        body = [
            fm,
            "",
            f"# {art.title}",
            "",
            *meta,
            "",
            "## 초록",
            art.abstract or "(없음)",
        ]
        if art.claims:
            body += ["", "## 청구범위", "```", art.claims[:4000], "```"]
        if analysis:
            body += [
                "",
                "## 우리 발명과의 비교",
                f"- **관련성**: {analysis.relevance}",
                f"- **신규성 위협**: {_RISK_BADGE.get(analysis.novelty_risk, analysis.novelty_risk)}",
                f"- **진보성 위협**: {_RISK_BADGE.get(analysis.inventive_step_risk, analysis.inventive_step_risk)}",
                "",
                "### 겹치는 구성",
                "\n".join(f"- {f}" for f in analysis.overlapping_features) or "- (없음)",
                "",
                "### 우리 발명의 차별 구성",
                "\n".join(f"- {f}" for f in analysis.distinguishing_features) or "- (없음)",
                "",
                "### 비고",
                analysis.notes or "(없음)",
            ]
        return "\n".join([ln for ln in body if ln is not None])

    def _assessment_note(self, idea: Idea, a: PatentabilityAssessment) -> str:
        fm = _frontmatter(
            {
                "type": "patentability",
                "발명": idea.title,
                "등록가능성": a.registration_likelihood,
                "tags": ["특허", "특허성판단"],
            }
        )
        closest = "\n".join(f"- [[선행문헌 - {c}]] / {c}" for c in a.closest_prior_art) or "- (없음)"
        return "\n".join(
            [
                fm,
                "",
                f"# {idea.title} — 특허성 판단",
                "",
                f"## 등록 가능성: {_RISK_BADGE.get(a.registration_likelihood, a.registration_likelihood)}",
                "",
                "## 신규성 (특허법 제29조 제1항)",
                a.novelty_conclusion,
                "",
                "## 진보성 (특허법 제29조 제2항)",
                a.inventive_step_conclusion,
                "",
                "## 가장 가까운 선행문헌",
                closest,
                "",
                "## 등록 포인트(핵심 차별점)",
                "\n".join(f"- {d}" for d in a.distinguishing_features) or "- (없음)",
                "",
                "## 위험 요소",
                "\n".join(f"- {r}" for r in a.risks) or "- (없음)",
                "",
                "## 등록 전략 / 보정 권고",
                "\n".join(f"- {r}" for r in a.recommendations) or "- (없음)",
                "",
                "## 종합 판단 근거",
                a.rationale,
            ]
        )

    def _draft_note(self, idea: Idea, d: PatentDraft) -> str:
        fm = _frontmatter(
            {
                "type": "patent-draft",
                "명칭": d.title,
                "tags": ["특허", "명세서초안"],
            }
        )
        claims_block = []
        n = 1
        for c in d.independent_claims:
            claims_block.append(f"**【청구항 {n}】** {c}")
            n += 1
        for c in d.dependent_claims:
            claims_block.append(f"**【청구항 {n}】** {c}")
            n += 1
        claims = "\n\n".join(claims_block) or "(없음)"
        return "\n".join(
            [
                fm,
                "",
                f"# {d.title}",
                "",
                "> ⚠️ 본 초안은 AI가 생성한 검토용 자료입니다. 출원 전 변리사 검토가 필요합니다.",
                "",
                "## 【발명의 명칭】",
                d.title,
                "",
                "## 【기술분야】",
                d.technical_field,
                "",
                "## 【배경기술】",
                d.background,
                "",
                "## 【발명이 해결하려는 과제】",
                d.problem,
                "",
                "## 【과제의 해결 수단】",
                d.solution,
                "",
                "## 【발명의 효과】",
                d.effects,
                "",
                "## 【발명을 실시하기 위한 구체적인 내용】",
                d.detailed_description,
                "",
                "## 【청구범위】",
                claims,
                "",
                "## 【요약서】",
                d.abstract,
                "",
                "---",
                f"관련: [[{_safe_filename(idea.title)} - 특허성 판단]]",
            ]
        )
