"""해외 뉴스/소식 수집.

provider:
  - "newsapi": NewsAPI.org (유료/무료 티어). config.news.newsapi_key 필요.
  - "websearch": Claude Code 내장 웹검색을 쓰는 경로(오케스트레이터에서 처리).
  - "none": 비활성화.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict


@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    published: str
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)


def collect_newsapi(query: str, api_key: str, language: str = "en",
                    max_results: int = 30) -> list[NewsItem]:
    if not api_key:
        return []
    qs = urllib.parse.urlencode({
        "q": query, "language": language, "pageSize": min(max_results, 100),
        "sortBy": "relevancy", "apiKey": api_key,
    })
    req = urllib.request.Request(f"https://newsapi.org/v2/everything?{qs}",
                                 headers={"User-Agent": "rpaper/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    items = []
    for a in payload.get("articles", [])[:max_results]:
        items.append(NewsItem(
            title=a.get("title", ""),
            source=(a.get("source") or {}).get("name", ""),
            url=a.get("url", ""),
            published=a.get("publishedAt", ""),
            summary=a.get("description", "") or "",
        ))
    return items


def collect(query: str, *, provider: str = "newsapi", newsapi_key: str = "",
            language: str = "en", max_results: int = 30) -> list[NewsItem]:
    if provider == "newsapi":
        return collect_newsapi(query, newsapi_key, language, max_results)
    # websearch 경로는 cli/orchestrator 에서 Claude 웹검색으로 채웁니다.
    return []
