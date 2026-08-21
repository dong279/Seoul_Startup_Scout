# CLAUDE.md — 서울 창업 입지 탐색기

서울시 상권 CSV 7종 + 네이버 뉴스로 창업 검토 후보 상권×업종(11종)을 제시하는
Streamlit 대시보드. **계약 정본은 `DEV_SPEC.md`(v8)** — 이 파일과 충돌하면 DEV_SPEC이 우선.

## 강제 규약
- 원본 읽기는 `common/loader.py`의 `load()`만 (cp949 + 코드 컬럼 dtype=str 강제)
- 조인은 코드 컬럼으로만. **영역-상권은 `on="상권_코드"` 단일 키** (분기 컬럼 없음)
- 상권 단위 컬럼(인구·가구)은 조인 후 sum() 금지 — 업종 수만큼 복제되어 있음
- 분위수는 drop_duplicates("상권_코드") 후 계산
- 분기 산술 금지 ("20254" 다음은 "20261") — loader.QUARTERS 인덱스로
- 비율 지표는 분모 0 방어 (loader.safe_ratio 사용)
- 산출 파일은 utf-8-sig
- 유형 7종·**업종 11종**·가중치(인구 1:1:1, 점수 0.6:0.4)는 DEV_SPEC §5 확정값 — 임의 변경 금지
- **갭점수는 유형별 정규화** (`groupby("유형").transform(minmax)`) — v8 확정. 전체 min-max로
  되돌리지 말 것. 이 변경은 게이트에 안 걸리므로 코드만 보고 판단하지 말 것
- 앱은 로직과 UI 분리: 데이터 변환·점수 재계산은 `app/logic.py`, 위젯은 `app/main.py`·`app/views_*.py`

## 앱 구조 (v8)
- `main.py` 는 엔트리 + 모드 4종 라우팅. 화면 본체는 views 파일에 있다
  - `views_c2.py` 화면 ② 업종별 개폐업률 산점도 · ⑥ 역방향
  - `views_c3.py` 화면 ③ 상세 패널 · ④ 상권 뉴스
  - `views_forward.py` 화면 ⑤ 정방향 입지 탐색
- **탭이 아니라 `st.radio` 모드**인 이유: `st.tabs`는 활성 탭을 파이썬이 알 수 없어
  사이드바를 화면별로 제어할 수 없다. 탭으로 되돌리지 말 것

## 뉴스 (v8 — 서울 전역)
- 수집 단위는 **서울 전역**. 검색어 정본은 `scrape_news.SEOUL_FOOD_QUERIES` (12종).
  행정동 단위로 되돌리지 말 것 — 요청 342회로 403 차단을 부르고 정밀도도 절반이었다
- 산출은 `data/seoul_food_news.csv`(요약 포함, 앱이 우선 로드) + `data/news.csv`(요약 제외)
- 컬럼은 `제목·언론사·날짜·링크·요약`. **`상권_코드`·`행정동_base` 없음** — 기사는
  특정 상권 소유가 아니다
- 날짜는 검색 결과가 아니라 **기사 원문 페이지에서** 읽는다. 상대 날짜(`N주 전`) 파싱으로
  되돌리지 말 것 — 그게 수집량을 1/5로 만든 원인이다
- `logic.load_news()` 가 없는 컬럼을 채울 때 **`pd.NA` 금지, 빈 문자열**. NA면 화면에
  `<NA>` 가 그대로 노출된다
- 주력은 `scripts/scrape_news.py`. `collect_news.py` 는 API 백업 — 임의로 바꾸지 말 것

## 검증 (완료 판정 = 이것의 green)
- uv run python seams/check_master.py   # data/master.csv
- uv run python seams/check_scores.py   # data/scores.csv (공급갭>0 후보만 담김)
- uv run python seams/check_news.py     # 뉴스 (인자 없으면 산출 파일을 자동 탐색)
  ⚠️ check_news는 **형식만** 검사한다 (컬럼·기간·도메인·제목·중복).
  기사가 쓸모 있는지는 못 잡으므로 **수집 후 사람이 목록을 눈으로 본다** (DEV_SPEC §4-3d)
- uv run python seams/check_app.py      # app/logic.py 계약 (화면이 아니라 로직)
  mock으로 돌릴 때: `... check_app.py data/mock/scores.csv data/mock/news.csv`

## 금지
- seams/ 검증 스크립트 수정 금지 (검사가 틀렸다고 판단되면 멈추고 사람에게 보고)
  계약이 바뀌어 검사도 바꿔야 하면 **팀장이 전담**한다
- 게이트가 `scripts/` 의 상수를 import 하지 말 것 — 수집기가 틀리면 게이트도 같이 틀린다
- **app/logic.py 에 streamlit import 금지** — 위젯·레이아웃은 main.py·views_*.py 에만
- **common/viz.py 는 B·C조 공유 파일 — 오너 1인만 수정** (다른 조는 요청)
- 자기 조 오너십 밖 파일 수정 금지
- git commit·push 금지 — 커밋·push·머지는 전부 사람이 직접 (에이전트는 파일 수정까지만)
