"""파이프라인 오케스트레이터.

아이디어 → (구조화) → (KIPRIS 특허 + OpenAlex 논문 선행조사) → (스크리닝)
→ (정밀 비교분석) → (특허성 판단) → (명세서 초안) → (Obsidian 위키 출력)

빠르되 충분한 검토를 위해, 검색·분석을 병렬 처리하고 캐시를 활용한다.
--dry-run 모드에서는 모의(mock) 구현으로 키 없이 전체 흐름을 시연한다.
"""

from __future__ import annotations

from typing import Callable

from .analysis import (
    analyze_prior_art,
    assess_patentability,
    screen_prior_art,
    structure_idea,
)
from .cache import Cache
from .config import Config
from .drafting import draft_specification
from .llm import LLM
from .llm_claude_code import ClaudeCodeLLM, claude_cli_available
from .mock import MockKiprisClient, MockLLM
from .models import PipelineResult, PriorArt
from .obsidian import VaultWriter
from .search import KiprisClient, LiteratureClient

ProgressFn = Callable[[str], None]

AnyLLM = LLM | ClaudeCodeLLM | MockLLM


def _noop(_: str) -> None:
    pass


def resolve_backend(config: Config) -> str:
    """설정에 따라 실제 사용할 LLM 백엔드를 결정한다.

    auto: API 키가 있으면 api, 없으면 claude CLI(구독) 사용.
    """
    backend = (config.llm_backend or "auto").lower()
    if backend == "api":
        return "api"
    if backend == "claude-code":
        return "claude-code"
    # auto
    if config.anthropic_api_key:
        return "api"
    if claude_cli_available():
        return "claude-code"
    return "none"


class PatentPipeline:
    def __init__(
        self,
        config: Config,
        progress: ProgressFn | None = None,
        use_cache: bool = True,
        dry_run: bool = False,
    ):
        self.config = config
        self.progress = progress or _noop
        self.cache = Cache(config.cache_dir, enabled=use_cache and not dry_run)
        self.dry_run = dry_run
        self._llm: AnyLLM | None = None

    @property
    def llm(self) -> AnyLLM:
        if self._llm is None:
            if self.dry_run:
                self._llm = MockLLM()
                return self._llm
            backend = resolve_backend(self.config)
            if backend == "api":
                self._llm = LLM(
                    api_key=self.config.require_anthropic(),
                    model=self.config.model,
                    effort=self.config.effort,
                    cache=self.cache,
                )
            elif backend == "claude-code":
                self.progress("   · LLM 백엔드: Claude Code CLI (구독 사용, 추가 과금 없음)")
                self._llm = ClaudeCodeLLM(
                    model=self.config.claude_code_model,
                    cache=self.cache,
                )
            else:
                raise RuntimeError(
                    "사용 가능한 LLM 백엔드가 없습니다. 다음 중 하나가 필요합니다:\n"
                    "  1) Claude Code CLI 설치 + Pro/Max 로그인 (추가 과금 없음)\n"
                    "  2) 환경변수 ANTHROPIC_API_KEY (유료 API)\n"
                    "  3) --dry-run (모의 실행)"
                )
        return self._llm

    def _search_patents(self, keywords: list[str]) -> list[PriorArt]:
        cfg = self.config
        if self.dry_run:
            with MockKiprisClient() as kipris:
                arts = kipris.search_for_idea(keywords, rows=cfg.search.max_results)
            return arts
        if not cfg.kipris_service_key:
            self.progress("   · KIPRIS 키 없음 → 특허 검색 생략")
            return []
        with KiprisClient(
            cfg.kipris_service_key,
            concurrency=cfg.search.concurrency,
            cache=self.cache,
        ) as kipris:
            return kipris.search_for_idea(keywords, rows=cfg.search.max_results)

    def _search_literature(self, keywords_en: list[str], title: str) -> list[PriorArt]:
        cfg = self.config
        if self.dry_run or not cfg.search.use_literature:
            return []
        try:
            with LiteratureClient(mailto=cfg.search.literature_mailto, cache=self.cache) as lit:
                return lit.search_for_idea(
                    keywords_en, title, per_page=cfg.search.literature_max_results
                )
        except Exception as exc:  # noqa: BLE001 - 논문 검색 실패는 치명적이지 않음
            self.progress(f"   · 논문 검색 건너뜀({exc})")
            return []

    def _enrich_claims(self, arts: list[PriorArt]) -> None:
        """KIPRIS 특허에 한해 청구범위를 보강(논문/모의는 제외)."""
        cfg = self.config
        if self.dry_run:
            MockKiprisClient().enrich_with_claims(arts)
            return
        patents = [a for a in arts if a.source == "KIPRIS" and a.application_number]
        if not patents or not cfg.kipris_service_key:
            return
        with KiprisClient(
            cfg.kipris_service_key,
            concurrency=cfg.search.concurrency,
            cache=self.cache,
        ) as kipris:
            kipris.enrich_with_claims(patents)

    def run(self, raw_idea: str, skip_search: bool = False) -> PipelineResult:
        cfg = self.config

        # 1. 아이디어 구조화
        self.progress("① 아이디어 구조화 중...")
        idea = structure_idea(self.llm, raw_idea)
        result = PipelineResult(idea=idea)
        self.progress(f"   → 명칭: {idea.title}")

        # 2. 선행조사 (특허 + 논문)
        prior_art: list[PriorArt] = []
        if not skip_search:
            self.progress("② 선행조사 중 (특허 + 논문)...")
            keywords = (idea.keywords_ko or []) + (idea.keywords_en or [])
            patents = self._search_patents(keywords)
            self.progress(f"   → 특허 {len(patents)}건")
            papers = self._search_literature(idea.keywords_en or [], idea.title)
            self.progress(f"   → 논문 {len(papers)}건")
            prior_art = patents + papers

            # 3. 스크리닝 후 상위 N건만 청구범위 보강
            if prior_art:
                self.progress("③ 관련도 스크리닝 중...")
                top = screen_prior_art(self.llm, idea, prior_art, cfg.search.analyze_top_n)
                self.progress(f"   → 상위 {len(top)}건 선정")
                self._enrich_claims(top)
                prior_art = top
        else:
            self.progress("② 선행조사 생략(--skip-search)")

        result.prior_art = prior_art

        # 4. 정밀 비교 분석
        if prior_art:
            self.progress("④ 선행문헌 정밀 비교 분석 중...")
            result.analyses = analyze_prior_art(
                self.llm, idea, prior_art, concurrency=cfg.search.concurrency
            )
            self.progress(f"   → {len(result.analyses)}건 분석 완료")

        # 5. 특허성 판단
        self.progress("⑤ 신규성·진보성 종합 판단 중...")
        result.assessment = assess_patentability(self.llm, idea, result.analyses)
        self.progress(f"   → 등록 가능성: {result.assessment.registration_likelihood}")

        # 6. 명세서 초안
        self.progress("⑥ 특허 명세서 초안 작성 중...")
        result.draft = draft_specification(self.llm, idea, result.assessment, result.analyses)
        self.progress(
            f"   → 청구항 {len(result.draft.independent_claims)}개(독립) "
            f"+ {len(result.draft.dependent_claims)}개(종속)"
        )

        # 7. Obsidian 출력
        self.progress("⑦ Obsidian 위키 노트 생성 중...")
        writer = VaultWriter(cfg.resolved_vault_path, folder=cfg.obsidian.folder)
        result.note_paths = writer.write(result)
        self.progress(f"   → {len(result.note_paths)}개 노트 생성 ({cfg.resolved_vault_path})")

        return result
