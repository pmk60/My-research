"""최종 원고 조립 — 흩어진 섹션 노트를 한 파일로 합치고, 저널 템플릿에 맞춥니다.

- 항상 `Manuscript.md`(전체 원고 단일 마크다운)를 생성.
- pandoc 이 있으면 `Manuscript.docx`로 변환. 저널 템플릿(.docx)이 있으면
  `--reference-doc` 으로 그 서식을 그대로 적용(저널이 요구하는 폰트/여백/스타일).
- pandoc 미설치 시 .md 만 만들고 변환 명령을 안내(파이프라인은 멈추지 않음).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# 표준 IMRaD 순서
ORDER = [
    ("Introduction", "Introduction"),
    ("Materials-and-Methods", "Materials and Methods"),
    ("Results", "Results"),
    ("Discussion", "Discussion"),
    ("Conclusion", "Conclusion"),
    ("Bibliography", "References"),
]


def assemble_markdown(manuscript_dir: Path, project_root: Path, title: str) -> Path:
    parts = [f"# {title}\n"]
    for fname, _ in ORDER:
        # Bibliography 는 프로젝트 루트, 나머지는 Manuscript/
        src = (project_root / "Bibliography.md") if fname == "Bibliography" \
            else (manuscript_dir / f"{fname}.md")
        if src.exists():
            text = src.read_text(encoding="utf-8")
            # frontmatter(--- ... ---) 제거
            if text.startswith("---"):
                end = text.find("\n---", 3)
                if end != -1:
                    text = text[end + 4:]
            parts.append(text.strip() + "\n")
        else:
            parts.append(f"# {fname.replace('-', ' ')}\n\n_미작성_\n")
    out = manuscript_dir / "Manuscript.md"
    out.write_text("\n\n".join(parts), encoding="utf-8")
    return out


def to_docx(md_path: Path, template_docx: Path | None = None) -> dict:
    if shutil.which("pandoc") is None:
        return {"ok": False, "md": str(md_path),
                "hint": "pandoc 미설치. 설치 후: "
                        f"pandoc '{md_path}' -o Manuscript.docx"
                        + (f" --reference-doc='{template_docx}'" if template_docx else "")}
    docx = md_path.with_suffix(".docx")
    cmd = ["pandoc", str(md_path), "-o", str(docx)]
    if template_docx and Path(template_docx).exists():
        cmd += ["--reference-doc", str(template_docx)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return {"ok": True, "docx": str(docx), "md": str(md_path)}
    return {"ok": False, "md": str(md_path), "error": proc.stderr.strip()}


def assemble(manuscript_dir: str | Path, project_root: str | Path, title: str,
             template_docx: str | Path | None = None) -> dict:
    md = assemble_markdown(Path(manuscript_dir), Path(project_root), title)
    tpl = Path(template_docx) if template_docx else None
    res = to_docx(md, tpl)
    res["markdown"] = str(md)
    return res
