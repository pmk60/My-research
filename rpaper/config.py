"""설정 로딩. config.yaml + 환경변수 오버라이드."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pyyaml 미설치 시에도 최소 동작
    yaml = None


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass
class Config:
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path = "config.yaml") -> "Config":
        path = Path(path)
        data: dict[str, Any] = {}
        if path.exists() and yaml is not None:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(raw=data)

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.raw
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    # 자주 쓰는 값에 환경변수 우선 적용
    @property
    def ncbi_api_key(self) -> str:
        return _env("RPAPER_NCBI_API_KEY") or self.get("pubmed", "api_key", default="")

    @property
    def email(self) -> str:
        return self.get("pubmed", "email", default="") or self.get("project", "obsidian_vault", default="")

    @property
    def anthropic_api_key(self) -> str:
        return _env("ANTHROPIC_API_KEY") or self.get("llm", "api_key", default="")

    @property
    def vault(self) -> Path:
        """기존 Obsidian vault 의 루트 경로."""
        return Path(self.get("project", "obsidian_vault", default="./vault"))

    @property
    def project_folder(self) -> str:
        """vault 안에서 이 프로젝트가 들어갈 하위 폴더명.

        지정이 없으면 제목을 슬러그로 변환. 기존 vault 의 노트들과 섞이지 않도록
        항상 전용 폴더 아래에 모읍니다.
        """
        folder = self.get("project", "folder", default="")
        if folder:
            return folder
        import re
        title = self.get("project", "title", default="rpaper-project")
        s = re.sub(r"[^\w\s-]", "", title).strip()
        s = re.sub(r"\s+", "-", s)
        return s[:60] or "rpaper-project"
