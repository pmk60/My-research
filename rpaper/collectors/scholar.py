"""Google Scholar 수집.

중요: Google Scholar 는 공식 API 가 없으며, 직접 스크래핑은 약관 위반이고
IP 차단/캡차로 신뢰성이 낮습니다. 합법적이고 안정적인 경로는 SerpAPI(유료)의
google_scholar 엔진을 쓰는 것입니다. 사용자가 유료 계정을 보유하셨으므로 권장합니다.

config.scholar.provider 가 "serpapi" 이고 키가 있으면 동작, 아니면 빈 리스트를 반환합니다.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from .pubmed import Reference


def collect(query: str, *, provider: str = "serpapi", serpapi_key: str = "",
            max_results: int = 20) -> list[Reference]:
    if provider != "serpapi" or not serpapi_key:
        return []
    qs = urllib.parse.urlencode({
        "engine": "google_scholar", "q": query, "api_key": serpapi_key, "num": min(max_results, 20),
    })
    req = urllib.request.Request(f"https://serpapi.com/search?{qs}",
                                 headers={"User-Agent": "rpaper/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    refs: list[Reference] = []
    for item in payload.get("organic_results", [])[:max_results]:
        info = item.get("publication_info", {})
        refs.append(Reference(
            source="scholar",
            uid=item.get("result_id", ""),
            title=item.get("title", ""),
            authors=[a.get("name", "") for a in info.get("authors", [])],
            journal=info.get("summary", ""),
            year="",
            abstract=item.get("snippet", ""),
            doi="",
            url=item.get("link", ""),
        ))
    return refs
