"""Claude(Anthropic) 래퍼.

- 구조화 분석에는 JSON 스키마 강제 출력(output_config.format) 사용
- 긴 명세서 작성에는 스트리밍으로 타임아웃 방지
- 적응형 사고(adaptive thinking) + effort 파라미터로 추론 깊이 제어
"""

from __future__ import annotations

import json
from typing import Any

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None

from .cache import Cache


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-8",
        effort: str = "high",
        cache: Cache | None = None,
    ):
        if anthropic is None:
            raise LLMError("anthropic 패키지가 필요합니다: pip install anthropic")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.effort = effort
        self.cache = cache

    # ---- 텍스트 생성 (긴 출력은 스트리밍) ----
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 16000,
        stream: bool | None = None,
    ) -> str:
        cache_key = None
        if self.cache:
            cache_key = Cache.key("complete", self.model, system, user, max_tokens)
            cached = self.cache.get("llm", cache_key)
            if cached is not None:
                return cached["text"]

        if stream is None:
            stream = max_tokens > 16000

        kwargs: dict[str, Any] = dict(
            model=self.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        if stream:
            with self.client.messages.stream(**kwargs) as s:
                message = s.get_final_message()
        else:
            message = self.client.messages.create(**kwargs)

        if message.stop_reason == "refusal":
            raise LLMError("모델이 요청을 거부했습니다(refusal).")

        text = "".join(b.text for b in message.content if b.type == "text")
        if self.cache and cache_key:
            self.cache.set("llm", cache_key, {"text": text})
        return text

    # ---- 구조화(JSON) 생성 ----
    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 16000,
    ) -> dict[str, Any]:
        cache_key = None
        if self.cache:
            cache_key = Cache.key("json", self.model, system, user, schema, max_tokens)
            cached = self.cache.get("llm", cache_key)
            if cached is not None:
                return cached

        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": schema},
            },
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        if message.stop_reason == "refusal":
            raise LLMError("모델이 요청을 거부했습니다(refusal).")

        text = next((b.text for b in message.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:  # pragma: no cover
            raise LLMError(f"JSON 파싱 실패: {exc}\n원본:\n{text[:500]}") from exc

        if self.cache and cache_key:
            self.cache.set("llm", cache_key, data)
        return data
