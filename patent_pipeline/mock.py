"""모의(mock) 구현 — API 키 없이 파이프라인 전체 흐름을 시연/테스트하기 위한 것.

--dry-run 모드에서 실제 Claude/KIPRIS 대신 사용된다. 실제 분석 품질은 없지만,
각 단계가 어떤 산출물을 만들고 Obsidian 노트가 어떻게 연결되는지 끝까지 확인할 수 있다.
"""

from __future__ import annotations

from typing import Any

from .models import PriorArt


class MockLLM:
    """LLM 과 동일한 인터페이스(complete / complete_json)를 흉내내는 모의 객체.

    출력 JSON 스키마의 특징적 키를 보고 어느 단계인지 추론하여
    그럴듯한 더미 응답을 돌려준다.
    """

    def __init__(self, *_: Any, **__: Any) -> None:
        self.model = "mock"
        self.effort = "n/a"

    def complete(self, system: str, user: str, max_tokens: int = 16000, stream: bool | None = None) -> str:
        return "(모의 텍스트 응답)"

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 16000,
    ) -> dict[str, Any]:
        props = set((schema.get("properties") or {}).keys())

        if "keywords_ko" in props:  # ① intake
            return {
                "title": "[모의] 발명의 명칭",
                "technical_field": "[모의] 기술분야",
                "problem": "[모의] 해결하고자 하는 과제",
                "solution": "[모의] 과제 해결 수단의 요지",
                "key_features": ["[모의] 구성요소 A", "[모의] 구성요소 B", "[모의] 구성요소 C"],
                "effects": ["[모의] 효과 1", "[모의] 효과 2"],
                "keywords_ko": ["모의키워드1", "모의키워드2"],
                "keywords_en": ["mock keyword1", "mock keyword2"],
                "ipc_hints": ["G06F"],
            }

        if "scores" in props:  # ③ screening
            count = user.count("[")  # 목록 항목 수 추정
            return {
                "scores": [
                    {"index": i, "score": max(10, 90 - i * 7), "reason": "[모의] 관련도 추정"}
                    for i in range(max(1, count))
                ]
            }

        if "overlapping_features" in props:  # ④ 개별 분석
            return {
                "relevance": "[모의] 일부 구성이 유사함",
                "overlapping_features": ["[모의] 겹치는 구성 A"],
                "distinguishing_features": ["[모의] 우리 발명의 차별 구성 B"],
                "novelty_risk": "medium",
                "inventive_step_risk": "low",
                "notes": "[모의] 핵심 차별 구성은 미개시로 추정",
            }

        if "novelty_conclusion" in props:  # ⑤ 특허성 판단
            return {
                "novelty_conclusion": "[모의] 차별 구성으로 신규성 인정 여지",
                "inventive_step_conclusion": "[모의] 효과의 현저성으로 진보성 주장 가능",
                "closest_prior_art": ["MOCK-0001"],
                "distinguishing_features": ["[모의] 등록 포인트 1", "[모의] 등록 포인트 2"],
                "registration_likelihood": "medium",
                "risks": ["[모의] 일부 구성은 공지로 보임"],
                "recommendations": ["[모의] 독립항에 차별 구성 한정 추가"],
                "rationale": "[모의] 차별 구성을 독립항에 반영하면 등록 가능성 상승",
            }

        if "independent_claims" in props:  # ⑥ 명세서 초안
            return {
                "title": "[모의] 발명의 명칭",
                "technical_field": "[모의] 본 발명은 ... 에 관한 것이다.",
                "background": "[모의] 종래기술은 ... 한계가 있었다.",
                "problem": "[모의] 본 발명이 해결하려는 과제",
                "solution": "[모의] 과제의 해결 수단",
                "effects": "[모의] 발명의 효과",
                "detailed_description": "[모의] 도면을 참조하면, ... 구체적 실시예 ...",
                "independent_claims": [
                    "[모의] 구성요소 A와, 상기 A에 결합된 차별 구성 B를 포함하는 장치.",
                    "[모의] 구성요소 A를 제공하는 단계와, 차별 구성 B를 수행하는 단계를 포함하는 방법.",
                ],
                "dependent_claims": [
                    "제1항에 있어서, [모의] 부가 한정 C를 더 포함하는 장치.",
                ],
                "abstract": "[모의] 차별 구성 B를 갖는 장치 및 방법.",
            }

        return {}


class MockKiprisClient:
    """KiprisClient 의 검색 인터페이스를 흉내내는 모의 객체."""

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    def __enter__(self) -> "MockKiprisClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        pass

    def close(self) -> None:
        pass

    def search_for_idea(self, keywords: list[str], rows: int = 30) -> list[PriorArt]:
        return [
            PriorArt(
                application_number=f"10-2020-000{i}",
                registration_number=f"MOCK-000{i}",
                title=f"[모의] 선행 특허 {i}",
                abstract=f"[모의] 선행 특허 {i} 의 초록입니다. 일부 구성이 유사합니다.",
                applicant="모의 출원인",
                status="등록",
                ipc="G06F",
                source="KIPRIS(mock)",
                score=0.0,
            )
            for i in range(1, 4)
        ]

    def enrich_with_claims(self, arts: list[PriorArt]) -> None:
        for a in arts:
            a.claims = "제1항: [모의] 구성요소 A를 포함하는 장치."
