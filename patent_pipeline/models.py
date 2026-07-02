"""파이프라인 전 단계에서 주고받는 데이터 모델."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


def _slugify(text: str, max_len: int = 60) -> str:
    """파일명/노트 제목에 안전한 슬러그. 한글은 보존한다."""
    text = text.strip()
    text = re.sub(r"[\\/:*?\"<>|#^\[\]]", "", text)  # Obsidian/파일시스템 금지문자
    text = re.sub(r"\s+", " ", text)
    return text[:max_len].strip() or "untitled"


@dataclass
class Idea:
    """사용자의 원시 아이디어를 구조화한 결과."""

    raw_text: str
    title: str = ""
    technical_field: str = ""           # 기술분야
    problem: str = ""                   # 해결하고자 하는 과제
    solution: str = ""                  # 과제 해결 수단 요지
    key_features: list[str] = field(default_factory=list)   # 핵심 구성요소/특징
    effects: list[str] = field(default_factory=list)        # 기대 효과
    keywords_ko: list[str] = field(default_factory=list)
    keywords_en: list[str] = field(default_factory=list)
    ipc_hints: list[str] = field(default_factory=list)      # 추정 IPC 분류

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PriorArt:
    """선행문헌 1건. KIPRIS 검색/상세 결과를 담는다."""

    application_number: str = ""        # 출원번호
    registration_number: str = ""       # 등록번호
    publication_number: str = ""        # 공개번호
    title: str = ""
    abstract: str = ""
    applicant: str = ""                 # 출원인
    inventors: str = ""
    application_date: str = ""          # 출원일
    ipc: str = ""
    status: str = ""                    # 법적상태 (등록/공개/거절 등)
    claims: str = ""                    # 청구범위 (상세조회 시)
    source: str = "KIPRIS"
    url: str = ""
    score: float = 0.0                  # 1차 스크리닝 관련도 점수

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def identifier(self) -> str:
        return (
            self.registration_number
            or self.publication_number
            or self.application_number
            or _slugify(self.title)
        )


@dataclass
class PriorArtAnalysis:
    """아이디어와 단일 선행문헌의 비교 분석."""

    prior_art: PriorArt
    relevance: str = ""                 # 관련성 요약
    overlapping_features: list[str] = field(default_factory=list)  # 겹치는 구성
    distinguishing_features: list[str] = field(default_factory=list)  # 우리 아이디어가 다른 점
    novelty_risk: str = "medium"        # high | medium | low (신규성 위협 정도)
    inventive_step_risk: str = "medium" # high | medium | low (진보성 위협 정도)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["prior_art"] = self.prior_art.to_dict()
        return d


@dataclass
class PatentabilityAssessment:
    """특허성(신규성·진보성) 종합 판단."""

    novelty_conclusion: str = ""        # 신규성 판단
    inventive_step_conclusion: str = "" # 진보성 판단
    closest_prior_art: list[str] = field(default_factory=list)  # 가장 가까운 선행문헌 식별자
    distinguishing_features: list[str] = field(default_factory=list)  # 핵심 차별점(등록 포인트)
    registration_likelihood: str = "medium"  # high | medium | low
    risks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)  # 등록 가능성을 높일 보정 방향
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PatentDraft:
    """특허 명세서 초안."""

    title: str = ""
    technical_field: str = ""           # 기술분야
    background: str = ""                # 배경기술
    problem: str = ""                   # 발명이 해결하려는 과제
    solution: str = ""                  # 과제의 해결 수단
    effects: str = ""                   # 발명의 효과
    detailed_description: str = ""      # 발명을 실시하기 위한 구체적인 내용
    independent_claims: list[str] = field(default_factory=list)  # 독립항
    dependent_claims: list[str] = field(default_factory=list)    # 종속항
    abstract: str = ""                  # 요약서

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineResult:
    """파이프라인 1회 실행 결과 전체."""

    idea: Idea
    prior_art: list[PriorArt] = field(default_factory=list)
    analyses: list[PriorArtAnalysis] = field(default_factory=list)
    assessment: PatentabilityAssessment | None = None
    draft: PatentDraft | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    note_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "idea": self.idea.to_dict(),
            "prior_art": [p.to_dict() for p in self.prior_art],
            "analyses": [a.to_dict() for a in self.analyses],
            "assessment": self.assessment.to_dict() if self.assessment else None,
            "draft": self.draft.to_dict() if self.draft else None,
            "created_at": self.created_at,
            "note_paths": self.note_paths,
        }
