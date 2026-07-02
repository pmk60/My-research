"""네트워크/API 키 없이 동작하는 오프라인 테스트.

실행: python -m pytest tests/  (pytest 설치 시)
또는: python tests/test_offline.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from patent_pipeline.config import load_config
from patent_pipeline.models import (
    Idea,
    PatentabilityAssessment,
    PatentDraft,
    PipelineResult,
    PriorArt,
    PriorArtAnalysis,
)
from patent_pipeline.obsidian import VaultWriter
from patent_pipeline.search.kipris import KiprisClient


def _sample_result() -> PipelineResult:
    idea = Idea(
        raw_text="접이식 자전거 잠금장치",
        title="모듈형 접이식 자전거 잠금장치",
        technical_field="자전거 보안 장치",
        problem="휴대 불편",
        solution="자력 결합 분절 구조",
        key_features=["분절형 링크", "자력 결합 잠금부"],
        effects=["경량화"],
        keywords_ko=["접이식 잠금장치"],
        keywords_en=["foldable bike lock"],
    )
    art = PriorArt(
        application_number="1020200012345",
        title="접이식 자전거 자물쇠",
        abstract="여러 링크가 연결된 접이식 자물쇠",
        applicant="홍길동",
        status="등록",
        score=82.0,
    )
    analysis = PriorArtAnalysis(
        prior_art=art,
        relevance="링크 구조 유사",
        overlapping_features=["분절형 링크"],
        distinguishing_features=["자력 결합부"],
        novelty_risk="medium",
        inventive_step_risk="low",
    )
    assessment = PatentabilityAssessment(
        novelty_conclusion="신규성 인정 여지",
        inventive_step_conclusion="진보성 주장 가능",
        closest_prior_art=["1020200012345"],
        distinguishing_features=["자력 결합 잠금부"],
        registration_likelihood="medium",
    )
    draft = PatentDraft(
        title="모듈형 접이식 자전거 잠금장치",
        independent_claims=["복수의 분절형 링크와 자력 결합부를 포함하는 자전거 잠금장치."],
        dependent_claims=["제1항에 있어서, 진동 센서를 더 포함하는 자전거 잠금장치."],
        abstract="자력 결합부를 갖는 접이식 자전거 잠금장치.",
    )
    return PipelineResult(
        idea=idea, prior_art=[art], analyses=[analysis], assessment=assessment, draft=draft
    )


def test_config_defaults():
    cfg = load_config("does-not-exist.yaml")
    assert cfg.model == "claude-opus-4-8"
    assert cfg.search.max_results == 30
    assert cfg.resolved_vault_path is not None


def test_kipris_search_parsing():
    """샘플 XML 파싱이 PriorArt 로 매핑되는지(네트워크 없이)."""
    xml = """<response><body><items>
      <item>
        <applicationNumber>1020200012345</applicationNumber>
        <inventionTitle>접이식 자전거 자물쇠</inventionTitle>
        <astrtCont>여러 링크가 연결된 접이식 자물쇠</astrtCont>
        <applicantName>홍길동</applicantName>
        <registerStatus>등록</registerStatus>
        <ipcNumber>E05B</ipcNumber>
      </item>
    </items></body></response>"""
    client = KiprisClient.__new__(KiprisClient)  # __init__ 우회(httpx 불필요)
    arts = client._parse_search(xml)
    assert len(arts) == 1
    assert arts[0].title == "접이식 자전거 자물쇠"
    assert arts[0].application_number == "1020200012345"
    assert arts[0].ipc == "E05B"


def test_obsidian_output():
    result = _sample_result()
    with tempfile.TemporaryDirectory() as d:
        paths = VaultWriter(d, folder="Patents").write(result)
        assert len(paths) == 5  # MOC + 아이디어 + 선행문헌1 + 판단 + 초안
        moc = next(Path(p) for p in paths if "개요" in p)
        text = moc.read_text(encoding="utf-8")
        assert "[[모듈형 접이식 자전거 잠금장치 - 아이디어]]" in text
        assert "자력 결합 잠금부" in text
        draft = next(Path(p) for p in paths if "명세서" in p)
        assert "【청구항 1】" in draft.read_text(encoding="utf-8")


def test_literature_abstract_reconstruction():
    from patent_pipeline.search.literature import reconstruct_abstract

    inv = {"A": [0], "foldable": [1], "lock": [2]}
    assert reconstruct_abstract(inv) == "A foldable lock"
    assert reconstruct_abstract(None) == ""


def test_literature_mapping():
    from patent_pipeline.search.literature import LiteratureClient

    work = {
        "id": "https://openalex.org/W123",
        "display_name": "A foldable bicycle lock",
        "publication_year": 2021,
        "type": "article",
        "doi": "https://doi.org/10.1/x",
        "authorships": [{"author": {"display_name": "Kim"}}],
        "abstract_inverted_index": {"Light": [0], "lock": [1]},
    }
    art = LiteratureClient._map(work)
    assert art.source == "OpenAlex"
    assert art.title == "A foldable bicycle lock"
    assert art.publication_number == "W123"
    assert art.applicant == "Kim"
    assert art.abstract == "Light lock"


def test_extract_json():
    from patent_pipeline.llm_claude_code import extract_json

    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('설명입니다.\n```json\n{"a": 1}\n```\n끝.') == {"a": 1}
    assert extract_json('앞말 {"a": {"b": "중{괄}호"}} 뒷말') == {"a": {"b": "중{괄}호"}}
    assert extract_json('{"s": "escaped \\" quote"}') == {"s": 'escaped " quote'}


def test_resolve_backend():
    from patent_pipeline.config import Config
    from patent_pipeline.pipeline import resolve_backend
    from patent_pipeline.llm_claude_code import claude_cli_available

    cfg = Config()
    cfg.anthropic_api_key = "sk-test"
    assert resolve_backend(cfg) == "api"          # auto + 키 → api

    cfg.llm_backend = "claude-code"
    assert resolve_backend(cfg) == "claude-code"  # 명시 지정이 우선

    cfg2 = Config()  # 키 없음, auto
    expected = "claude-code" if claude_cli_available() else "none"
    assert resolve_backend(cfg2) == expected


def test_dry_run_pipeline():
    """API 키 없이 모의 모드로 전체 파이프라인이 노트를 생성하는지."""
    from patent_pipeline.config import Config
    from patent_pipeline.pipeline import PatentPipeline

    with tempfile.TemporaryDirectory() as d:
        cfg = Config()
        cfg.obsidian.vault_path = d
        pipeline = PatentPipeline(cfg, dry_run=True)
        result = pipeline.run("접이식 자전거 잠금장치 아이디어")
        assert result.assessment is not None
        assert result.draft is not None
        assert len(result.prior_art) == 3       # 모의 특허 3건
        assert len(result.analyses) == 3
        assert len(result.note_paths) == 7       # MOC + 아이디어 + 선행 3 + 판단 + 초안


if __name__ == "__main__":
    test_config_defaults()
    test_kipris_search_parsing()
    test_obsidian_output()
    test_literature_abstract_reconstruction()
    test_literature_mapping()
    test_extract_json()
    test_resolve_backend()
    test_dry_run_pipeline()
    print("모든 오프라인 테스트 통과 ✓")
