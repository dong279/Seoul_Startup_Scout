# CLAUDE.md — 서울 창업 입지 탐색기

서울시 상권 CSV 7종 + 네이버 뉴스로 창업 검토 후보 상권×업종(11종)을 제시하는
Streamlit 대시보드. **계약 정본은 `DEV_SPEC.md`** — 이 파일과 충돌하면 DEV_SPEC이 우선.

## 강제 규약
- 원본 읽기는 `common/loader.py`의 `load()`만 (cp949 + 코드 컬럼 dtype=str 강제)
- 조인은 코드 컬럼으로만. **영역-상권은 `on="상권_코드"` 단일 키** (분기 컬럼 없음)
- 상권 단위 컬럼(인구·가구)은 조인 후 sum() 금지 — 업종 수만큼 복제되어 있음
- 분위수는 drop_duplicates("상권_코드") 후 계산
- 분기 산술 금지 ("20254" 다음은 "20261") — loader.QUARTERS 인덱스로
- 비율 지표는 분모 0 방어 (loader.safe_ratio 사용)
- 산출 파일은 utf-8-sig
- 유형 7종·**업종 11종**·가중치(인구 1:1:1, 점수 0.6:0.4)는 DEV_SPEC §5 확정값 — 임의 변경 금지
- 앱은 로직과 UI 분리: 데이터 변환·점수 재계산은 `app/logic.py`, 위젯은 `app/main.py`

## 환경 (uv)
- 실행은 전부 `uv run python ...` 경유. 패키지 추가는 pip 금지 — `uv add`만
  (pyproject.toml + uv.lock 변경을 같은 커밋으로, 사람이 커밋)

## 검증 (완료 판정 = 이것의 green)
- uv run python seams/check_master.py   # data/master.csv
- uv run python seams/check_scores.py   # data/scores.csv (공급갭>0 후보만 담김)
- uv run python seams/check_news.py     # data/news.csv (0행이면 red, 일부 상권 미보유는 정상)
  ⚠️ check_news는 **형식만** 검사한다 (제목 길이·도메인·기간·조인 키).
  기사가 쓸모 있는지는 못 잡으므로 **수집 후 사람이 목록을 눈으로 본다** (DEV_SPEC §4-3f)
- uv run python seams/check_app.py      # app/logic.py 계약 (화면이 아니라 로직)

## 금지
- seams/ 검증 스크립트 수정 금지 (검사가 틀렸다고 판단되면 멈추고 사람에게 보고)
- **app/logic.py 에 streamlit import 금지** — 위젯·레이아웃은 app/main.py 에만
- **common/viz.py 는 B·C조 공유 파일 — 오너 1인만 수정** (다른 조는 요청)
- 뉴스 수집 주력은 scripts/scrape_news.py (requests+bs4). collect_news.py는 API 백업 —
  주력/백업을 임의로 바꾸지 말 것 (전환은 확보 기사 5건 미달 시 코드가 자동으로 한다)
- **뉴스 검색 단위는 서울 전체 · 외식/창업 주제 8종** (DEV_SPEC §4-3a). `행정동_base`에는
  행정동명이 아니라 수집 주제가 들어간다. 행정동 단위로 되돌리지 말 것 — 요청 342회로
  403 차단을 부르고 정밀도도 절반이었다
- 뉴스 필터 사전(STARTUP/FOOD/NOISE/OTHER_REGION)을 조인 뒤에는 **확보 기사 수가
  MIN_ARTICLES 아래로 떨어지지 않았는지 확인** — 정밀도와 확보량은 맞바꾸는 관계다
- 자기 조 오너십 밖 파일 수정 금지
- git commit·push 금지 — 커밋·push·머지는 전부 사람이 직접 (에이전트는 파일 수정까지만)
