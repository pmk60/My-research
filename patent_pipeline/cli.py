"""명령행 인터페이스.

사용 예:
  python -m patent_pipeline run "내 아이디어 ..." --vault ~/Obsidian/MyVault
  python -m patent_pipeline run --file idea.md
  python -m patent_pipeline check        # 설정/키 점검
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .pipeline import PatentPipeline


def _progress(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def cmd_run(args: argparse.Namespace) -> int:
    from .pipeline import resolve_backend

    cfg = load_config(args.config)
    if args.vault:
        cfg.obsidian.vault_path = args.vault
    if args.model:
        cfg.model = args.model
    if args.llm:
        cfg.llm_backend = args.llm

    if args.file:
        raw = Path(args.file).read_text(encoding="utf-8")
    elif args.idea:
        raw = args.idea
    else:
        _progress("아이디어를 입력하세요(끝내려면 Ctrl-D):")
        raw = sys.stdin.read()

    if not raw.strip():
        _progress("오류: 아이디어가 비어 있습니다.")
        return 2

    if not args.dry_run and resolve_backend(cfg) == "none":
        _progress(
            "오류: 사용 가능한 LLM 백엔드가 없습니다.\n"
            "  1) Claude Code CLI 설치 + Pro/Max 로그인 (추가 과금 없음)\n"
            "  2) 환경변수 ANTHROPIC_API_KEY (유료 API)\n"
            "  3) --dry-run (모의 실행)"
        )
        return 2

    if args.dry_run:
        _progress("※ --dry-run: 모의 데이터로 전체 흐름을 시연합니다(실제 분석 아님).")

    pipeline = PatentPipeline(
        cfg, progress=_progress, use_cache=not args.no_cache, dry_run=args.dry_run
    )
    result = pipeline.run(raw, skip_search=args.skip_search)

    print("\n" + "=" * 60, file=sys.stderr)
    print("완료. 생성된 노트:", file=sys.stderr)
    for p in result.note_paths:
        print(f"  - {p}", file=sys.stderr)

    if result.assessment:
        print(
            f"\n등록 가능성: {result.assessment.registration_likelihood}",
            file=sys.stderr,
        )

    if args.json:
        json.dump(result.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
        print()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from .pipeline import resolve_backend

    cfg = load_config(args.config)
    backend = resolve_backend(cfg)
    backend_desc = {
        "api": "Anthropic API (유료 키 사용)",
        "claude-code": "Claude Code CLI (Pro/Max 구독 — 추가 과금 없음)",
        "none": "없음 ✗",
    }[backend]

    print("=== 설정 점검 ===")
    print(f"LLM 백엔드:   {backend_desc}")
    if backend == "api":
        print(f"모델: {cfg.model} (effort={cfg.effort})")
    print(f"Anthropic 키: {'설정됨' if cfg.anthropic_api_key else '없음 (claude-code 백엔드면 불필요)'}")
    print(f"KIPRIS 키:    {'설정됨' if cfg.kipris_service_key else '없음 (특허 선행조사 생략, 논문 조사는 무료로 동작)'}")
    print(f"Vault 경로:   {cfg.resolved_vault_path}")
    print(f"캐시 경로:    {cfg.cache_dir}")
    print(f"검색: 최대 {cfg.search.max_results}건 / 분석 상위 {cfg.search.analyze_top_n}건"
          f" / 동시 {cfg.search.concurrency}")
    ok = backend != "none"
    print("\n준비 상태:", "정상 — 바로 실행 가능" if ok else
          "LLM 백엔드 필요 (Claude Code 로그인 또는 ANTHROPIC_API_KEY)")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patent-pipeline",
        description="KIPRIS·문헌 기반 특허 작성 파이프라인 (Obsidian 연동)",
    )
    parser.add_argument("--config", help="config.yaml 경로", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="아이디어로부터 특허 검토·초안·위키 생성")
    run.add_argument("idea", nargs="?", help="아이디어 텍스트")
    run.add_argument("--file", "-f", help="아이디어가 담긴 파일")
    run.add_argument("--vault", help="Obsidian vault 경로(설정 덮어쓰기)")
    run.add_argument("--model", help="사용할 Claude 모델 (api 백엔드)")
    run.add_argument(
        "--llm",
        choices=["auto", "api", "claude-code"],
        help="LLM 백엔드 (기본 auto: 키 있으면 api, 없으면 claude-code 구독)",
    )
    run.add_argument("--skip-search", action="store_true", help="선행조사 생략")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="API 키 없이 모의 데이터로 전체 흐름 시연",
    )
    run.add_argument("--no-cache", action="store_true", help="캐시 사용 안 함")
    run.add_argument("--json", action="store_true", help="결과를 표준출력에 JSON 으로도 출력")
    run.set_defaults(func=cmd_run)

    check = sub.add_parser("check", help="설정/키 점검")
    check.set_defaults(func=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
