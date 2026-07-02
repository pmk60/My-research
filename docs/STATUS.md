# 구현 상태 및 다음 작업 (정직한 현황)

## 🗓️ 화요일 아침 체크리스트 — 당신이 추가할 것만

코드/구조/연동은 완료돼 있습니다. 아래 **5가지(키·경로)만** 채우면 즉시 돌아갑니다.

1. `cp config.example.yaml config.yaml` 후 `config.yaml` 편집:
   - `project.obsidian_vault`: **기존 Obsidian vault 루트 경로** (이 안에 프로젝트 폴더가 자동 생성됨)
   - `project.title`, `project.keywords`: 이번 논문 주제/아이템
   - `llm.api_key` (또는 환경변수 `ANTHROPIC_API_KEY`): 요약·원고용 — **품질 핵심**
   - `pubmed.api_key`(선택), `scholar.serpapi_key`(Scholar 원하면), `news.newsapi_key`(뉴스 원하면)
2. (선택) `bash scripts/setup.sh` 로 R/ggplot2 설치 — figure·정확 p값용
3. 실행: `rpaper run` → `rpaper analyze data.csv group value` → `rpaper figure ...` →
   `rpaper write results` → `rpaper write discussion` → `rpaper status` 로 확인

> 위 키들 외에 **당신이 직접 줘야 하는 것**: ① raw data CSV ② 저널 정할 때 template/guideline URL
> ③ figurelabs API 문서/키(있다면) — 이건 외부 사양이라 제가 임의로 못 만듭니다.



요청하신 전체 워크플로우를 모듈로 나눠 골격을 만들었습니다. 아래는 각 부분이
**지금 실제로 되는지 / 무엇이 더 필요한지** 입니다.

## ✅ 지금 바로 동작 (검증 완료, 10개 단위테스트 통과)

- **기존 Obsidian vault 연동** (`knowledge/obsidian.py`): vault 루트를 지정하면 그 안에
  **프로젝트 전용 폴더**를 만들어 모읍니다. 기존 노트는 건드리지 않음(테스트로 검증).
  인용 wikilink 는 경로까지 명시(`[[folder/References/Ref-001|1]]`)해 다른 프로젝트와 충돌 없음.
  `00-Index.md`(MOC) + `References/Ref-NNN.md`(번호별 요약·abstract·Vancouver 인용·블록앵커)
  + `Bibliography.md`(번호순 전체) + `News/` + `Manuscript/`.
- **BibTeX 내보내기** (`knowledge/citations.py`): `.rpaper/references.bib` — Zotero/저널 호환.
- **PubMed 수집** (`collectors/pubmed.py`): NCBI E-utilities 공개 API, 표준 라이브러리만.
  *외부 네트워크 허용 환경에서만* (이 클라우드 세션은 정책상 403, 본인 PC/모바일은 정상).
- **통계분석** (`analysis/stats.py`): `analyze()` 가 R 우선·파이썬 폴백을 동일 스키마로 반환.
  2그룹 t-test / 3그룹+ ANOVA+Tukey, 결과를 `stats.json` 으로 구조화 저장.
- **R figure** (`analysis/figures.py`): ggplot2 boxplot + 2그룹 유의성 막대(ggsignif),
  `figures.json` 매니페스트 누적(재실행 시 중복 제거).
- **통계 정밀화**: Shapiro-Wilk 정규성 검정으로 **모수(t-test/ANOVA) ↔ 비모수
  (Mann-Whitney/Kruskal-Wallis) 자동 선택**, IQR 이상치 개수 보고.
- **Figure 4종**: boxplot/bar(평균±SE)/scatter(상관)/line(dose-response) — `--type` 선택.
- **참고문헌 중복 제거**: DOI·정규화 제목 기준(PubMed+Scholar 겹침 대비).
- **원고 섹션 작성** (`manuscript/sections.py`): Intro/Methods/Results/Discussion/**Conclusion(별도)**.
  Results 는 analyze/figure 산출물 자동 반영. LLM 키 없으면 골격 반환.
- **최종 원고 조립** (`manuscript/assemble.py`): 전 섹션을 `Manuscript.md` 로 합치고,
  pandoc 이 있으면 저널 템플릿(.docx)을 `--reference-doc` 으로 적용해 `Manuscript.docx` 생성.
- **CLI** (`cli.py`): `collect/analyze/figure/write/journal/assemble/status/run`. 네트워크 차단·R·
  pandoc·LLM 미설정에서도 죽지 않고 폴백. `status` 로 진행률·키 설정 한눈에 점검.
- **CI**: `.github/workflows/ci.yml` 에서 PR마다 pytest 자동 실행.

## ⚙️ 키/설정만 넣으면 동작

- **Google Scholar**: 공식 API 없음 + 직접 스크래핑은 약관 위반·차단 위험.
  → **SerpAPI(유료) google_scholar 엔진** 권장. `config.scholar.serpapi_key` 입력 시 동작.
- **해외 뉴스**: `config.news.newsapi_key`(NewsAPI.org) 입력 시 동작.
- **LLM 요약·원고**: `ANTHROPIC_API_KEY` 또는 `config.llm.api_key`. 모델 기본값 `claude-fable-5`.
- **저널 템플릿/가이드라인**: `config.journal.template_url` + `guidelines_url` 입력 시 다운로드.
  많은 저널이 로그인/동적 페이지라 URL 확인 필요 — 안 되면 수동 다운로드 후 경로 지정.

## ❌ 외부 사양 확인이 필요 (현재 스텁)

- **figurelabs 연동** (`integrations/figurelabs.py`): figurelabs 의 공개 REST API 나
  MCP 제공 여부, 인증 방식을 확인하지 못했습니다. 계정(pmk601313@knu.ac.kr)만으로는
  프로그램 연동이 안 되고, **API 키 + 엔드포인트 문서**가 필요합니다.
  - 확인해 주실 것: ① figurelabs 가 API/MCP 를 제공하는지 ② 키 발급 위치
  - 그때까지는 **R(ggplot2) 로컬 생성 figure** 를 사용하시면 됩니다(논문 품질 충분).

## 🔌 MCP / API 키 연동 권고 (유료 계정 활용)

| 용도 | 권장 | 비고 |
|------|------|------|
| 논문 요약·원고 | Anthropic API (Claude) | 이미 코드 연동됨, 키만 |
| Scholar | SerpAPI | 합법적·안정적 |
| 뉴스 | NewsAPI | 무료티어도 가능 |
| 노트 동기화(대안) | Notion MCP | Obsidian 대신/병행 가능 (이 세션에 Notion MCP 있음) |
| 문헌 PDF 관리 | Zotero API | 향후 추가 후보 |

## 다음 우선순위

1. `config.yaml` 에 NCBI/SerpAPI/NewsAPI/Anthropic 키 입력 후 본인 환경에서 `rpaper collect` 검증
2. figurelabs API 문서/키 확보 → `figurelabs.py` 의 `create_figure`/`upload_figure` 구현
3. R 설치 후 `analyze`/`figure` 정확값 검증
4. 자주 쓰는 저널의 template/guideline URL 수집 → `journal` 자동화 강화
5. Results 작성 시 analyze/figure 결과를 자동으로 받아오도록 캐시 연결 (현재 일부 수동)
