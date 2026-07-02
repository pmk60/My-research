"""PubMed 문헌 수집 — NCBI E-utilities (공개 API, 실제 동작).

표준 라이브러리만 사용하므로 추가 설치 없이 동작합니다.
API 키가 있으면 rate limit 이 초당 3 -> 10 요청으로 올라갑니다.
"""
from __future__ import annotations

import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@dataclass
class Reference:
    source: str          # "pubmed"
    uid: str             # PMID
    title: str
    authors: list[str]
    journal: str
    year: str
    abstract: str
    doi: str
    url: str

    def to_dict(self) -> dict:
        return asdict(self)


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "rpaper/0.1 (research tool)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _eutils(endpoint: str, params: dict) -> bytes:
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v})
    return _get(f"{EUTILS}/{endpoint}?{qs}")


def search_pmids(query: str, max_results: int = 40, api_key: str = "", email: str = "") -> list[str]:
    data = _eutils("esearch.fcgi", {
        "db": "pubmed", "term": query, "retmax": max_results,
        "retmode": "json", "api_key": api_key, "email": email, "sort": "relevance",
    })
    import json
    payload = json.loads(data)
    return payload.get("esearchresult", {}).get("idlist", [])


def _text(node, path, default="") -> str:
    found = node.find(path)
    return (found.text or default).strip() if found is not None and found.text else default


def fetch_details(pmids: list[str], api_key: str = "", email: str = "") -> list[Reference]:
    if not pmids:
        return []
    data = _eutils("efetch.fcgi", {
        "db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
        "api_key": api_key, "email": email,
    })
    root = ET.fromstring(data)
    refs: list[Reference] = []
    for art in root.findall(".//PubmedArticle"):
        pmid = _text(art, ".//PMID")
        title = _text(art, ".//ArticleTitle")
        journal = _text(art, ".//Journal/Title")
        year = _text(art, ".//JournalIssue/PubDate/Year") or _text(art, ".//PubDate/MedlineDate")[:4]
        abstract = " ".join(
            (n.text or "").strip() for n in art.findall(".//Abstract/AbstractText")
        ).strip()
        authors = []
        for a in art.findall(".//Author"):
            last = _text(a, "LastName")
            init = _text(a, "Initials")
            if last:
                authors.append(f"{last} {init}".strip())
        doi = ""
        for aid in art.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                doi = (aid.text or "").strip()
        refs.append(Reference(
            source="pubmed", uid=pmid, title=title, authors=authors,
            journal=journal, year=year, abstract=abstract, doi=doi,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        ))
    return refs


def collect(query: str, max_results: int = 40, api_key: str = "", email: str = "") -> list[Reference]:
    """검색 -> 상세조회 한 번에. rate limit 대비 짧은 대기 포함."""
    pmids = search_pmids(query, max_results, api_key, email)
    time.sleep(0.34 if not api_key else 0.11)
    return fetch_details(pmids, api_key, email)
