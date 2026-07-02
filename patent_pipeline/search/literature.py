"""학술 논문 선행조사 — OpenAlex API.

OpenAlex(https://openalex.org)는 무료·인증키 불필요 학술 메타데이터 API다.
(예의상 mailto 파라미터로 연락처를 넘기면 polite pool 로 처리된다.)
검색 결과를 PriorArt(source="OpenAlex")로 매핑해 특허 선행문헌과 함께 검토한다.
"""

from __future__ import annotations

from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

from ..cache import Cache
from ..models import PriorArt

BASE_URL = "https://api.openalex.org/works"


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """OpenAlex 의 abstract_inverted_index(단어→위치목록)를 원문 순서로 복원."""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort(key=lambda p: p[0])
    return " ".join(word for _, word in positions)


class LiteratureClient:
    def __init__(
        self,
        mailto: str = "",
        cache: Cache | None = None,
        timeout: float = 30.0,
    ):
        if httpx is None:
            raise RuntimeError("httpx 패키지가 필요합니다: pip install httpx")
        self.mailto = mailto
        self.cache = cache
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LiteratureClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def search(self, query: str, per_page: int = 10) -> list[PriorArt]:
        query = query.strip()
        if not query:
            return []

        params: dict[str, Any] = {
            "search": query,
            "per_page": max(1, min(per_page, 50)),
            "sort": "relevance_score:desc",
        }
        if self.mailto:
            params["mailto"] = self.mailto

        cache_key = None
        if self.cache:
            cache_key = Cache.key("openalex", params)
            cached = self.cache.get("openalex", cache_key)
            if cached is not None:
                data = cached
            else:
                data = self._fetch(params)
                self.cache.set("openalex", cache_key, data)
        else:
            data = self._fetch(params)

        return [self._map(work) for work in data.get("results", [])]

    def _fetch(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._client.get(BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            return {"results": []}

    @staticmethod
    def _map(work: dict[str, Any]) -> PriorArt:
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in work.get("authorships", [])[:3]
        ]
        openalex_id = (work.get("id") or "").rsplit("/", 1)[-1]
        doi = work.get("doi") or ""
        return PriorArt(
            publication_number=openalex_id,            # 식별자로 사용
            title=work.get("display_name") or "(제목 없음)",
            abstract=reconstruct_abstract(work.get("abstract_inverted_index")),
            applicant=", ".join(a for a in authors if a),  # 저자
            application_date=str(work.get("publication_year") or ""),
            status=work.get("type") or "article",
            url=doi or (work.get("id") or ""),
            source="OpenAlex",
        )

    def search_for_idea(self, keywords_en: list[str], title: str, per_page: int = 10) -> list[PriorArt]:
        """영문 키워드(없으면 명칭)로 1회 검색."""
        query = " ".join(k for k in keywords_en[:4] if k.strip()) or title
        return self.search(query, per_page=per_page)
