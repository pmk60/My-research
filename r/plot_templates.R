# rpaper 재사용 R figure 템플릿 (publication-quality, ggplot2)
# 사용: source("r/plot_templates.R") 후 함수 호출, 또는 figures.py 가 동적 생성.
suppressMessages({ library(ggplot2) })

theme_pub <- function(base = 14) {
  theme_classic(base_size = base) +
    theme(legend.position = "none",
          axis.text = element_text(color = "black"))
}

# 그룹 비교 boxplot + jitter
fig_boxplot <- function(df, group, value, title = "") {
  ggplot(df, aes(x = .data[[group]], y = .data[[value]], fill = .data[[group]])) +
    geom_boxplot(outlier.shape = NA, alpha = 0.7) +
    geom_jitter(width = 0.15, size = 1.5, alpha = 0.6) +
    labs(title = title, x = group, y = value) +
    theme_pub()
}

# 평균 ± SE 막대그래프 (유의성 표기는 ggsignif 권장)
fig_barplot <- function(df, group, value, title = "") {
  agg <- aggregate(df[[value]], list(g = df[[group]]),
                   function(x) c(m = mean(x), se = sd(x) / sqrt(length(x))))
  d <- data.frame(g = agg$g, m = agg$x[, "m"], se = agg$x[, "se"])
  ggplot(d, aes(x = g, y = m, fill = g)) +
    geom_col(width = 0.6, alpha = 0.8) +
    geom_errorbar(aes(ymin = m - se, ymax = m + se), width = 0.2) +
    labs(title = title, x = group, y = value) +
    theme_pub()
}
