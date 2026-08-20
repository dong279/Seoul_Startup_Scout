# 서울 창업 입지 탐색기 (Seoul Startup Scout)

서울시 상권 공공데이터 7종을 결합해, 비슷한 성격의 상권끼리 비교했을 때
**공급이 부족하면서 폐업률이 안정적인 상권×업종 조합**을 검토 후보로 제시하는
Streamlit 대시보드.

분석 대상은 생활밀접 **외식·식음료 11종**(한식·중식·일식·양식음식점, 분식전문점,
패스트푸드점, 치킨전문점, 호프-간이주점, 제과점, 커피-음료, 반찬가게)이며,
공급밀도·폐업률·업종 추이 등 **모든 지표를 이 11종 범위 안에서 계산**한다.

> 계약 정본은 [`DEV_SPEC.md`](DEV_SPEC.md) · 결정 이력은 [`docs/킥오프_회의록.md`](docs/킥오프_회의록.md)

## 설치 및 실행

```bash
# 1. 환경 구성 (uv 필요: https://docs.astral.sh/uv/)
uv sync

# 2. 원본 데이터 배치 — data/raw/README.md 의 CSV 7종 다운로드 (cp949)

# 3. 파이프라인 실행 (각 단계 뒤 검증 스크립트가 완료 판정)
uv run python scripts/build_master.py
uv run python seams/check_master.py      # → OK 확인
uv run python scripts/build_scores.py
uv run python seams/check_scores.py      # → OK 확인

# 4. 뉴스 수집 (requests + BeautifulSoup)
uv run python scripts/scrape_news.py
uv run python seams/check_news.py        # → OK 확인
#    확보 지역 20개 미만이면 검색 API 백업 경로로 자동 전환 (.env 에 키 필요)

# 5. 참고 지표 (선택 — 없으면 상세 패널의 해당 영역만 비워진다)
uv run python scripts/build_trend.py

# 6. 앱 로직 계약 검증 + 대시보드 실행
uv run python seams/check_app.py         # → OK 확인
uv run streamlit run app/main.py
```

원본 데이터가 아직 없을 때는 계약과 동일한 형태의 가데이터로 앱을 먼저 띄울 수 있다:

```bash
uv run python scripts/make_mock.py
uv run python seams/check_app.py data/mock/scores.csv data/mock/news.csv
```

## 파이프라인

```
data/raw/ (CSV 7종, cp949)
   → build_master.py   → master.csv          (106,337행 × 77컬럼 · 상권 1,558 · 업종 62)
   → build_scores.py   → scores.csv          (후보 3,443건 · 유형 7종 · 업종 11종 · 상권 1,339)
   → scrape_news.py    → news.csv            (후보 상권 최근 3개월 경제지 기사, bs4)
   → build_trend.py    → industry_trend.csv  (업종 11종 × 5분기 = 55행, 참고 표시용)
   → app/main.py       (Streamlit)
```

`master.csv`가 62종인 것은 필터 누락이 아니라 의도다 — **결합 테이블은 원천으로 두고,
업종 한정은 소비 단계에서 적용**한다. 62종을 남겨두는 이유는 "62종 중 왜 이 11종인가"의
대조 근거가 필요하기 때문이며, 그 대조 분석 외에는 어떤 집계도 62종으로 돌리지 않는다
(`DEV_SPEC.md` 아티팩트 1의 소비 규약).

## 주요 설계

- **유형별 기준선 대비 갭 분석** — 서울 전체 순위는 "번화가가 좋다"는 자명한 결론으로
  수렴하므로, 상권을 7개 유형으로 분류한 뒤 같은 유형 안에서 공급 부족을 탐지
- **유효수요 = 상주+직장+유동 인구의 로그 정규화 균등 가중합** — 직장인구는
  상주·유동과 독립적인 수요 정보(상관 0.23/0.39). 로그 없이는 스케일 차이(404배)로
  직장인구가 지표에서 사라진다
- **안정성 = 행정동 × 외식 11종의 4분기 폐업률** — 개별 상권×업종 폐업률은 분산의 84%가
  노이즈임을 실측으로 확인하고 집계 단위를 행정동으로 상향했고, 집계 대상 업종은 분석
  대상과 일치시켰다. "이 지역에서 **외식업이** 얼마나 버티는가"를 재는 지표다
- **가중치는 팀이 아니라 사용자가 정한다** — 갭·안정성 슬라이더 2종(기본 0.6:0.4).
  팀이 고정하면 "왜 그 숫자인가"에 답이 없다
- **데이터 품질 자동 검증** — 조 간 인계는 `seams/` 검증 스크립트 통과가 완료 기준.
  산문 보고가 아니라 게이트 출력이 완료의 증거다

## 저장소 구조

```
├── DEV_SPEC.md            계약 정본 (스키마·지표 정의·미해결 레지스터·결정 기록)
├── CLAUDE.md              AI 협업 규약
├── pyproject.toml         의존성 (uv, 버전 고정) + uv.lock
├── config/업종_whitelist.csv   분석 업종 11종 (모든 지표 계산의 적용 대상)
├── common/                loader(원본 읽기 단일 창구) · viz(폰트·팔레트)
├── scripts/               build_master · build_scores · build_trend
│                          scrape_news(주력) · collect_news(백업) · news_filter(공유 필터)
│                          make_mock(가데이터 생성)
├── seams/                 검증 게이트 4종 — master · scores · news · app (수정은 팀장 전담)
├── notebooks/             EDA (pandas + seaborn/matplotlib)
├── data/                  mock/(선착수용) · raw/(로컬 보관) · 산출 CSV
└── app/                   logic.py(순수 로직, streamlit 비의존) · main.py(위젯·레이아웃)
```

<!-- 4일차: 실행 화면 GIF 삽입 -->

## 데이터 출처·라이선스

서울 열린데이터광장 · 서울시 상권분석서비스 (서울신용보증재단) · 공공누리 1유형
