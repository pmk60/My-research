"""Claude Code CLI 백엔드.

Anthropic 유료 API 대신, 로컬에 설치·로그인된 Claude Code CLI(`claude -p`)를
LLM 엔진으로 사용한다. Claude Pro/Max 구독이면 추가 과금 없이 동작한다.

LLM 클래스와 동일한 인터페이스(complete / complete_json)를 제공하므로
파이프라인의 어느 단계에서든 교체 사용할 수 있다.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from typing import Any

from .cache import Cache


class ClaudeCodeError(RuntimeError):
    pass


def claude_cli_available(command: str = "claude") -> bool:
    return shutil.which(command) is not None


def extract_json(text: str) -> dict[str, Any]:
    """모델 출력에서 JSON 객체 하나를 견고하게 추출한다.

    코드펜스(```json ... ```)나 앞뒤 설명 문장이 섞여 있어도 첫 '{' 부터
    균형이 맞는 '}' 까지를 파싱한다.
    """
    # 1) 코드펜스 우선
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    # 2) 첫 '{' 부터 중괄호 균형 추적
    start = text.find("{")
    if start == -1:
        raise ValueError("출력에 JSON 객체가 없습니다")
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("JSON 객체가 닫히지 않았습니다")


class ClaudeCodeLLM:
    """`claude -p` 를 서브프로세스로 호출하는 LLM 백엔드."""

    def __init__(
        self,
        command: str = "claude",
        model: str = "",
        cache: Cache | None = None,
        timeout: float = 900.0,
    ):
        if not claude_cli_available(command):
            raise ClaudeCodeError(
                "claude CLI 를 찾을 수 없습니다. Claude Code 를 설치하고 "
                "Pro/Max 계정으로 로그인하세요 (https://claude.com/claude-code)."
            )
        self.command = command
        self.model = model  # 비우면 CLI 기본 모델 사용
        self.cache = cache
        self.timeout = timeout

    # ---- 내부 호출 ----
    def _invoke(self, prompt: str, retries: int = 1) -> str:
        args = [self.command, "-p", "--output-format", "text"]
        if self.model:
            args += ["--model", self.model]
        last_err = ""
        for attempt in range(retries + 1):
            try:
                proc = subprocess.run(
                    args,
                    input=prompt.encode("utf-8"),
                    capture_output=True,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise ClaudeCodeError(f"claude CLI 응답 시간 초과({self.timeout}s)") from exc
            if proc.returncode == 0:
                return proc.stdout.decode("utf-8", errors="replace").strip()
            last_err = proc.stdout.decode("utf-8", errors="replace").strip() or proc.stderr.decode(
                "utf-8", errors="replace"
            ).strip()
            if attempt < retries:
                time.sleep(3)
        raise ClaudeCodeError(f"claude CLI 실패(code {proc.returncode}): {last_err[:500]}")

    # ---- LLM 인터페이스 ----
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 16000,
        stream: bool | None = None,
    ) -> str:
        prompt = (
            f"<지침>\n{system}\n</지침>\n\n{user}\n\n"
            "(도구를 사용하지 말고, 요청된 내용만 바로 출력하세요.)"
        )
        cache_key = None
        if self.cache:
            cache_key = Cache.key("cc-complete", self.model, system, user)
            cached = self.cache.get("llm", cache_key)
            if cached is not None:
                return cached["text"]
        text = self._invoke(prompt)
        if self.cache and cache_key:
            self.cache.set("llm", cache_key, {"text": text})
        return text

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 16000,
    ) -> dict[str, Any]:
        cache_key = None
        if self.cache:
            cache_key = Cache.key("cc-json", self.model, system, user, schema)
            cached = self.cache.get("llm", cache_key)
            if cached is not None:
                return cached

        schema_text = json.dumps(schema, ensure_ascii=False, indent=2)
        prompt = (
            f"<지침>\n{system}\n</지침>\n\n{user}\n\n"
            "<출력형식>\n"
            "다음 JSON 스키마를 만족하는 JSON 객체 **하나만** 출력하세요. "
            "설명 문장, 코드펜스, 주석 없이 순수 JSON 만 출력합니다.\n"
            f"{schema_text}\n"
            "</출력형식>\n"
            "(도구를 사용하지 말고 JSON 만 출력하세요.)"
        )
        text = self._invoke(prompt)
        try:
            data = extract_json(text)
        except (ValueError, json.JSONDecodeError):
            # 1회 재시도: JSON 만 다시 요청
            retry = self._invoke(
                "아래 출력에서 JSON 객체만 추출해, 유효한 JSON 하나로만 다시 출력하세요.\n\n"
                + text[:8000]
            )
            try:
                data = extract_json(retry)
            except (ValueError, json.JSONDecodeError) as exc:
                raise ClaudeCodeError(
                    f"JSON 파싱 실패: {exc}\n원본(앞 500자):\n{text[:500]}"
                ) from exc

        if self.cache and cache_key:
            self.cache.set("llm", cache_key, data)
        return data
