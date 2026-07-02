"""BibTeX 내보내기 — 수집한 reference 를 .bib 로 저장(Zotero/저널 투고 호환)."""
from __future__ import annotations

import re
from pathlib import Path


def _key(ref: dict, number: int) -> str:
    first = (ref.get("authors") or ["anon"])[0].split()[0] if ref.get("authors") else "anon"
    first = re.sub(r"[^A-Za-z]", "", first) or "anon"
    return f"{first}{ref.get('year','') or number}_{number}"


def _entry(ref: dict, number: int) -> str:
    key = _key(ref, number)
    authors = " and ".join(ref.get("authors", [])) or "Unknown"
    fields = {
        "title": ref.get("title", ""),
        "author": authors,
        "journal": ref.get("journal", ""),
        "year": ref.get("year", ""),
        "doi": ref.get("doi", ""),
        "url": ref.get("url", ""),
        "note": f"PMID/UID: {ref.get('uid','')}" if ref.get("uid") else "",
    }
    lines = [f"@article{{{key},"]
    for k, v in fields.items():
        if v:
            v = str(v).replace("{", "").replace("}", "")
            lines.append(f"  {k} = {{{v}}},")
    lines.append("}")
    return "\n".join(lines)


def export_bibtex(refs: list[dict], path: str | Path) -> str:
    text = "\n\n".join(_entry(r, i) for i, r in enumerate(refs, start=1)) + "\n"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    return str(path)
