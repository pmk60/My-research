"""KIPRIS Plus REST OpenAPI 클라이언트.

특허·실용신안 서지정보 검색(getAdvancedSearch / getWordSearch)과
상세 서지(getBibliographyDetailInfoSearch), 청구범위(getClaimInfoSearch)를 호출한다.

엔드포인트는 plus.kipris.or.kr 의 patUtiModInfoSearchSevice 기준이며,
서비스키(ServiceKey)는 발급받은 일반 인증키를 사용한다.
응답은 XML 이므로 표준 라이브러리로 파싱한다.
"""

from __future__ import annotations

import concurrent.futures as futures
import xml.etree.ElementTree as ET
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

from ..cache import Cache
from ..models import PriorArt

BASE_URL = "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice"


def _text(node: ET.Element | None, tag: str) -> str:
    if node is None:
        return ""
    child = node.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


class KiprisClient:
    def __init__(
        self,
        service_key: str,
        concurrency: int = 6,
        cache: Cache | None = None,
        timeout: float = 30.0,
    ):
        if httpx is None:
            raise RuntimeError("httpx 패키지가 필요합니다: pip install httpx")
        self.service_key = service_key
        self.concurrency = max(1, concurrency)
        self.cache = cache
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "KiprisClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ---- 내부 HTTP ----
    def _get(self, operation: str, params: dict[str, Any]) -> str:
        params = {k: v for k, v in params.items() if v not in (None, "", [])}
        params["ServiceKey"] = self.service_key

        cache_key = None
        if self.cache:
            cache_key = Cache.key("kipris", operation, params)
            cached = self.cache.get("kipris", cache_key)
            if cached is not None:
                return cached["xml"]

        resp = self._client.get(f"{BASE_URL}/{operation}", params=params)
        resp.raise_for_status()
        xml = resp.text
        if self.cache and cache_key:
            self.cache.set("kipris", cache_key, {"xml": xml})
        return xml

    # ---- 검색 ----
    def word_search(self, word: str, rows: int = 30) -> list[PriorArt]:
        """자유어(워드) 검색. 명칭+초록 등 전반을 대상으로 한다."""
        xml = self._get(
            "getWordSearch",
            {
                "word": word,
                "numOfRows": rows,
                "pageNo": 1,
                # 공개/등록 모두 포함
                "patent": "true",
                "utility": "true",
            },
        )
        return self._parse_search(xml)

    def advanced_search(
        self,
        invention_title: str = "",
        abstract: str = "",
        ipc: str = "",
        rows: int = 30,
    ) -> list[PriorArt]:
        """항목별(명칭/초록/IPC) 정밀 검색."""
        xml = self._get(
            "getAdvancedSearch",
            {
                "inventionTitle": invention_title,
                "astrtCont": abstract,
                "ipcNumber": ipc,
                "numOfRows": rows,
                "pageNo": 1,
                "patent": "true",
                "utility": "true",
            },
        )
        return self._parse_search(xml)

    def claim_info(self, application_number: str) -> str:
        """출원번호로 청구범위를 조회한다."""
        try:
            xml = self._get(
                "getClaimInfoSearch",
                {"applicationNumber": application_number},
            )
        except httpx.HTTPError:
            return ""
        root = self._safe_root(xml)
        if root is None:
            return ""
        claims = [
            (item.text or "").strip()
            for item in root.iter("claim")
            if item.text and item.text.strip()
        ]
        if not claims:
            # 일부 응답은 claimInfo/claimScope 형태
            claims = [
                (item.text or "").strip()
                for item in root.iter("claimScope")
                if item.text and item.text.strip()
            ]
        return "\n\n".join(claims)

    # ---- 파싱 ----
    @staticmethod
    def _safe_root(xml: str) -> ET.Element | None:
        try:
            return ET.fromstring(xml)
        except ET.ParseError:
            return None

    def _parse_search(self, xml: str) -> list[PriorArt]:
        root = self._safe_root(xml)
        if root is None:
            return []
        results: list[PriorArt] = []
        # KIPRIS 응답은 <body><items><item>...</item></items></body> 구조
        for item in root.iter("item"):
            app_no = _text(item, "applicationNumber")
            results.append(
                PriorArt(
                    application_number=app_no,
                    registration_number=_text(item, "registerNumber"),
                    publication_number=_text(item, "openNumber")
                    or _text(item, "publicationNumber"),
                    title=_text(item, "inventionTitle"),
                    abstract=_text(item, "astrtCont"),
                    applicant=_text(item, "applicantName"),
                    inventors=_text(item, "inventorName"),
                    application_date=_text(item, "applicationDate"),
                    ipc=_text(item, "ipcNumber"),
                    status=_text(item, "registerStatus") or _text(item, "applicationStatus"),
                    url=self._detail_url(app_no),
                    source="KIPRIS",
                )
            )
        return results

    @staticmethod
    def _detail_url(application_number: str) -> str:
        if not application_number:
            return ""
        return (
            "https://www.kipris.or.kr/khtml/patent/PatentSearchResult.do"
            f"?applicationNumber={application_number}"
        )

    # ---- 고수준 헬퍼 ----
    def search_for_idea(self, keywords: list[str], rows: int = 30) -> list[PriorArt]:
        """키워드 묶음으로 병렬 검색 후 출원번호 기준 중복 제거."""
        seen: dict[str, PriorArt] = {}
        queries = [k for k in keywords if k.strip()]
        if not queries:
            return []

        with futures.ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            jobs = {pool.submit(self.word_search, q, rows): q for q in queries}
            for fut in futures.as_completed(jobs):
                try:
                    items = fut.result()
                except Exception:  # noqa: BLE001 - 일부 쿼리 실패는 무시
                    continue
                for art in items:
                    key = art.identifier
                    if key not in seen:
                        seen[key] = art
        return list(seen.values())

    def enrich_with_claims(self, arts: list[PriorArt]) -> None:
        """선택된 선행문헌에 청구범위를 병렬로 채운다(상위 N건 대상)."""
        targets = [a for a in arts if a.application_number and not a.claims]
        if not targets:
            return
        with futures.ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            jobs = {pool.submit(self.claim_info, a.application_number): a for a in targets}
            for fut in futures.as_completed(jobs):
                art = jobs[fut]
                try:
                    art.claims = fut.result()
                except Exception:  # noqa: BLE001
                    art.claims = ""
