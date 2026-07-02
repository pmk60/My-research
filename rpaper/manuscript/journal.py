"""저널 템플릿 + 투고 가이드라인 처리.

저널을 정할 때마다 해당 저널 홈페이지에서 템플릿과 author guidelines 를
다운로드합니다. 두 가지를 항상 함께 가져옵니다.

자동 다운로드는 URL 만 알면 가능하지만, 많은 저널이 로그인/동적 페이지라
URL 확인이 필요합니다. 그래서 다운로드 + 체크리스트 추출 인터페이스를 둡니다.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path
from dataclasses import dataclass


@dataclass
class JournalSpec:
    name: str
    template_url: str = ""
    guidelines_url: str = ""


def download(url: str, dest: Path) -> dict:
    if not url:
        return {"ok": False, "error": "URL 없음"}
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rpaper/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            dest.write_bytes(resp.read())
        return {"ok": True, "path": str(dest)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "hint": "로그인/동적 페이지일 수 있음 — 수동 다운로드 후 경로 지정"}


def fetch_journal_assets(spec: JournalSpec, out_dir: str | Path) -> dict:
    out = Path(out_dir)
    results = {"journal": spec.name}
    if spec.template_url:
        ext = Path(spec.template_url).suffix or ".docx"
        results["template"] = download(spec.template_url, out / f"{spec.name}_template{ext}")
    if spec.guidelines_url:
        ext = Path(spec.guidelines_url).suffix or ".pdf"
        results["guidelines"] = download(spec.guidelines_url, out / f"{spec.name}_guidelines{ext}")
    if not spec.template_url and not spec.guidelines_url:
        results["note"] = ("config.journal 에 template_url/guidelines_url 입력 필요. "
                           "저널 'Author Guidelines' / 'Manuscript template' 페이지 URL 을 넣으세요.")
    return results
