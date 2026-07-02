"""figurelabs 연동 인터페이스 (스텁).

주의: figurelabs 의 공개 REST API / 인증 방식(스코프, 엔드포인트)을 아직 확인하지
못했습니다. 공식 API 문서나 키 발급 페이지를 확인하면 아래 메서드 본문을 채웁니다.
계정: pmk601313@knu.ac.kr

연동 옵션(우선순위):
  1. figurelabs 가 REST API + API 키를 제공 -> 아래 upload_figure/create_figure 구현
  2. MCP 서버를 제공 -> .mcp.json 에 등록 후 MCP 도구로 호출
  3. 둘 다 없으면 R(ggplot2) 로 로컬 생성한 figure 를 수동 업로드
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FigurelabsClient:
    account: str = ""
    api_key: str = ""
    base_url: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url)

    def create_figure(self, spec: dict) -> dict:
        if not self.configured:
            return {"ok": False,
                    "error": "figurelabs API 미설정. base_url 과 api_key 를 config 에 입력하거나 "
                             "API 사양 확인 필요. 우선 R(ggplot2) 로컬 생성 figure 를 사용하세요."}
        # TODO: 실제 API 사양 확인 후 requests 로 POST 구현
        raise NotImplementedError("figurelabs API 사양 확정 후 구현")

    def upload_figure(self, local_path: str, name: str = "") -> dict:
        if not self.configured:
            return {"ok": False, "error": "figurelabs API 미설정 — 로컬 figure 경로 반환",
                    "local_path": local_path}
        raise NotImplementedError("figurelabs API 사양 확정 후 구현")
