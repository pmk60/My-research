"""R 기반 Figure 생성 + figurelabs 연동 인터페이스.

- R(ggplot2) 스크립트를 생성/실행하여 publication-quality figure 를 PNG 로 출력.
- 종류: boxplot(그룹비교, 2그룹이면 ggsignif 유의성 막대), bar(평균±SE),
  scatter(상관), line(dose-response/시간경과).
- 생성한 figure 메타데이터를 figures.json 매니페스트로 누적 -> Results 작성에 사용.
- figurelabs 연동은 공식 API 사양 확인 후 활성화 (integrations/figurelabs.py).
"""
from __future__ import annotations

import json
from pathlib import Path

from .stats import run_r

_THEME = ('theme_classic(base_size = 14) + '
          'theme(legend.position = "none", axis.text = element_text(color = "black"))')


def _boxplot(csv, x, y, out, title):
    return f'''has_signif <- requireNamespace("ggsignif", quietly = TRUE)
suppressMessages({{ library(ggplot2); if (has_signif) library(ggsignif) }})
df <- read.csv("{csv}", stringsAsFactors = TRUE)
groups <- levels(df${x})
p <- ggplot(df, aes(x = {x}, y = {y}, fill = {x})) +
  geom_boxplot(outlier.shape = NA, alpha = 0.7) +
  geom_jitter(width = 0.15, size = 1.5, alpha = 0.6) +
  labs(title = "{title}", x = "{x}", y = "{y}") + {_THEME}
if (has_signif && length(groups) == 2)
  p <- p + geom_signif(comparisons = list(groups), map_signif_level = TRUE, test = "t.test", textsize = 4)
ggsave("{out}", p, width = 6, height = 5, dpi = 300)
cat("Saved figure: {out}\\n")
'''


def _barplot(csv, x, y, out, title):
    return f'''suppressMessages({{ library(ggplot2) }})
df <- read.csv("{csv}", stringsAsFactors = TRUE)
agg <- aggregate(df[["{y}"]], list(g = df[["{x}"]]),
                 function(z) c(m = mean(z), se = sd(z)/sqrt(length(z))))
d <- data.frame(g = agg$g, m = agg$x[,"m"], se = agg$x[,"se"])
p <- ggplot(d, aes(x = g, y = m, fill = g)) +
  geom_col(width = 0.6, alpha = 0.85) +
  geom_errorbar(aes(ymin = m - se, ymax = m + se), width = 0.2) +
  labs(title = "{title}", x = "{x}", y = "{y} (mean ± SE)") + {_THEME}
ggsave("{out}", p, width = 6, height = 5, dpi = 300)
cat("Saved figure: {out}\\n")
'''


def _scatter(csv, x, y, out, title):
    return f'''suppressMessages({{ library(ggplot2) }})
df <- read.csv("{csv}", stringsAsFactors = TRUE)
r <- cor(df[["{x}"]], df[["{y}"]], use = "complete.obs")
p <- ggplot(df, aes(x = {x}, y = {y})) +
  geom_point(size = 2, alpha = 0.7) +
  geom_smooth(method = "lm", se = TRUE, color = "#2c7fb8") +
  labs(title = sprintf("{title} (r = %.2f)", r), x = "{x}", y = "{y}") +
  theme_classic(base_size = 14) + theme(axis.text = element_text(color = "black"))
ggsave("{out}", p, width = 6, height = 5, dpi = 300)
cat("Saved figure: {out}\\n")
'''


def _line(csv, x, y, out, title):
    # dose-response / 시간경과: x 가 연속(용량/시간), 평균±SE 선그래프
    return f'''suppressMessages({{ library(ggplot2) }})
df <- read.csv("{csv}", stringsAsFactors = TRUE)
agg <- aggregate(df[["{y}"]], list(x = df[["{x}"]]),
                 function(z) c(m = mean(z), se = sd(z)/sqrt(length(z))))
d <- data.frame(x = agg$x, m = agg$x.1[,"m"], se = agg$x.1[,"se"])
p <- ggplot(d, aes(x = x, y = m)) +
  geom_line(color = "#2c7fb8") + geom_point(size = 2) +
  geom_errorbar(aes(ymin = m - se, ymax = m + se), width = 0.05) +
  labs(title = "{title}", x = "{x}", y = "{y} (mean ± SE)") +
  theme_classic(base_size = 14) + theme(axis.text = element_text(color = "black"))
ggsave("{out}", p, width = 6, height = 5, dpi = 300)
cat("Saved figure: {out}\\n")
'''


_BUILDERS = {"boxplot": _boxplot, "bar": _barplot, "scatter": _scatter, "line": _line}


def make_figure(csv_path: str, x_col: str, y_col: str, out_dir: str, *,
                kind: str = "boxplot", title: str = "", caption: str = "",
                rscript_path: str = "Rscript") -> dict:
    if kind not in _BUILDERS:
        return {"ok": False, "error": f"알 수 없는 종류: {kind}. 선택: {list(_BUILDERS)}"}
    out_path = str(Path(out_dir) / f"figure_{kind}_{y_col}.png")
    script = _BUILDERS[kind](csv_path, x_col, y_col, out_path, title or f"{y_col} by {x_col}")
    result = run_r(script, out_dir, rscript_path)
    result["figure"] = out_path
    result["caption"] = caption or f"{kind}: {y_col} vs {x_col}"
    result["value"] = y_col
    result["kind"] = kind
    if result.get("ok"):
        _append_manifest(out_dir, {"figure": out_path, "caption": result["caption"],
                                   "value": y_col, "group": x_col, "kind": kind})
    return result


# 하위호환: 기존 boxplot 진입점
def make_boxplot(csv_path: str, group_col: str, value_col: str, out_dir: str,
                 title: str = "", caption: str = "", alpha: float = 0.05,
                 rscript_path: str = "Rscript") -> dict:
    return make_figure(csv_path, group_col, value_col, out_dir, kind="boxplot",
                       title=title, caption=caption, rscript_path=rscript_path)


def _append_manifest(out_dir: str, entry: dict) -> None:
    mp = Path(out_dir) / "figures.json"
    items = []
    if mp.exists():
        try:
            items = json.loads(mp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            items = []
    items = [x for x in items if x.get("figure") != entry["figure"]]  # 재실행 중복 제거
    items.append(entry)
    mp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def load_manifest(out_dir: str) -> list[dict]:
    mp = Path(out_dir) / "figures.json"
    if mp.exists():
        try:
            return json.loads(mp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []
