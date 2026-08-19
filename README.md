# 서울 창업 입지 탐색기 (Seoul Startup Scout)

서울시 상권 공공데이터 7종을 결합해, 비슷한 성격의 상권끼리 비교했을 때
**공급이 부족하면서 폐업률이 안정적인 상권×업종 조합**을 검토 후보로 제시하는
Streamlit 대시보드.

> 계약 정본은 [`DEV_SPEC.md`](DEV_SPEC.md) · 결정 이력은 [`docs/킥오프_회의록.md`](docs/킥오프_회의록.md)

## 설치 및 실행

```bash
# 1. 환경 구성 (uv 필요: https://docs.astral.sh/uv/)
uv sync

# 2. 원본 데이터 배치 — data/raw/README.md 의 8종 CSV 다운로드

# 3. 파이프라인 실행 (각 단계 뒤 검증 스크립트가 완료 판정)
uv run python scripts/build_master.py
uv run python seams/check_master.py      # → OK 확인
uv run python scripts/build_scores.py
uv run python seams/check_scores.py      # → OK 확인

# 4. (선택) 뉴스 수집 — .env.example 을 .env 로 복사 후 API 키 기입
uv run python scripts/collect_news.py

# 5. 대시보드 실행
uv run streamlit run app/main.py
```

## 파이프라인

```
data/raw/ (CSV 8종, cp949)
   → build_master.py   → master.csv   (106,337행 × 77컬럼 · 상권 1,558)
   → build_scores.py   → scores.csv   (후보 3,443건 · 유형 7종 · 업종 11종)
   → collect_news.py   → news.csv     (후보 상권 최근 3개월 경제지 기사)
   → app/main.py       (Streamlit)
```

## 주요 설계

- **유형별 기준선 대비 갭 분석** — 서울 전체 순위는 "번화가가 좋다"는 자명한 결론으로
  수렴하므로, 상권을 7개 유형으로 분류한 뒤 같은 유형 안에서 공급 부족을 탐지
- **유효수요 = 상주+직장+유동 인구의 로그 정규화 균등 가중합** — 직장인구는
  상주·유동과 독립적인 수요 정보(상관 0.23/0.39)
- **안정성 = 행정동 단위 4분기 폐업률** — 개별 상권×업종 폐업률은 분산의 84%가
  노이즈임을 실측으로 확인하고 집계 단위를 상향
- **데이터 품질 자동 검증** — 조 간 인계는 `seams/` 검증 스크립트 통과가 완료 기준

## 저장소 구조

```
├── DEV_SPEC.md            계약 정본 (스키마·지표 정의·결정 기록)
├── CLAUDE.md              AI 협업 규약
├── pyproject.toml         의존성 (uv, 버전 고정) + uv.lock
├── config/업종_whitelist.csv
├── common/                loader(원본 읽기 단일 창구) · viz(폰트·팔레트)
├── scripts/               build_master · build_scores · collect_news
├── seams/                 검증 게이트 2종 (수정 금지)
├── notebooks/             EDA (pandas + seaborn/matplotlib)
├── data/                  mock/(선착수용) · raw/(로컬 보관) · 산출 CSV
└── app/                   Streamlit 대시보드
```

<!-- 4일차: 실행 화면 GIF 삽입 -->

## 데이터 출처·라이선스

서울 열린데이터광장 · 서울시 상권분석서비스 (서울신용보증재단) · 공공누리 1유형
