"""rpaper CLI — 연구 논문 작성 파이프라인 오케스트레이터.

단계별 서브커맨드로 모바일/PC/IDE 어디서든 동일하게 실행합니다.

  rpaper collect       # PubMed/Scholar/News 수집 -> Obsidian 위키 + BibTeX
  rpaper analyze CSV GROUP VALUE   # raw data 통계분석 (R, 폴백 지원)
  rpaper figure  CSV GROUP VALUE   # R(ggplot2) figure 생성
  rpaper write SECTION             # intro|methods|results|discussion
  rpaper journal       # 저널 템플릿/가이드라인 다운로드
  rpaper status        # 진행 현황 점검
  rpaper run           # collect -> intro/methods 일괄
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .collectors import pubmed, scholar, news
from .knowledge.obsidian import Vault
from .knowledge.summarizer import summarize_reference
from .knowledge.citations import export_bibtex
from .manuscript import sections, journal, assemble as assembler
from .analysis import stats, figures
from .integrations.figurelabs import FigurelabsClient


def _dedupe(refs: list) -> list:
    """DOI -> 정규화 제목 기준으로 중복 제거(PubMed + Scholar 겹침 대비)."""
    import re
    seen_doi, seen_title, out = set(), set(), []
    for r in refs:
        doi = (getattr(r, "doi", "") or "").lower().strip()
        title = re.sub(r"\W+", "", (getattr(r, "title", "") or "").lower())
        if doi and doi in seen_doi:
            continue
        if title and title in seen_title:
            continue
        if doi:
            seen_doi.add(doi)
        if title:
            seen_title.add(title)
        out.append(r)
    return out


def _keywords(cfg: Config) -> list[str]:
    kw = cfg.get("project", "keywords", default=[]) or []
    if not kw:
        title = cfg.get("project", "title", default="")
        kw = [w for w in title.split() if len(w) > 3][:5]
    return kw


def _vault(cfg: Config) -> Vault:
    return Vault(cfg.vault, cfg.project_folder)


def _analysis_dir(cfg: Config) -> Path:
    """통계/그림 산출물 기본 위치 — 프로젝트 폴더 안에 모아 Results 가 찾기 쉽게."""
    d = _vault(cfg).cache_dir() / "analysis"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- collect
def cmd_collect(cfg: Config, args) -> None:
    title = cfg.get("project", "title", default="Untitled")
    kw = _keywords(cfg)
    query = " AND ".join(kw) if kw else title
    print(f"[collect] query = {query!r}")

    def _safe(label, fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — 네트워크 차단/타임아웃에도 파이프라인 유지
            print(f"[collect] {label} 실패: {type(e).__name__}: {e}", file=sys.stderr)
            return []

    refs = _safe("PubMed", lambda: pubmed.collect(
        query, cfg.get("pubmed", "max_results", default=40), cfg.ncbi_api_key, cfg.email))
    print(f"[collect] PubMed: {len(refs)} refs")
    refs += _safe("Scholar", lambda: scholar.collect(
        query, provider=cfg.get("scholar", "provider", default="none"),
        serpapi_key=cfg.get("scholar", "serpapi_key", default=""),
        max_results=cfg.get("scholar", "max_results", default=20)))
    news_items = _safe("News", lambda: news.collect(
        query, provider=cfg.get("news", "provider", default="none"),
        newsapi_key=cfg.get("news", "newsapi_key", default=""),
        language=cfg.get("news", "language", default="en"),
        max_results=cfg.get("news", "max_results", default=30)))
    before = len(refs)
    refs = _dedupe(refs)
    if len(refs) < before:
        print(f"[collect] 중복 제거: {before} -> {len(refs)}")
    print(f"[collect] total refs: {len(refs)}, news: {len(news_items)}")

    vault = _vault(cfg)
    have_llm = bool(cfg.anthropic_api_key)
    ref_numbers, ref_dicts, summaries = [], [], []
    for i, ref in enumerate(refs, start=1):
        d = ref.to_dict()
        summ = summarize_reference(d, api_key=cfg.anthropic_api_key,
                                   model=cfg.get("llm", "model", default="claude-fable-5"))
        vault.write_reference(i, d, summ)
        ref_numbers.append(i); ref_dicts.append(d); summaries.append(summ)
    news_names = [vault.write_news(n.to_dict()) for n in news_items]
    vault.write_index(title, ref_numbers, news_names, kw)
    vault.write_bibliography(ref_dicts)

    bib = export_bibtex(ref_dicts, vault.cache_dir() / "references.bib")
    (vault.cache_dir() / "refs.json").write_text(
        json.dumps({"refs": ref_dicts, "summaries": summaries}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"[collect] Obsidian: {vault.root}")
    print(f"[collect] BibTeX: {bib}")
    if not have_llm and refs:
        print("[collect] 참고: LLM 키 미설정 — 요약은 abstract 기반. 키 입력 후 재실행하면 고품질 요약.")


def _load_refs(cfg: Config):
    p = _vault(cfg).cache_dir() / "refs.json"
    if not p.exists():
        print("먼저 `rpaper collect` 를 실행하세요.", file=sys.stderr); sys.exit(1)
    data = json.loads(p.read_text(encoding="utf-8"))
    return data["refs"], data["summaries"]


# ---------------------------------------------------------------- analyze
def cmd_analyze(cfg: Config, args) -> None:
    out = args.out or str(_analysis_dir(cfg))
    res = stats.analyze(args.csv, args.group, args.value, out,
                        alpha=cfg.get("analysis", "alpha", default=0.05),
                        rscript_path=cfg.get("analysis", "rscript_path", default="Rscript"))
    # Results 작성에 쓸 수 있도록 분석별 결과를 누적 저장
    store = Path(out) / "stats_all.json"
    allres = json.loads(store.read_text(encoding="utf-8")) if store.exists() else []
    allres = [x for x in allres if x.get("value") != res.get("value")]
    allres.append(res)
    store.write_text(json.dumps(allres, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- figure
def cmd_figure(cfg: Config, args) -> None:
    out = args.out or str(_analysis_dir(cfg))
    res = figures.make_figure(args.csv, args.group, args.value, out, kind=args.type,
                              title=args.title or "", caption=args.caption or "",
                              rscript_path=cfg.get("analysis", "rscript_path", default="Rscript"))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if cfg.get("figurelabs", "enabled", default=False):
        fl = FigurelabsClient.from_config(cfg)
        print("[figurelabs]", fl.upload_figure(res.get("figure", ""), args.value))


# ---------------------------------------------------------------- write
def cmd_write(cfg: Config, args) -> None:
    refs, summaries = _load_refs(cfg)
    title = cfg.get("project", "title", default="Untitled")
    kw = _keywords(cfg)
    api = cfg.anthropic_api_key
    model = cfg.get("llm", "model", default="claude-fable-5")
    vault = _vault(cfg)

    if args.section == "intro":
        out = sections.write_introduction(title, kw, refs, summaries, api_key=api, model=model)
        vault.write_section("Introduction", out)
    elif args.section == "methods":
        out = sections.write_methods(title, refs, summaries, api_key=api, model=model)
        vault.write_section("Materials-and-Methods", out)
    elif args.section == "results":
        adir = str(_analysis_dir(cfg))
        figs = figures.load_manifest(adir)
        store = Path(adir) / "stats_all.json"
        stats_data = json.loads(store.read_text(encoding="utf-8")) if store.exists() else []
        # figures.json <-> stats_all.json 캐시를 value/group 기준으로 자동 매칭
        pairs = sections.pair_figure_stats(figs, stats_data)
        n_paired = sum(1 for p in pairs if p["figure"] and p["stats"])
        if not figs and not stats_data:
            print("[write] 참고: analyze/figure 산출물이 없습니다. 먼저 실행하면 Results 가 풍부해집니다.")
        elif n_paired:
            print(f"[write] 캐시 매칭: figure {len(figs)}건 중 {n_paired}건을 통계 결과와 짝지었습니다.")
        out = sections.write_results(title, pairs, api_key=api, model=model)
        vault.write_section("Results", out)
    elif args.section == "discussion":
        results_path = vault.root / "Manuscript" / "Results.md"
        results_text = results_path.read_text(encoding="utf-8") if results_path.exists() else "(Results 미작성)"
        out = sections.write_discussion(title, refs, summaries, results_text, api_key=api, model=model)
        vault.write_section("Discussion", out)
    elif args.section == "conclusion":
        man = vault.root / "Manuscript"
        rt = (man / "Results.md").read_text(encoding="utf-8") if (man / "Results.md").exists() else "(Results 미작성)"
        dt = (man / "Discussion.md").read_text(encoding="utf-8") if (man / "Discussion.md").exists() else "(Discussion 미작성)"
        out = sections.write_conclusion(title, rt, dt, api_key=api, model=model)
        vault.write_section("Conclusion", out)
    else:
        print(f"알 수 없는 섹션: {args.section}", file=sys.stderr); sys.exit(1)
    print(f"[write] {args.section} -> {vault.root}/Manuscript/")


def _format_stats(stats_data: list[dict]) -> str:
    """간단 요약(로그/상태 표시용). Results 본문은 sections.write_results 가 캐시를 직접 매칭."""
    lines = []
    for s in stats_data:
        if s.get("error"):
            lines.append(f"- {s.get('value','?')}: {s['error']}")
            continue
        sig = "유의함" if s.get("significant") else "유의하지 않음"
        means = ", ".join(f"{k}={v:.3g}" for k, v in (s.get("means") or {}).items())
        lines.append(f"- {s.get('value','?')}: {s.get('test','')}, "
                     f"통계량={s.get('statistic'):.4g}, p={s.get('p_value'):.4g} ({sig}); 평균 {means}")
    return "\n".join(lines) or "(통계 결과 없음)"


# ---------------------------------------------------------------- journal
def cmd_journal(cfg: Config, args) -> None:
    vault = _vault(cfg)
    spec = journal.JournalSpec(
        name=cfg.get("journal", "name", default="journal") or "journal",
        template_url=cfg.get("journal", "template_url", default=""),
        guidelines_url=cfg.get("journal", "guidelines_url", default=""))
    res = journal.fetch_journal_assets(spec, vault.root / "Manuscript" / "journal")
    print(json.dumps(res, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- status
def cmd_status(cfg: Config, args) -> None:
    vault = _vault(cfg)
    refs_json = vault.cache_dir() / "refs.json"
    n_refs = 0
    if refs_json.exists():
        n_refs = len(json.loads(refs_json.read_text(encoding="utf-8")).get("refs", []))
    man = vault.root / "Manuscript"
    secs = {s: (man / f"{s}.md").exists() for s in
            ("Introduction", "Materials-and-Methods", "Results", "Discussion", "Conclusion")}
    figs = figures.load_manifest(str(_analysis_dir(cfg)))
    check = lambda b: "✅" if b else "⬜"
    print(f"프로젝트: {cfg.get('project','title', default='?')}")
    print(f"Vault: {vault.root}")
    print(f"  {check(n_refs>0)} References: {n_refs}")
    print(f"  {check(bool(figs))} Figures: {len(figs)}")
    for s, ok in secs.items():
        print(f"  {check(ok)} {s}")
    print("키 설정:")
    print(f"  {check(bool(cfg.anthropic_api_key))} Anthropic(LLM)")
    print(f"  {check(bool(cfg.ncbi_api_key))} NCBI(PubMed, 선택)")
    print(f"  {check(bool(cfg.get('scholar','serpapi_key', default='')))} SerpAPI(Scholar)")
    print(f"  {check(bool(cfg.get('news','newsapi_key', default='')))} NewsAPI")
    print(f"  {check(stats.r_available(cfg.get('analysis','rscript_path', default='Rscript')))} R(Rscript)")


def cmd_assemble(cfg: Config, args) -> None:
    vault = _vault(cfg)
    title = cfg.get("project", "title", default="Untitled")
    # 저널 템플릿(.docx)이 있으면 reference-doc 으로 사용
    jdir = vault.root / "Manuscript" / "journal"
    template = None
    if jdir.exists():
        docs = list(jdir.glob("*template*.docx")) or list(jdir.glob("*.docx"))
        template = docs[0] if docs else None
    res = assembler.assemble(vault.root / "Manuscript", vault.root, title, template)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if template:
        print(f"[assemble] 저널 템플릿 적용: {template.name}")
    elif res.get("ok"):
        print("[assemble] 저널 템플릿 없음 — 기본 서식. `rpaper journal` 로 받으면 자동 적용.")


def cmd_run(cfg: Config, args) -> None:
    cmd_collect(cfg, args)
    for sec in ("intro", "methods"):
        args.section = sec
        cmd_write(cfg, args)
    print("[run] 수집 + intro/methods 초안 완료. analyze/figure 후 `write results`, `write discussion` 진행.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="rpaper", description="연구 논문 작성 파이프라인")
    p.add_argument("--config", default="config.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("collect")
    a = sub.add_parser("analyze")
    a.add_argument("csv"); a.add_argument("group"); a.add_argument("value")
    a.add_argument("--out", default="")
    f = sub.add_parser("figure")
    f.add_argument("csv"); f.add_argument("group"); f.add_argument("value")
    f.add_argument("--type", default="boxplot", choices=["boxplot", "bar", "scatter", "line"])
    f.add_argument("--out", default=""); f.add_argument("--title", default="")
    f.add_argument("--caption", default="")
    w = sub.add_parser("write")
    w.add_argument("section", choices=["intro", "methods", "results", "discussion", "conclusion"])
    sub.add_parser("journal")
    sub.add_parser("assemble")
    sub.add_parser("status")
    sub.add_parser("run")

    args = p.parse_args(argv)
    cfg = Config.load(args.config)
    {"collect": cmd_collect, "analyze": cmd_analyze, "figure": cmd_figure,
     "write": cmd_write, "journal": cmd_journal, "assemble": cmd_assemble,
     "status": cmd_status, "run": cmd_run}[args.cmd](cfg, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
