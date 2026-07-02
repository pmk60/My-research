#!/bin/bash
# rpaper 의존성 설치 — Claude Code on the web 세션에서 테스트가 바로 동작하도록.
set -euo pipefail

# 원격(웹) 세션에서만 실행. 로컬은 사용자의 기존 환경을 건드리지 않음.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# --- 1) Python 의존성 ---
# pip 업그레이드는 환경에 따라 막힐 수 있으므로 실패해도 무시(필수 아님).
python -m pip install --upgrade pip || true
pip install -e .      # rpaper + 런타임 의존성(pyyaml, requests, anthropic)
pip install pytest    # 테스트 러너

# --- 2) R 도구 (그래프/figure 기본 엔진) ---
# rpaper 는 모든 그래프/figure 를 R(ggplot2) 로 그리는 것을 기본으로 합니다.
# R 이 없으면 figure 가 생성되지 않으므로 웹 세션에 R + ggplot2 + ggsignif 를 깝니다.
# 전부 best-effort(실패해도 세션은 시작). 첫 세션 이후 컨테이너 캐시로 재설치 안 함.
if ! command -v Rscript >/dev/null 2>&1; then
  SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"
  $SUDO apt-get update -qq || true
  # Ubuntu 패키지가 CRAN 컴파일보다 빠르고 안정적
  $SUDO apt-get install -y -qq r-base-core r-cran-ggplot2 r-cran-ggsignif || true
fi
if command -v Rscript >/dev/null 2>&1; then
  echo "R: $(Rscript --version 2>&1 | head -1)"
else
  echo "참고: R 설치 실패 — figure 는 R 설치된 환경에서 생성됩니다(통계는 파이썬 폴백 동작)."
fi

echo "rpaper 의존성 설치 완료."
