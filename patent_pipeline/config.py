"""설정 로딩. 환경변수 > patent_config.yaml > 기본값 순으로 적용."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


@dataclass
class SearchConfig:
    max_results: int = 30
    analyze_top_n: int = 12
    concurrency: int = 6
    # 학술 논문(OpenAlex) 선행조사
    use_literature: bool = True
    literature_max_results: int = 10
    literature_mailto: str = ""


@dataclass
class ObsidianConfig:
    vault_path: str = ""
    folder: str = "Patents"


@dataclass
class Config:
    kipris_service_key: str = ""
    anthropic_api_key: str = ""
    model: str = "claude-opus-4-8"
    effort: str = "high"
    # LLM 백엔드: auto | api | claude-code
    #  - auto: API 키 있으면 api, 없으면 claude CLI(Pro/Max 구독, 추가 과금 없음)
    #  - api: Anthropic API (유료 키 필요)
    #  - claude-code: Claude Code CLI 강제 사용
    llm_backend: str = "auto"
    # claude-code 백엔드에서 쓸 모델 별칭(예: opus, sonnet). 비우면 CLI 기본값.
    claude_code_model: str = ""
    cache_dir: str = ".cache"
    search: SearchConfig = field(default_factory=SearchConfig)
    obsidian: ObsidianConfig = field(default_factory=ObsidianConfig)

    @property
    def resolved_vault_path(self) -> Path:
        if self.obsidian.vault_path:
            return Path(self.obsidian.vault_path).expanduser()
        return Path("output") / "vault"

    def require_anthropic(self) -> str:
        if not self.anthropic_api_key:
            raise RuntimeError(
                "Anthropic API 키가 없습니다. 환경변수 ANTHROPIC_API_KEY 또는 "
                "patent_config.yaml 의 anthropic_api_key 를 설정하세요."
            )
        return self.anthropic_api_key

    def require_kipris(self) -> str:
        if not self.kipris_service_key:
            raise RuntimeError(
                "KIPRIS 서비스키가 없습니다. 환경변수 KIPRIS_SERVICE_KEY 또는 "
                "patent_config.yaml 의 kipris_service_key 를 설정하세요."
            )
        return self.kipris_service_key


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if yaml is None:
        raise RuntimeError("PyYAML 이 설치되어 있지 않습니다: pip install PyYAML")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    """patent_config.yaml(있으면) 과 환경변수를 합쳐 Config 를 만든다."""
    data: dict[str, Any] = {}
    # patent_config.yaml 우선 (저장소에 rpaper 의 config.yaml 이 공존하므로 분리).
    # 하위호환으로 config.yaml / config.local.yaml 도 계속 지원.
    candidates = (
        [Path(path)]
        if path
        else [Path("patent_config.yaml"), Path("config.yaml"), Path("config.local.yaml")]
    )
    for candidate in candidates:
        if candidate.exists():
            data = _load_yaml(candidate)
            break

    search_data = data.get("search") or {}
    obsidian_data = data.get("obsidian") or {}

    cfg = Config(
        kipris_service_key=data.get("kipris_service_key", ""),
        anthropic_api_key=data.get("anthropic_api_key", ""),
        model=data.get("model", "claude-opus-4-8"),
        effort=data.get("effort", "high"),
        llm_backend=data.get("llm_backend", "auto"),
        claude_code_model=data.get("claude_code_model", ""),
        cache_dir=data.get("cache_dir", ".cache"),
        search=SearchConfig(
            max_results=int(search_data.get("max_results", 30)),
            analyze_top_n=int(search_data.get("analyze_top_n", 12)),
            concurrency=int(search_data.get("concurrency", 6)),
            use_literature=bool(search_data.get("use_literature", True)),
            literature_max_results=int(search_data.get("literature_max_results", 10)),
            literature_mailto=search_data.get("literature_mailto", ""),
        ),
        obsidian=ObsidianConfig(
            vault_path=obsidian_data.get("vault_path", ""),
            folder=obsidian_data.get("folder", "Patents"),
        ),
    )

    # 환경변수 우선 적용
    cfg.kipris_service_key = os.environ.get("KIPRIS_SERVICE_KEY", cfg.kipris_service_key)
    cfg.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", cfg.anthropic_api_key)
    cfg.model = os.environ.get("PATENT_PIPELINE_MODEL", cfg.model)
    cfg.llm_backend = os.environ.get("PATENT_LLM_BACKEND", cfg.llm_backend)
    if os.environ.get("OBSIDIAN_VAULT_PATH"):
        cfg.obsidian.vault_path = os.environ["OBSIDIAN_VAULT_PATH"]

    return cfg
