"""FigureLabs API 클라이언트 (REST API v1 연동).

공식 사양 (조사 완료, 2026-10):
  * Base URL   : https://api.figurelabs.ai/v1
  * 인증       : HTTP 헤더 ``Authorization: Bearer <API_KEY>`` (키 형식 ``fl_live_...``)
                 키는 환경변수 ``FIGURELABS_API_KEY`` 또는 config.yaml 의
                 ``figurelabs.api_key`` 로 설정.
  * 생성 요청  : ``POST {base_url}/images/generations``
                 body: ``{"prompt": "...", "mode": "generations", "style": "Flat"}``
                 응답: HTTP 202 Accepted, ``{"task_id": "tsk_...", "status": "processing", ...}``
  * 상태 확인  : ``GET {base_url}/tasks/{task_id}`` (polling)
                 상태: pending / processing / succeeded / failed / rejected / canceled
                 성공 시 ``{"status": "succeeded", "output_url": "https://files.figurelabs.ai/presigned/...", ...}``
  * MCP 연동   : ``https://api.figurelabs.ai/plot-mcp`` — Claude Code / Claude Desktop 의
                 MCP 설정에 추가하면 계정 로그인으로 사용 가능(대화형 도구용).

참고: 기본 figure 생성은 여전히 R(ggplot2) 로컬 엔진(``rpaper figure``)이 담당합니다.
FigureLabs 는 R 로 그리기 어려운 삽화/스킴atic 등을 보조 생성하는 옵션입니다.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://api.figurelabs.ai/v1"
MCP_URL = "https://api.figurelabs.ai/plot-mcp"
ENV_API_KEY = "FIGURELABS_API_KEY"
ENV_BASE_URL = "FIGURELABS_BASE_URL"

# 종료 상태(더 이상 polling 하지 않음)
TERMINAL_STATUSES = {"succeeded", "failed", "rejected", "canceled"}


def _post_json(url: str, body: dict, api_key: str, timeout: float = 30.0) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, api_key: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(
        url, method="GET",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _get_bytes(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, method="GET",
                                 headers={"Accept": "image/*,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


# 테스트에서 갈아끼우기 쉬운 module-level 훅
_sleep = time.sleep


def _key_error() -> dict:
    """API 키 미설정 시의 친절한 안내."""
    return {
        "ok": False,
        "error": ("FigureLabs API 키가 설정되지 않았습니다. 환경변수 FIGURELABS_API_KEY 또는 "
                  "config.yaml 의 figurelabs.api_key 에 키(fl_live_...)를 입력하세요. "
                  "키가 없다면 R(ggplot2) 로컬 figure 생성(`rpaper figure`)을 사용하세요 — "
                  "논문 품질은 충분합니다."),
        "hint": {"rest_api": DEFAULT_BASE_URL, "mcp_url": MCP_URL},
    }


@dataclass
class FigurelabsClient:
    """FigureLabs REST API v1 클라이언트.

    ``api_key`` / ``base_url`` 을 비워 두면 환경변수(FIGURELABS_API_KEY /
    FIGURELABS_BASE_URL)로 대체하고, 그래도 없으면 기본 base_url 을 씁니다.
    """

    account: str = ""
    api_key: str = ""
    base_url: str = ""

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = os.environ.get(ENV_API_KEY, "")
        if not self.base_url:
            self.base_url = os.environ.get(ENV_BASE_URL, "") or DEFAULT_BASE_URL
        self.base_url = self.base_url.rstrip("/")

    @classmethod
    def from_config(cls, cfg) -> "FigurelabsClient":
        """rpaper Config(config.yaml 의 figurelabs 섹션)에서 생성."""
        return cls(account=cfg.get("figurelabs", "account", default=""),
                   api_key=cfg.get("figurelabs", "api_key", default=""),
                   base_url=cfg.get("figurelabs", "base_url", default=""))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------ 생성
    def create_figure(self, prompt: str, style: str = "Flat",
                      poll_interval: float = 3.0, timeout: float = 120.0) -> dict:
        """프롬프트로 figure 를 생성하고 완료될 때까지 polling 합니다.

        반환: 성공 시 ``{"ok": True, "task_id": ..., "output_url": ...}``,
        실패 시 ``{"ok": False, "error": ..., "status": ...}``.
        """
        if not self.configured:
            return _key_error()
        if not prompt:
            return {"ok": False, "error": "prompt 가 비어 있습니다."}

        body = {"prompt": prompt, "mode": "generations", "style": style}
        try:
            resp = _post_json(f"{self.base_url}/images/generations", body, self.api_key)
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except Exception:  # noqa: BLE001
                pass
            return {"ok": False,
                    "error": f"FigureLabs 생성 요청 실패 (HTTP {e.code}): {detail or e.reason}"}
        except (urllib.error.URLError, OSError, ValueError) as e:
            return {"ok": False, "error": f"FigureLabs 생성 요청 실패: {type(e).__name__}: {e}"}

        task_id = resp.get("task_id")
        if not task_id:
            return {"ok": False, "error": "생성 응답에 task_id 가 없습니다.", "response": resp}

        deadline = time.monotonic() + timeout
        last_status = resp.get("status", "")
        while True:
            try:
                task = _get_json(f"{self.base_url}/tasks/{task_id}", self.api_key)
            except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as e:
                return {"ok": False, "task_id": task_id,
                        "error": f"상태 확인 실패: {type(e).__name__}: {e}",
                        "last_status": last_status}
            last_status = task.get("status", last_status)

            if last_status == "succeeded":
                output_url = task.get("output_url", "")
                if not output_url:
                    return {"ok": False, "task_id": task_id,
                            "error": "작업은 succeeded 였지만 output_url 이 없습니다.", "raw": task}
                return {"ok": True, "task_id": task_id, "status": last_status,
                        "output_url": output_url, "raw": task}
            if last_status in TERMINAL_STATUSES:
                return {"ok": False, "task_id": task_id, "status": last_status,
                        "error": f"FigureLabs 작업이 실패로 끝났습니다: {last_status}", "raw": task}
            if time.monotonic() >= deadline:
                return {"ok": False, "task_id": task_id, "status": last_status,
                        "error": f"타임아웃({timeout:.0f}초) — 마지막 상태: {last_status}"}
            _sleep(poll_interval)

    # ------------------------------------------------------------ 다운로드
    def download_figure(self, output_url: str, save_path: str) -> dict:
        """성공한 작업의 ``output_url`` 에서 이미지를 내려받아 로컬 파일로 저장."""
        if not output_url:
            return {"ok": False, "error": "output_url 이 비어 있습니다."}
        try:
            data = _get_bytes(output_url)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            return {"ok": False, "error": f"다운로드 실패: {type(e).__name__}: {e}"}
        if not data:
            return {"ok": False, "error": "다운로드한 파일이 비어 있습니다."}
        out = Path(save_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return {"ok": True, "saved_path": str(out), "bytes": len(data)}

    # ------------------------------------------------------------ 업로드(미제공)
    def upload_figure(self, local_path: str, name: str = "") -> dict:
        """로컬 figure 업로드는 REST API v1 에 엔드포인트가 없습니다.

        기존 호출부 호환을 위해 시그니처를 유지하며, 로컬 경로를 그대로 안내합니다.
        로컬 R(ggplot2) figure 는 그 자체로 원고에 사용하세요.
        """
        p = Path(local_path) if local_path else None
        exists = bool(p and p.exists())
        return {"ok": False,
                "error": ("FigureLabs REST API v1 은 생성 전용(images/generations)이며 "
                          "로컬 파일 업로드 엔드포인트를 제공하지 않습니다. "
                          "로컬 figure 를 그대로 사용하세요."),
                "local_path": str(p) if p else local_path,
                "local_path_exists": exists,
                "name": name,
                "hint": "생성형 보조 figure 가 필요하면 create_figure(prompt) 를 사용하세요."}
