"""rpaper 부분의 네트워크/API 키 없이 동작하는 오프라인 테스트.

- FigureLabs 클라이언트 (integrations/figurelabs.py): 키 미설정 안내, 생성/polling/다운로드
  (HTTP 훅을 모의로 갈아끼워 검증), 업로드 미제공 안내.
- Results 캐시 매칭 (manuscript/sections.py): figures.json <-> stats_all.json 페어링과
  폴백 마크다운 골격.

실행: python -m pytest tests/test_rpaper_offline.py
또는: python tests/test_rpaper_offline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpaper.integrations import figurelabs as fl
from rpaper.manuscript import sections


# ---------------------------------------------------------------- figurelabs
def test_figurelabs_defaults_and_env():
    c = fl.FigurelabsClient()
    assert c.base_url == fl.DEFAULT_BASE_URL
    assert not c.configured
    assert not fl.FigurelabsClient(api_key="fl_live_x").configured is False


def test_figurelabs_unconfigured_friendly_error(monkeypatch=None):
    """키 미설정 시 R 로컬 figure 를 권장하는 친절한 오류를 반환(예외로 죽지 않음)."""
    import os
    saved = os.environ.pop(fl.ENV_API_KEY, None)
    try:
        c = fl.FigurelabsClient()
        res = c.create_figure("a schematic of the workflow")
        assert res["ok"] is False
        assert "FIGURELABS_API_KEY" in res["error"]
        assert "R(ggplot2)" in res["error"]
        assert res["hint"]["rest_api"] == fl.DEFAULT_BASE_URL
        assert res["hint"]["mcp_url"] == fl.MCP_URL
    finally:
        if saved is not None:
            os.environ[fl.ENV_API_KEY] = saved


def test_create_figure_success_polling(monkeypatch):
    """POST -> task_id -> polling(succeeded) -> output_url 반환."""
    calls = {"posts": 0, "polls": 0, "sleeps": 0}

    def fake_post(url, body, api_key, timeout=30.0):
        calls["posts"] += 1
        assert url.endswith("/images/generations")
        assert body["mode"] == "generations" and body["style"] == "Flat"
        assert api_key == "fl_live_test"
        return {"task_id": "tsk_123", "status": "processing"}

    states = [{"status": "pending"}, {"status": "processing"},
              {"status": "succeeded", "output_url": "https://files.figurelabs.ai/presigned/x.png"}]

    def fake_get(url, api_key, timeout=30.0):
        calls["polls"] += 1
        assert url.endswith("/tasks/tsk_123")
        return states[min(calls["polls"] - 1, len(states) - 1)]

    def fake_sleep(_s):
        calls["sleeps"] += 1

    monkeypatch.setattr(fl, "_post_json", fake_post)
    monkeypatch.setattr(fl, "_get_json", fake_get)
    monkeypatch.setattr(fl, "_sleep", fake_sleep)

    c = fl.FigurelabsClient(api_key="fl_live_test")
    res = c.create_figure("workflow diagram", style="Flat", poll_interval=3.0, timeout=120.0)
    assert res["ok"] is True
    assert res["task_id"] == "tsk_123"
    assert res["output_url"].startswith("https://files.figurelabs.ai/presigned/")
    assert calls["posts"] == 1 and calls["polls"] == 3 and calls["sleeps"] == 2


def test_create_figure_timeout_and_failure(monkeypatch):
    """타임아웃과 종료 상태(failed)를 오류로 반환."""
    def fake_post(url, body, api_key, timeout=30.0):
        return {"task_id": "tsk_t", "status": "processing"}

    monkeypatch.setattr(fl, "_post_json", fake_post)
    monkeypatch.setattr(fl, "_get_json", lambda *a, **k: {"status": "processing"})
    monkeypatch.setattr(fl, "_sleep", lambda _s: None)

    c = fl.FigurelabsClient(api_key="fl_live_test")
    res = c.create_figure("x", timeout=0.0)
    assert res["ok"] is False and "타임아웃" in res["error"]

    monkeypatch.setattr(fl, "_get_json", lambda *a, **k: {"status": "failed"})
    res = c.create_figure("x", timeout=5.0)
    assert res["ok"] is False and res["status"] == "failed"


def test_download_figure(monkeypatch, tmp_path):
    """output_url 에서 내려받아 로컬 파일로 저장."""
    monkeypatch.setattr(fl, "_get_bytes", lambda url, timeout=60.0: b"\x89PNG fake")

    c = fl.FigurelabsClient(api_key="fl_live_test")
    dest = tmp_path / "figures" / "fig1.png"
    res = c.download_figure("https://files.figurelabs.ai/presigned/x.png", str(dest))
    assert res["ok"] is True and res["bytes"] == 9
    assert dest.read_bytes() == b"\x89PNG fake"

    res = c.download_figure("", str(dest))
    assert res["ok"] is False


def test_upload_figure_not_supported():
    """REST v1 은 업로드 엔드포인트가 없음 — 시그니처 유지 + 로컬 경로 안내."""
    c = fl.FigurelabsClient(api_key="fl_live_test")
    res = c.upload_figure("/nonexistent/fig.png", "weight")
    assert res["ok"] is False
    assert "업로드" in res["error"]
    assert res["local_path"] == "/nonexistent/fig.png"
    assert res["local_path_exists"] is False
    assert "create_figure" in res["hint"]


# ---------------------------------------------------------------- results 캐시 매칭
def test_pair_figure_stats_basic():
    figs = [{"figure": "a/weight.png", "caption": "boxplot: weight", "value": "weight",
             "group": "group", "kind": "boxplot"},
            {"figure": "a/score.png", "caption": "", "value": "score",
             "group": "group", "kind": "bar"}]
    stats = [{"value": "weight", "group": "group", "test": "Welch two-sample t-test",
              "statistic": -4.12, "p_value": 0.0012, "significant": True,
              "means": {"ctrl": 10.2, "treat": 15.8}}]
    pairs = sections.pair_figure_stats(figs, stats)
    assert len(pairs) == 2
    assert pairs[0]["figure"]["value"] == "weight" and pairs[0]["stats"]["value"] == "weight"
    assert pairs[1]["figure"]["value"] == "score" and pairs[1]["stats"] is None  # 도표만 있음


def test_pair_figure_stats_stats_only_and_group_preference():
    figs = [{"figure": "a/x.png", "value": "x", "group": "batchA", "kind": "boxplot"}]
    stats = [{"value": "x", "group": "batchA", "test": "One-way ANOVA", "statistic": 5.1,
              "p_value": 0.02, "significant": True, "means": {"a": 1, "b": 2}},
             {"value": "x", "group": "batchB", "test": "One-way ANOVA", "statistic": 9.9,
              "p_value": 0.001, "significant": True, "means": {}},
             {"value": "y", "group": "group", "test": "Mann-Whitney U test",
              "statistic": 33.0, "p_value": 0.4, "significant": False, "means": {}}]
    pairs = sections.pair_figure_stats(figs, stats)
    # figure 는 group 이 일치하는 통계와 짝이 되어야 함
    assert pairs[0]["stats"]["group"] == "batchA"
    # 통계만 있는 항목(y, batchB)도 figure 없이 포함
    tail = [p for p in pairs if p["figure"] is None]
    assert {p["stats"]["value"] + ":" + p["stats"]["group"] for p in tail} == {"y:group", "x:batchB"}


def test_write_results_fallback_markdown():
    """LLM 미설정: Figure별 이미지 + 대응 통계가 매핑된 마크다운 골격."""
    figs = [{"figure": "vault/cache/analysis/figure_boxplot_weight.png", "value": "weight",
             "group": "group", "kind": "boxplot", "caption": "boxplot: weight vs group"}]
    stats = [{"value": "weight", "group": "group", "test": "Welch two-sample t-test",
              "statistic": -4.12, "p_value": 0.0012, "significant": True,
              "means": {"ctrl": 10.2, "treat": 15.8}, "engine": "R"}]
    out = sections.write_results("테스트 연구", sections.pair_figure_stats(figs, stats))
    assert out.startswith("# Results")
    assert "![Figure 1](vault/cache/analysis/figure_boxplot_weight.png)" in out
    assert "Welch two-sample t-test" in out and "p=0.0012" in out
    assert "ctrl=10.2" in out
    assert "도표만" not in out


def test_write_results_handles_orphans_and_errors():
    figs = [{"figure": "f1.png", "value": "orphan", "group": "g", "kind": "bar", "caption": ""}]
    stats = [{"value": "err", "error": "각 그룹에 최소 2개 표본 필요"},
             {"value": "solo", "group": "g", "test": "One-way ANOVA", "statistic": 6.4,
              "p_value": 0.009, "significant": True, "means": {"a": 1.0, "b": 2.0}}]
    out = sections.write_results("테스트", sections.pair_figure_stats(figs, stats))
    assert "orphan" in out and "통계 검정**: (analyze 캐시 없음" in out
    assert "solo" in out and "p=0.009" in out
    assert "각 그룹에 최소 2개 표본 필요" in out
    assert "통계 결과만 있는 항목" in out


def test_write_results_empty():
    out = sections.write_results("테스트", [])
    assert "# Results" in out and "analyze/figure 산출물이 없습니다" in out


if __name__ == "__main__":
    class _MP:
        """pytest 의 monkeypatch fixture 최소 대체 (스크립트 실행용)."""
        def __init__(self):
            self._undo = []
        def setattr(self, target, name, value):
            self._undo.append((target, name, getattr(target, name)))
            setattr(target, name, value)
        def undo(self):
            for t, n, v in reversed(self._undo):
                setattr(t, n, v)
            self._undo.clear()

    mp = _MP()
    try:
        import tempfile
        test_figurelabs_defaults_and_env()
        test_figurelabs_unconfigured_friendly_error()
        test_create_figure_success_polling(mp)
        test_create_figure_timeout_and_failure(mp)
        with tempfile.TemporaryDirectory() as td:
            test_download_figure(mp, Path(td))
        test_upload_figure_not_supported()
        test_pair_figure_stats_basic()
        test_pair_figure_stats_stats_only_and_group_preference()
        test_write_results_fallback_markdown()
        test_write_results_handles_orphans_and_errors()
        test_write_results_empty()
    finally:
        mp.undo()
    print("rpaper 오프라인 테스트 전부 통과 ✓")
