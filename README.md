# my-phone- — 연구·특허 자동화 도구 모음

이 저장소에는 서로 독립적인 두 개의 파이프라인이 들어 있습니다.

| 프로젝트 | 설명 | 설정 파일 | 실행 |
|---|---|---|---|
| [rpaper](#rpaper--연구-논문-작성-자동화-파이프라인) | 문헌 수집 → Obsidian 위키 → R 통계/figure → 논문 원고 작성 | `config.yaml` | `rpaper ...` |
| [특허 작성 파이프라인](#특허-작성-파이프라인-patent-writing-pipeline) | KIPRIS·논문 선행조사 → 신규성·진보성 판단 → 명세서 초안 → Obsidian 위키 | `patent_config.yaml` | `python -m patent_pipeline ...` |

두 프로젝트 모두 산출물을 Obsidian 위키로 남기며, 같은 vault 를 공유해도 됩니다.

---

# rpaper — 연구 논문 작성 자동화 파이프라인

제목과 키워드(아이템)를 주면 문헌·뉴스를 수집해 **Obsidian 위키**를 만들고,
참고문헌 번호별 요약을 정리한 뒤, **Introduction → Materials & Methods →
Results → Discussion → Conclusion** 순서로 원고 초안을 작성합니다.
raw data 는 **R 기반**으로 통계분석/시각화하고, 저널별 템플릿·가이드라인을
내려받아 형식을 맞춥니다. 모바일/PC/IDE 어디서나 동일한 CLI로 동작합니다.

> ⚠️ 이 저장소는 **동작하는 골격(MVP)** 입니다. 실제로 바로 돌아가는 부분과
> 외부 인증/사양 확인이 필요한 부분을 `docs/STATUS.md` 에 정직하게 정리했습니다.

## 빠른 시작

```bash
pip install -e .                 # 또는: pip install pyyaml requests anthropic
cp config.example.yaml config.yaml   # 키/경로 채우기
rpaper collect                   # PubMed/Scholar/News -> Obsidian 위키 (중복 제거)
rpaper analyze examples/raw.csv group viability     # 정규성 검정 -> 모수/비모수 자동
rpaper figure  examples/raw.csv group viability --type bar  # boxplot|bar|scatter|line
rpaper write intro               # intro|methods|results|discussion|conclusion
rpaper journal                   # 저널 템플릿+가이드라인 다운로드
rpaper assemble                  # 전 섹션 -> Manuscript.md/.docx (저널 템플릿 적용)
rpaper status                    # 진행률·키 설정 점검
rpaper run                       # collect + intro/methods 일괄
```

설정 없이도 핵심 모듈은 표준 라이브러리만으로 동작합니다(요약·LLM·R 은 선택).

## 파이프라인 단계

| 단계 | 명령 | 상태 |
|------|------|------|
| 1. 문헌 수집 (PubMed) | `collect` | ✅ 동작 (NCBI E-utilities) |
| 1. 문헌 수집 (Scholar) | `collect` | ⚙️ SerpAPI 키 필요 (Scholar 직접 수집은 약관 위반) |
| 1. 해외 뉴스 | `collect` | ⚙️ NewsAPI 키 필요 |
| 2. Obsidian 위키 + 번호별 요약 | `collect` | ✅ 동작 (요약은 LLM 키 있으면 고품질) |
| 3. Introduction | `write intro` | ✅ 동작 (LLM 키 권장) |
| 4. Materials & Methods | `write methods` | ✅ 동작 |
| 5. 통계분석 | `analyze` | ✅ R 있으면 정확, 없으면 파이썬 폴백 |
| 6. R figure | `figure` | ✅ R(ggplot2) 필요 |
| 6. figurelabs 연동 | `figure` | ❌ API 사양 확인 필요 (스텁) |
| 7. Results/Discussion/Conclusion | `write` | ✅ 동작 (Conclusion 별도 섹션) |
| 8. 저널 템플릿/가이드라인 | `journal` | ⚙️ URL 입력 시 다운로드 |
| 9. 최종 원고 조립 (.md/.docx) | `assemble` | ✅ pandoc 있으면 .docx, 없으면 .md |

자세한 상태와 다음 작업은 [`docs/STATUS.md`](docs/STATUS.md) 참고.

## 모바일 / PC / Antigravity IDE

- **공통**: 순수 Python CLI + Obsidian 마크다운 vault. vault 폴더를
  iCloud/Dropbox/Obsidian Sync 로 동기화하면 모바일 Obsidian 앱에서 그대로 열림.
- **PC / IDE**: `pip install -e .` 후 `rpaper ...`. Antigravity(또는 VS Code)
  통합 터미널에서 동일하게 실행.
- **모바일에서 실행**: 무거운 단계(수집/통계)는 PC나 클라우드(이 Claude Code
  세션 포함)에서 돌리고, 결과 vault 만 모바일에서 읽고 편집하는 방식을 권장.

---

# 특허 작성 파이프라인 (Patent Writing Pipeline)

KIPRIS와 특허·논문을 기반으로, **내가 떠올린 아이디어가 특허로 출원·등록될 수 있는지**를
검토하고, 신규성·진보성 관점에서 기존 특허와의 차별점을 찾아 **명세서 초안까지 작성**하며,
**모든 과정을 Obsidian 위키로 정리**해 주는 파이프라인입니다.

> ⚠️ 본 도구는 검토를 돕는 보조 자료를 생성합니다. 실제 출원 전에는 변리사 검토가 필요합니다.

## 무엇을 해주나

아이디어 한 문단을 넣으면 다음 7단계를 자동으로 수행합니다.

| 단계 | 내용 | 산출물 |
|---|---|---|
| ① 구조화 | 아이디어를 명칭·기술분야·과제·해결수단·구성요소·검색키워드로 분해 | 아이디어 노트 |
| ② 선행조사 | **KIPRIS** 국내 특허·실용신안 + **OpenAlex** 학술 논문 병렬 검색 | 선행문헌 목록 |
| ③ 스크리닝 | 명칭·초록 기준 관련도 점수화 → 상위 N건 선정, 청구범위 조회 | 점수화된 목록 |
| ④ 정밀 비교 | 각 선행문헌을 구성요소 단위로 대비 (신규성·진보성 위협도) | 선행문헌별 분석 노트 |
| ⑤ 특허성 판단 | 신규성(§29①)·진보성(§29②) 종합 판단 + 등록 전략 | 특허성 판단 노트 |
| ⑥ 명세서 작성 | 차별점을 독립항에 반영한 한국 특허 명세서 초안 | 명세서 초안 노트 |
| ⑦ 위키화 | 위 모든 결과를 위키링크로 연결한 Obsidian 노트로 출력 | MOC + 노트 묶음 |

**빠르되 충분한 검토**를 위해 KIPRIS 검색과 선행문헌 분석을 병렬 처리하고,
KIPRIS·LLM 응답을 캐시해 재실행 속도를 높입니다.

## 설치

```bash
pip install -r requirements.txt
```

필요 패키지: `anthropic`, `httpx`, `PyYAML` (모두 표준 라이브러리 외 최소 의존성).

## 💰 무과금 사용 (Claude Pro/Max 구독자 — 권장)

**유료 API 키 없이**, 이미 구독 중인 Claude Pro/Max 를 그대로 LLM 엔진으로 씁니다.

1. [Claude Code](https://claude.com/claude-code) 설치 후 Pro/Max 계정으로 로그인 (`claude` 실행 → 로그인)
2. 끝. API 키 없이 바로 실행:

```bash
python -m patent_pipeline check     # "Claude Code CLI (추가 과금 없음)" 표시되면 준비 완료
python -m patent_pipeline run --file idea.md
```

`llm_backend: auto`(기본값)는 API 키가 없으면 자동으로 Claude Code CLI 를 사용합니다.
비용 구조: LLM 분석 = **구독 포함(0원)** · 논문 검색(OpenAlex) = **무료** ·
특허 검색(KIPRIS) = 무료 가입 후 기본 무료 (선택사항).

## 설정 (유료 API 를 쓰고 싶은 경우에만)

키는 **환경변수** 또는 `patent_config.yaml`로 설정합니다(환경변수 우선).
rpaper 의 `config.yaml` 과 겹치지 않도록 별도 파일을 사용합니다.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."     # 선택 (설정 시 유료 API 백엔드 사용)
export KIPRIS_SERVICE_KEY="..."           # 선택 (없으면 특허 선행조사 생략)
export OBSIDIAN_VAULT_PATH="$HOME/Obsidian/MyVault"   # 선택
```

또는:

```bash
cp patent_config.example.yaml patent_config.yaml   # 값을 채워 넣기 (git 제외됨)
```

- **Anthropic API 키**(선택): https://console.anthropic.com — 기본 모델 `claude-opus-4-8`
- **KIPRIS Plus 서비스키**(선택): https://plus.kipris.or.kr — REST OpenAPI 신청 후 발급

설정 점검:

```bash
python -m patent_pipeline check
```

## 사용법

```bash
# 키 없이 전체 흐름 미리보기(모의 데이터) — 산출물 형태 확인용
python -m patent_pipeline run --dry-run --file examples/idea_example.md --vault /tmp/demo

# 아이디어를 인자로
python -m patent_pipeline run "접이식 자전거 잠금장치인데, 분절형 링크를 자력으로 결합해..."

# 파일로
python -m patent_pipeline run --file examples/idea_example.md

# Obsidian vault 지정
python -m patent_pipeline run --file idea.md --vault ~/Obsidian/MyVault

# KIPRIS 키 없이 LLM 검토만 (특허·논문 선행조사 생략)
python -m patent_pipeline run --file idea.md --skip-search

# 결과를 JSON으로도 받기
python -m patent_pipeline run --file idea.md --json > result.json
```

> **API 키가 아직 없다면** `--dry-run` 으로 모의 데이터를 써서 7단계가 어떤 노트를
> 만들고 어떻게 연결되는지 먼저 확인할 수 있습니다(실제 분석 아님).

실행이 끝나면 `<vault>/Patents/<날짜 발명명>/` 폴더에 노트가 생성됩니다.
Obsidian에서 그 폴더를 열면 위키링크와 그래프로 연결된 검토 자료를 볼 수 있습니다.

## 생성되는 Obsidian 노트 구조

```
Patents/
  20260619 모듈형 접이식 자전거 잠금장치/
    ├─ ... - 개요 (MOC).md         ← 지도 노트. 모든 노트를 위키링크로 연결
    ├─ ... - 아이디어.md            ← 구조화된 발명 정보 + 검색 키워드
    ├─ 선행문헌 - ....md            ← 선행문헌마다 1개 (초록·청구범위·우리발명과 비교)
    ├─ ... - 특허성 판단.md          ← 신규성·진보성 결론 + 등록 포인트 + 보정 권고
    └─ ... - 명세서 초안.md          ← 청구범위 포함 한국 특허 명세서 초안
```

각 노트의 프론트매터에 `type`, `tags`(예: `특허`, `선행문헌`, `kw/...`), 출원번호 등이 들어가
Obsidian 검색·그래프뷰·Dataview로 나만의 특허 위키를 누적할 수 있습니다.

## 동작 원리(특허성 판단 기준)

- **신규성 (특허법 제29조 제1항)**: 단일 선행문헌이 발명의 *모든* 구성요소를 개시하는지 대비.
  하나라도 미개시 구성이 있으면 신규성 인정 여지.
- **진보성 (특허법 제29조 제2항)**: 가장 가까운 선행문헌(주인용발명) 기준으로,
  복수 문헌 결합의 용이성과 **효과의 현저성**을 함께 판단(사후적 고찰 경계).
- 판단에서 도출된 **차별점(등록 포인트)**을 명세서 작성 단계에서 **독립항 한정**으로 강제 반영하여,
  선행문헌과 구별되는 권리범위를 확보합니다.

## 아키텍처

```
patent_pipeline/
  config.py            설정(환경변수 > yaml > 기본값)
  models.py            데이터 모델(Idea / PriorArt / Assessment / Draft ...)
  llm.py               Anthropic API 백엔드 (JSON 스키마 출력 · 스트리밍)
  llm_claude_code.py   Claude Code CLI 백엔드 (Pro/Max 구독 — 무과금)
  cache.py             파일 캐시 (KIPRIS · LLM 응답 재사용)
  search/kipris.py     KIPRIS Plus REST 클라이언트 (병렬 검색 · XML 파싱)
  search/literature.py OpenAlex 학술 논문 검색 (무료 · 키 불필요)
  mock.py              모의 LLM/KIPRIS (--dry-run 모드)
  analysis/
    intake.py          ① 아이디어 구조화
    prior_art.py       ③④ 스크리닝 · 정밀 비교
    patentability.py   ⑤ 신규성·진보성 판단
  drafting/drafter.py  ⑥ 명세서 초안 작성
  obsidian/vault.py    ⑦ Obsidian 마크다운 출력
  pipeline.py          전체 오케스트레이션
  cli.py               명령행 인터페이스
```

## 한계와 주의

- 생성물은 **AI 보조 자료**입니다. 청구항 표현, 인용 정확성, 법적 판단은 변리사 검토가 필요합니다.
- KIPRIS 검색은 국내 특허·실용신안 위주이고, 논문은 OpenAlex(영문 위주)입니다. 해외 특허는 별도 보강이 필요합니다.
- 비용: **Claude Pro/Max 구독자는 claude-code 백엔드로 추가 과금 없이 사용 가능**합니다.
  Anthropic API 백엔드를 선택한 경우에만 토큰 비용이 발생합니다. OpenAlex 는 무료이며,
  캐시로 재실행 비용/시간을 줄일 수 있습니다.
