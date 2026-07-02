#!/usr/bin/env bash
# rpaper 환경 설정 — PC/IDE 공통. (모바일은 README 의 "모바일" 항목 참고)
set -e
echo "[1/3] Python 패키지 설치"
pip install -e . || pip install pyyaml requests anthropic

echo "[2/3] config.yaml 준비"
if [ ! -f config.yaml ]; then
  cp config.example.yaml config.yaml
  echo "  -> config.yaml 생성됨. 키/경로를 채우세요."
else
  echo "  -> config.yaml 이미 존재."
fi

echo "[3/3] R 패키지(선택) — figure/정확 통계용"
if command -v Rscript >/dev/null 2>&1; then
  Rscript -e 'pkgs<-c("ggplot2","ggsignif"); for(p in pkgs) if(!requireNamespace(p,quietly=TRUE)) install.packages(p, repos="https://cloud.r-project.org")' || true
else
  echo "  -> R 미설치. figure/정확 p값이 필요하면 R 설치 권장 (없어도 파이프라인은 동작)."
fi
echo "완료. 'rpaper status' 로 현황을 확인하세요."
