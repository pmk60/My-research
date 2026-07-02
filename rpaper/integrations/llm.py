"""Claude API 클라이언트 — 참고문헌 요약 및 원고 섹션 초안 작성.

ANTHROPIC_API_KEY 환경변수 또는 config.llm.api_key 필요.
키가 없으면 graceful 하게 None 을 돌려주어 파이프라인이 멈추지 않습니다.
"""
from __future__ import annotations


def available(api_key: str) -> bool:
    if not api_key:
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def complete(prompt: str, *, api_key: str, model: str = "claude-fable-5",
             max_tokens: int = 2000, system: str = "") -> str | None:
    if not available(api_key):
        return None
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system or "You are a scientific writing assistant. Be precise, cite by [n].",
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")
