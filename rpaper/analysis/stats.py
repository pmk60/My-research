"""Raw data 정리 + 통계분석.

사용자가 도표/그래프를 R 기반으로 원하므로, 통계와 시각화를 모두 R 스크립트로
생성하고 Rscript 로 실행합니다. R 미설치 시 순수 파이썬 폴백으로 유의성만 점검합니다.
"""
from __future__ import annotations

import csv
import math
import shutil
import subprocess
from pathlib import Path
from statistics import mean, stdev


def load_csv(path: str | Path) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return (reader.fieldnames or []), rows


def r_available(rscript_path: str = "Rscript") -> bool:
    return shutil.which(rscript_path) is not None


def welch_t_python(a: list[float], b: list[float]) -> dict:
    """R 미설치 시 폴백: Welch's t-test (양측). p 값은 정규근사 추정치."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return {"error": "각 그룹에 최소 2개 표본 필요"}
    ma, mb = mean(a), mean(b)
    va, vb = stdev(a) ** 2, stdev(b) ** 2
    se = math.sqrt(va / na + vb / nb)
    if se == 0:
        return {"error": "분산이 0"}
    t = (ma - mb) / se
    # 정규근사 양측 p (df 큰 경우 근사). 정확값은 R 사용 권장.
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
    return {"mean_a": ma, "mean_b": mb, "t": t, "p_approx": p}


def generate_r_script(csv_path: str, group_col: str, value_col: str,
                      out_dir: str, alpha: float = 0.05) -> str:
    """그룹 비교(2그룹 t-test / 3+그룹 ANOVA+Tukey)와 정확 p 값을 계산하는 R 스크립트.

    콘솔 출력에 더해 out_dir/stats.json 에 구조화된 결과를 기록하여
    Results 섹션 작성에 그대로 사용합니다(jsonlite 불필요, 수동 직렬화).
    """
    return f'''# rpaper 자동 생성 통계 스크립트 (정규성 검정 -> 모수/비모수 자동 선택)
suppressMessages({{ library(stats) }})
df <- read.csv("{csv_path}", stringsAsFactors = TRUE)
g <- "{group_col}"; v <- "{value_col}"
df <- df[!is.na(df[[v]]), ]
groups <- levels(droplevels(df[[g]]))
means <- tapply(df[[v]], df[[g]], mean)
cat("Groups:", paste(groups, collapse=", "), "\\n")

# 그룹별 정규성(Shapiro-Wilk, n>=3). 하나라도 비정규면 비모수 검정 사용.
normal <- TRUE
for (grp in groups) {{
  x <- df[[v]][df[[g]] == grp]
  if (length(x) >= 3 && length(x) <= 5000) {{
    pw <- tryCatch(shapiro.test(x)$p.value, error = function(e) 1)
    cat(sprintf("Shapiro %s: p=%.4f\\n", grp, pw))
    if (!is.na(pw) && pw < 0.05) normal <- FALSE
  }}
}}

# IQR 기반 이상치 개수
out_n <- 0
for (grp in groups) {{
  x <- df[[v]][df[[g]] == grp]; qs <- quantile(x, c(.25, .75)); iqr <- diff(qs)
  out_n <- out_n + sum(x < qs[1] - 1.5*iqr | x > qs[2] + 1.5*iqr)
}}

if (length(groups) == 2) {{
  if (normal) {{
    res <- t.test(df[[v]] ~ df[[g]]); test <- "Welch two-sample t-test"
    stat <- unname(res$statistic); pval <- res$p.value
  }} else {{
    res <- wilcox.test(df[[v]] ~ df[[g]]); test <- "Mann-Whitney U test (non-parametric)"
    stat <- unname(res$statistic); pval <- res$p.value
  }}
}} else {{
  if (normal) {{
    fit <- aov(df[[v]] ~ df[[g]]); s <- summary(fit)[[1]]
    pval <- s[["Pr(>F)"]][1]; stat <- s[["F value"]][1]; test <- "One-way ANOVA"
    print(TukeyHSD(fit))
  }} else {{
    res <- kruskal.test(df[[v]] ~ df[[g]]); test <- "Kruskal-Wallis test (non-parametric)"
    stat <- unname(res$statistic); pval <- res$p.value
    print(pairwise.wilcox.test(df[[v]], df[[g]], p.adjust.method = "BH"))
  }}
}}
sig <- pval < {alpha}
cat(sprintf("Test: %s\\nstatistic=%.4f, p=%.6f\\n", test, stat, pval))
cat(sprintf("Normal: %s | Outliers(IQR): %d | Significant(alpha={alpha}): %s\\n", normal, out_n, sig))
mean_str <- paste(sprintf('"%s": %.4f', names(means), means), collapse=", ")
json <- sprintf('{{"value": "%s", "group": "%s", "test": "%s", "statistic": %.6f, "p_value": %.8g, "alpha": %s, "significant": %s, "normal": %s, "outliers": %d, "means": {{%s}}}}',
                v, g, test, stat, pval, {alpha}, tolower(as.character(sig)),
                tolower(as.character(normal)), out_n, mean_str)
writeLines(json, file.path("{out_dir}", "stats.json"))
saveRDS(df, file.path("{out_dir}", "data.rds"))
'''


def run_r(script: str, out_dir: str, rscript_path: str = "Rscript") -> dict:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    sp = Path(out_dir) / "analysis.R"
    sp.write_text(script, encoding="utf-8")
    if not r_available(rscript_path):
        return {"ok": False, "error": "R(Rscript) 미설치. 폴백 또는 R 설치 필요.",
                "script": str(sp)}
    proc = subprocess.run([rscript_path, str(sp)], capture_output=True, text=True)
    return {"ok": proc.returncode == 0, "stdout": proc.stdout,
            "stderr": proc.stderr, "script": str(sp)}


def analyze(csv_path: str, group_col: str, value_col: str, out_dir: str,
            alpha: float = 0.05, rscript_path: str = "Rscript") -> dict:
    """그룹 비교 통계. R 우선, 미설치 시 파이썬 폴백. 항상 동일 스키마 반환.

    반환: {engine, value, group, test, statistic, p_value, alpha, significant, means, ...}
    """
    import json
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    script = generate_r_script(csv_path, group_col, value_col, out_dir, alpha)
    r = run_r(script, out_dir, rscript_path)
    sj = Path(out_dir) / "stats.json"
    if r.get("ok") and sj.exists():
        result = json.loads(sj.read_text(encoding="utf-8"))
        result["engine"] = "R"
        result["stdout"] = r.get("stdout", "")
        return result

    # 폴백: 파이썬 (2그룹 Welch t-test). p 값은 정규근사.
    _, rows = load_csv(csv_path)
    groups: dict[str, list[float]] = {}
    for row in rows:
        try:
            groups.setdefault(row[group_col], []).append(float(row[value_col]))
        except (KeyError, ValueError):
            continue
    means = {k: (sum(v) / len(v) if v else 0.0) for k, v in groups.items()}
    if len(groups) == 2:
        a, b = list(groups.values())
        t = welch_t_python(a, b)
        if "error" in t:
            return {"engine": "python", "error": t["error"], "means": means}
        return {"engine": "python", "value": value_col, "group": group_col,
                "test": "Welch two-sample t-test (정규근사 p)", "statistic": t["t"],
                "p_value": t["p_approx"], "alpha": alpha,
                "significant": t["p_approx"] < alpha, "means": means,
                "note": "정확한 p 값은 R 설치 후 재실행 권장"}
    return {"engine": "python", "value": value_col, "group": group_col,
            "test": "3그룹+ 비교는 R(ANOVA) 필요", "means": means,
            "error": "R 미설치 — 3그룹 이상은 R 설치 후 실행"}
