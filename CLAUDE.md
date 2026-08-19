# CLAUDE.md — 서울 창업 입지 탐색기

서울시 상권 CSV 7종 + 네이버 뉴스 API로 창업 검토 후보 상권×업종(11종)을 제시하는
Streamlit 대시보드. **계약 정본은 `DEV_SPEC.md`** — 이 파일과 충돌하면 DEV_SPEC이 우선.

## 강제 규약
- 원본 읽기는 `common/loader.py`의 `load()`만 (cp949 + 코드 컬럼 dtype=str 강제)
- 조인은 코드 컬럼으로만. **영역-상권은 `on="상권_코드"` 단일 키** (분기 컬럼 없음)
- 상권 단위 컬럼(인구·가구)은 조인 후 sum() 금지 — 업종 수만큼 복제되어 있음
- 분위수는 drop_duplicates("상권_코드") 후 계산
- 분기 산술 금지 ("20254" 다음은 "20261") — loader.QUARTERS 인덱스로
- 비율 지표는 분모 0 방어 (loader.safe_ratio 사용)
- 산출 파일은 utf-8-sig
- 유형 7종·업종 11종·가중치(인구 1:1:1, 점수 0.6:0.4)는 DEV_SPEC §5 확정값 — 임의 변경 금지

## 환경 (uv)
- 실행은 전부 `uv run python ...` 경유. 패키지 추가는 pip 금지 — `uv add`만
  (pyproject.toml + uv.lock 변경을 같은 커밋으로, 사람이 커밋)

## 검증 (완료 판정 = 이것의 green)
- uv run python seams/check_master.py   # data/master.csv
- uv run python seams/check_scores.py   # data/scores.csv (공급갭>0 후보만 담김)

## 금지
- seams/ 검증 스크립트 수정 금지 (검사가 틀렸다고 판단되면 멈추고 사람에게 보고)
- 뉴스 수집 주력은 scripts/scrape_news.py (requests+bs4). collect_news.py는 API 백업 — 임의로 주력/백업을 바꾸지 말 것
- 자기 조 오너십 밖 파일 수정 금지
- git commit·push 금지 — 커밋·push·머지는 전부 사람이 직접 (에이전트는 파일 수정까지만)
