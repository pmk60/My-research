"""오프라인 검증 테스트 (네트워크/R/LLM 없이 동작하는 부분)."""
import json
from pathlib import Path

from rpaper.knowledge.obsidian import Vault, slug, _citation
from rpaper.knowledge.citations import export_bibtex
from rpaper.analysis import stats, figures


REF = {
    "source": "pubmed", "uid": "123", "title": "A study of X",
    "authors": ["Kim J", "Lee S"], "journal": "J Test", "year": "2024",
    "abstract": "We tested X. It worked. Limitations exist.", "doi": "10.1/x",
    "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
}


def test_slug():
    assert slug("Effect of X on Y!") == "Effect-of-X-on-Y"


def test_citation_format():
    c = _citation(REF, 1)
    assert c.startswith("1. ") and "Kim J" in c and "doi:10.1/x" in c


def test_vault_nests_in_subfolder(tmp_path):
    v = Vault(tmp_path, "MyProject")
    assert (tmp_path / "MyProject" / "References").exists()
    v.write_reference(1, REF, "summary text")
    assert (tmp_path / "MyProject" / "References" / "Ref-001.md").exists()
    # 인용 링크는 폴더 경로를 포함해 모호성 제거
    assert v.ref_link(1) == "[[MyProject/References/Ref-001|1]]"


def test_vault_does_not_touch_existing_notes(tmp_path):
    existing = tmp_path / "MyDailyNote.md"
    existing.write_text("# 기존 노트", encoding="utf-8")
    Vault(tmp_path, "Proj").write_index("T", [], [], ["k"])
    assert existing.read_text(encoding="utf-8") == "# 기존 노트"  # 손대지 않음


def test_index_and_bibliography(tmp_path):
    v = Vault(tmp_path, "P")
    v.write_reference(1, REF, "s")
    v.write_bibliography([REF])
    v.write_index("Title", [1], [], ["kw"])
    idx = (tmp_path / "P" / "00-Index.md").read_text(encoding="utf-8")
    assert "[[P/References/Ref-001|1]]" in idx
    assert (tmp_path / "P" / "Bibliography.md").exists()


def test_bibtex_export(tmp_path):
    p = export_bibtex([REF], tmp_path / "refs.bib")
    text = Path(p).read_text(encoding="utf-8")
    assert "@article{" in text and "Kim J and Lee S" in text and "10.1/x" in text


def test_python_ttest_significant():
    out = stats.welch_t_python([98, 95, 97, 99], [72, 68, 75, 70])
    assert out["p_approx"] < 0.05


def test_analyze_fallback_schema(tmp_path):
    csv = tmp_path / "raw.csv"
    csv.write_text("group,v\nc,1\nc,2\nc,3\nt,8\nt,9\nt,10\n", encoding="utf-8")
    res = stats.analyze(str(csv), "group", "v", str(tmp_path / "out"), rscript_path="nonexistent")
    assert res["engine"] == "python"
    assert set(["test", "p_value", "significant", "means"]).issubset(res)
    assert res["significant"] is True


def test_figure_manifest(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    figures._append_manifest(str(d), {"figure": "f.png", "caption": "c", "value": "v", "group": "g"})
    figures._append_manifest(str(d), {"figure": "f.png", "caption": "c2", "value": "v", "group": "g"})
    m = figures.load_manifest(str(d))
    assert len(m) == 1 and m[0]["caption"] == "c2"  # 재실행 시 중복 제거


def test_r_script_emits_json_writer(tmp_path):
    script = stats.generate_r_script("x.csv", "g", "v", str(tmp_path), 0.05)
    assert "stats.json" in script and "writeLines" in script


def test_r_script_has_normality_and_nonparametric(tmp_path):
    script = stats.generate_r_script("x.csv", "g", "v", str(tmp_path), 0.05)
    assert "shapiro.test" in script
    assert "wilcox.test" in script and "kruskal.test" in script


def test_dedupe_by_doi_and_title():
    from rpaper.cli import _dedupe
    from rpaper.collectors.pubmed import Reference
    mk = lambda uid, title, doi: Reference("pubmed", uid, title, [], "", "", "", doi, "")
    refs = [mk("1", "Study A", "10.1/a"), mk("2", "Study A dup", "10.1/a"),
            mk("3", "Study B", ""), mk("4", "study b", "")]
    out = _dedupe(refs)
    assert len(out) == 2  # DOI 중복 1개, 제목 중복 1개 제거


def test_conclusion_skeleton():
    from rpaper.manuscript.sections import write_conclusion
    out = write_conclusion("T", "results", "discussion", api_key="")
    assert out.startswith("# Conclusion")


def test_figure_unknown_kind(tmp_path):
    res = figures.make_figure("x.csv", "g", "v", str(tmp_path), kind="pie")
    assert res["ok"] is False and "알 수 없는" in res["error"]


def test_figure_builders_exist():
    assert set(figures._BUILDERS) == {"boxplot", "bar", "scatter", "line"}


def test_assemble_markdown(tmp_path):
    from rpaper.manuscript.assemble import assemble_markdown
    root = tmp_path / "Proj"
    man = root / "Manuscript"
    man.mkdir(parents=True)
    (man / "Introduction.md").write_text("---\ntype: x\n---\n\n# Introduction\n\nIntro body.", encoding="utf-8")
    (man / "Results.md").write_text("# Results\n\nResults body.", encoding="utf-8")
    (root / "Bibliography.md").write_text("# Bibliography\n\n1. Ref.", encoding="utf-8")
    out = assemble_markdown(man, root, "My Title")
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# My Title")
    assert "Intro body." in text and "Results body." in text and "1. Ref." in text
    assert "type: x" not in text  # frontmatter 제거됨
