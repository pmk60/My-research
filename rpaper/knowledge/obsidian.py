"""Obsidian vault 생성기 — 기존 vault 에 안전하게 연동.

기존 Obsidian vault 의 루트를 가리키면, 그 안에 프로젝트 전용 폴더를 만들어
모든 노트를 모읍니다. 기존 노트와 섞이지 않고, 그래프뷰/검색/wikilink 는
vault 전체에서 그대로 동작합니다.

  <vault_root>/<project_folder>/
    00-Index.md               # 프로젝트 허브(MOC)
    References/Ref-001.md ...  # reference 번호별 노트(요약 포함)
    Bibliography.md            # 번호순 전체 인용 목록
    News/...                   # 해외 뉴스 노트
    Manuscript/...             # Introduction/Methods/Results/...
    .rpaper/                   # 파이프라인 캐시(숨김)

인용 wikilink 는 경로까지 명시(`[[<folder>/References/Ref-001|1]]`)하여
같은 vault 의 다른 프로젝트와 노트명이 겹쳐도 모호하지 않습니다.
모바일/PC 어디서 동기화하든 동일하게 열립니다.
"""
from __future__ import annotations

import re
from pathlib import Path
from datetime import date


def slug(text: str, n: int = 60) -> str:
    s = re.sub(r"[^\w\s-]", "", text).strip()
    s = re.sub(r"\s+", "-", s)
    return s[:n] or "untitled"


def _fm(d: dict) -> str:
    """YAML frontmatter."""
    lines = ["---"]
    for k, v in d.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            lines.extend(f"  - {x}" for x in v)
        else:
            lines.append(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def _citation(ref: dict, number: int) -> str:
    """Vancouver 스타일 번호 인용 한 줄."""
    authors = ref.get("authors", [])
    if len(authors) > 6:
        au = ", ".join(authors[:6]) + ", et al"
    else:
        au = ", ".join(authors)
    parts = [p for p in [
        au, ref.get("title", "").rstrip("."), ref.get("journal", ""),
        ref.get("year", ""),
    ] if p]
    line = ". ".join(parts)
    if ref.get("doi"):
        line += f". doi:{ref['doi']}"
    elif ref.get("url"):
        line += f". {ref['url']}"
    return f"{number}. {line}."


class Vault:
    def __init__(self, root: str | Path, project_folder: str = ""):
        self.vault_root = Path(root)
        self.root = self.vault_root / project_folder if project_folder else self.vault_root
        self.folder = project_folder
        for sub in ("References", "News", "Manuscript", ".rpaper"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    # 인용에 쓸 vault 상대 경로(폴더 포함, 모호성 제거)
    def ref_link(self, number: int) -> str:
        rid = f"Ref-{number:03d}"
        base = f"{self.folder}/References/{rid}" if self.folder else f"References/{rid}"
        return f"[[{base}|{number}]]"

    def cache_dir(self) -> Path:
        return self.root / ".rpaper"

    def write_reference(self, number: int, ref: dict, summary: str = "") -> str:
        rid = f"Ref-{number:03d}"
        authors = ", ".join(ref.get("authors", [])[:8])
        fm = _fm({
            "id": rid, "type": "reference", "number": number,
            "source": ref.get("source", ""), "title": ref.get("title", ""),
            "year": ref.get("year", ""), "doi": ref.get("doi", ""),
            "url": ref.get("url", ""), "aliases": [rid, f"[{number}]"],
            "tags": ["reference", f"src/{ref.get('source','unknown')}"],
        })
        body = f"""{fm}

# [{number}] {ref.get('title','')}

**Authors:** {authors}
**Journal:** {ref.get('journal','')} ({ref.get('year','')})
**Link:** {ref.get('url','')}

## Summary
{summary or '_요약 대기 중 (LLM 키 입력 시 자동 생성)_'}

## Abstract
{ref.get('abstract','') or '_없음_'}

## Citation
> {_citation(ref, number)}

^{rid.lower()}
"""
        (self.root / "References" / f"{rid}.md").write_text(body, encoding="utf-8")
        return rid

    def write_bibliography(self, refs: list[dict]) -> None:
        lines = [_citation(r, i) for i, r in enumerate(refs, start=1)]
        body = f"""{_fm({"type": "bibliography", "count": len(refs), "tags": ["bibliography"]})}

# Bibliography ({len(refs)})

> 번호는 본문 인용 번호와 일치. BibTeX 는 `.rpaper/references.bib` 참고.

{chr(10).join(lines) if lines else '_없음_'}
"""
        (self.root / "Bibliography.md").write_text(body, encoding="utf-8")

    def write_news(self, item: dict) -> str:
        title = item.get("title", "untitled")
        name = slug(title)
        fm = _fm({
            "type": "news", "source": item.get("source", ""),
            "url": item.get("url", ""), "published": item.get("published", ""),
            "tags": ["news"],
        })
        body = f"""{fm}

# {title}

**Source:** {item.get('source','')} — {item.get('published','')}
**Link:** {item.get('url','')}

{item.get('summary','')}
"""
        (self.root / "News" / f"{name}.md").write_text(body, encoding="utf-8")
        return name

    def write_index(self, title: str, ref_numbers: list[int], news_names: list[str],
                    keywords: list[str]) -> None:
        ref_links = "\n".join(f"{n}. {self.ref_link(n)}" for n in ref_numbers)
        news_links = "\n".join(f"- [[{n}]]" for n in news_names)
        man = self.folder + "/Manuscript/" if self.folder else "Manuscript/"
        sections = ["Introduction", "Materials-and-Methods", "Results", "Discussion", "Conclusion"]
        sec_links = "\n".join(f"- [[{man}{s}|{s.replace('-', ' ')}]]" for s in sections)
        body = f"""{_fm({"type": "MOC", "title": title, "updated": str(date.today()), "tags": ["project", "rpaper"]})}

# {title}

> 연구 위키 허브 — {date.today()}

**Keywords:** {", ".join(keywords)}

## 📄 Manuscript
{sec_links}
- [[{self.folder + '/Bibliography' if self.folder else 'Bibliography'}|Bibliography]]

## 📚 References ({len(ref_numbers)})
{ref_links or '_없음_'}

## 📰 News & Updates ({len(news_names)})
{news_links or '_없음_'}
"""
        (self.root / "00-Index.md").write_text(body, encoding="utf-8")

    def write_section(self, name: str, content: str) -> None:
        (self.root / "Manuscript" / f"{name}.md").write_text(content, encoding="utf-8")
