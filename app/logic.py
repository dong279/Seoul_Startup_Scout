"""app/logic.py — 대시보드 로직 (Streamlit 비의존 · C조 오너)

**이 파일에 streamlit을 import하지 않는다.** 위젯·레이아웃은 `app/main.py`,
데이터 변환·점수 재계산·필터는 전부 여기다. 분리 이유는 하나 —
`seams/check_app.py`가 이 함수들을 직접 호출해 계약 준수를 기계 검사할 수 있게
하기 위해서다. UI에 로직이 섞이면 에이전트 산출물의 수용 기준을
"화면이 잘 뜨면"으로밖에 쓸 수 없다.

계약: DEV_SPEC §4 아티팩트 2·3, §5-6 종합점수
"""
from __future__ import annotations

import pandas as pd

# 아래 PATH는 mock(임의 데이터, 예시 데이터)에 대한 경로이다. 데이터 작업이 완료되면 경로를 변경한다.
SCORES_PATH = "data/mock/scores.csv"
NEWS_PATH = "data/mock/news.csv"
MASTER_PATH = "data/mock/master.csv"
CITY_STORE_PATH = "data/mock/city_store.csv"
TREND_PATH = "data/industry_trend.csv"
LATEST_QUARTER = "20261"     # 상세 패널용 master.csv 최신 분기


STR_COLS = ["상권_코드", "상권_코드_명", "서비스_업종_코드", "서비스_업종_코드_명",
            "상권_구분_코드_명", "유형", "자치구_코드_명", "행정동_코드", "행정동_코드_명"]
NEWS_COLS = ["상권_코드", "행정동_base", "제목", "언론사", "날짜", "링크"]
TREND_COLS = ["서비스_업종_코드_명", "기준_년분기_코드", "개업률", "폐업률"]

W_GAP_DEFAULT = 0.6      # DEV_SPEC §5-6 확정 기본값
W_STAB_DEFAULT = 0.4


# ── 로드 ──────────────────────────────────────────────────────────────
def load_scores(path: str = SCORES_PATH) -> pd.DataFrame:
    """후보 테이블. 이미 공급갭 > 0 인 행만 담겨 있으므로 별도 필터하지 않는다."""
    return pd.read_csv(path, encoding="utf-8-sig",
                       dtype={c: str for c in STR_COLS})


def load_trend(path: str = TREND_PATH) -> pd.DataFrame:
    """아티팩트 5 — 업종별 서울시 전체 개·폐업률 추이 (참고 표시용).

    **파일이 없어도 예외를 던지지 않는다.** 점수 계산에 들어가지 않는 참고 지표이므로,
    미산출은 앱 장애가 아니라 해당 영역만 비는 상태다.
    """
    try:
        df = pd.read_csv(path, encoding="utf-8-sig",
                         dtype={"서비스_업종_코드_명": str, "기준_년분기_코드": str})
    except FileNotFoundError:
        return pd.DataFrame(columns=TREND_COLS)
    for c in TREND_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    return df.sort_values("기준_년분기_코드")


def load_news(path: str = NEWS_PATH) -> pd.DataFrame:
    """뉴스 테이블. **파일이 없어도 예외를 던지지 않는다** —
    뉴스는 보조 데이터이고, 미수집은 정상 상태이지 앱 장애가 아니다."""
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    except FileNotFoundError:
        return pd.DataFrame(columns=NEWS_COLS)
    for c in NEWS_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    return df

def load_master(path: str = MASTER_PATH) -> pd.DataFrame:
    """상세 패널에 필요한 연령·요일별 매출 데이터를 불러온다."""
    return pd.read_csv(
        path,
        encoding="utf-8-sig",
        dtype={
            "기준_년분기_코드": str,
            "상권_코드": str,
            "서비스_업종_코드": str,
            "행정동_코드": str,
        },
    )

def load_city_store(path: str = CITY_STORE_PATH) -> pd.DataFrame:
    """서울시 업종별 개·폐업률 추이 데이터를 불러온다."""
    return pd.read_csv(
        path,
        encoding="utf-8-sig",
        dtype={
            "기준_년분기_코드": str,
            "서비스_업종_코드": str,
        },
    )

# ── 점수 재계산 ───────────────────────────────────────────────────────
def rescore(df: pd.DataFrame,
            w_gap: float = W_GAP_DEFAULT,
            w_stab: float = W_STAB_DEFAULT) -> pd.DataFrame:
    """슬라이더 가중치로 종합점수만 다시 계산한다.

    갭점수·안정성점수는 scores.csv에 이미 0~1로 정규화되어 있으므로
    여기서는 가중합만 한다 (재정규화 금지 — 필터 결과에 따라 순위가
    흔들리면 "조건을 좁혔더니 순위가 뒤집힌다"는 설명 불가 현상이 생긴다).

    두 슬라이더 합이 1이 아니어도 되도록 내부에서 비율로 환산한다.
    """
    total = w_gap + w_stab
    if total <= 0:                      # 둘 다 0으로 내린 경우 방어
        w_gap, w_stab, total = W_GAP_DEFAULT, W_STAB_DEFAULT, 1.0
    g, s = w_gap / total, w_stab / total

    out = df.copy()
    out["종합점수"] = g * out["갭점수"] + s * out["안정성점수"]
    return out.sort_values("종합점수", ascending=False, kind="mergesort")


# ── 필터 ──────────────────────────────────────────────────────────────
def filter_candidates(df: pd.DataFrame,
                      업종: list[str] | None = None,
                      유형: list[str] | None = None,
                      자치구: list[str] | None = None) -> pd.DataFrame:
    """사이드바 조건 적용. None 또는 빈 리스트는 '전체'를 뜻한다."""
    out = df
    if 업종:
        out = out[out["서비스_업종_코드_명"].isin(업종)]
    if 유형:
        out = out[out["유형"].isin(유형)]
    if 자치구:
        out = out[out["자치구_코드_명"].isin(자치구)]
    return out


def summary(df: pd.DataFrame) -> dict:
    """상단 요약 지표. 빈 결과에서도 예외 없이 0을 돌려준다."""
    if df.empty:
        return {"후보_수": 0, "평균_종합점수": 0.0,
                "상권_수": 0, "평균_공급갭": 0.0}
    return {
        "후보_수": int(len(df)),
        "평균_종합점수": float(df["종합점수"].mean()),
        "상권_수": int(df["상권_코드"].nunique()),
        "평균_공급갭": float(df["공급갭"].mean()),
    }

# ── 상세 패널 ─────────────────────────────────────────────────────────
def detail_for(scores: pd.DataFrame,
               master: pd.DataFrame,
               상권_코드: str,
               서비스_업종_코드: str) -> dict:
    """③ 상세 패널용 데이터 조회."""

    score = scores[
        (scores["상권_코드"] == 상권_코드) &
        (scores["서비스_업종_코드"] == 서비스_업종_코드)
    ]

    latest = master[
        master["기준_년분기_코드"] == LATEST_QUARTER
    ]

    detail = latest[
        (latest["상권_코드"] == 상권_코드) &
        (latest["서비스_업종_코드"] == 서비스_업종_코드)
    ]

    if score.empty or detail.empty:
        return {}

    s = score.iloc[0]
    d = detail.iloc[0]

    연령_구성 = pd.DataFrame({
        "연령대": [
            "10대", "20대", "30대",
            "40대", "50대", "60대 이상"
        ],
        "상주인구": [
            d["연령대_10_상주인구_수"],
            d["연령대_20_상주인구_수"],
            d["연령대_30_상주인구_수"],
            d["연령대_40_상주인구_수"],
            d["연령대_50_상주인구_수"],
            d["연령대_60_이상_상주인구_수"],
        ],
    })

    요일별_매출 = pd.DataFrame({
        "요일": ["월", "화", "수", "목", "금", "토", "일"],
        "매출금액": [
            d["월요일_매출_금액"],
            d["화요일_매출_금액"],
            d["수요일_매출_금액"],
            d["목요일_매출_금액"],
            d["금요일_매출_금액"],
            d["토요일_매출_금액"],
            d["일요일_매출_금액"],
        ],
    })

    return {
        "상권명": s["상권_코드_명"],
        "업종": s["서비스_업종_코드_명"],
        "유형": s["유형"],

        "공급밀도": float(s["공급밀도"]),
        "동일유형_중앙_공급밀도":
            float(s["동일유형_중앙_공급밀도"]),

        "행정동_폐업률":
            float(s["행정동_폐업률"]),

        "당월_매출_금액":
            int(s["당월_매출_금액"]),
        "당월_매출_건수":
            int(s["당월_매출_건수"]),

        "연령_구성": 연령_구성,
        "요일별_매출": 요일별_매출,
    }

def city_trend_for(city_store: pd.DataFrame,
                   서비스_업종_코드: str) -> pd.DataFrame:
    """③ 상세 패널 — 선택 업종의 서울시 전체 개·폐업률 추이."""
    return (
        city_store[
            city_store["서비스_업종_코드"] == 서비스_업종_코드
        ]
        .sort_values("기준_년분기_코드")
        [["기준_년분기_코드", "개업_율", "폐업_률"]]
        .reset_index(drop=True)
    )

def news_for(news: pd.DataFrame, 상권_코드: str, n: int = 3) -> pd.DataFrame:
    """해당 상권 기사. **없으면 빈 DataFrame** — 호출부는 이를 정상 상태로
    처리하고 '최근 3개월 관련 기사 없음'을 표시한다 (버그가 아니다)."""
    if news.empty:
        return news
    return news[news["상권_코드"] == 상권_코드].sort_values(
        "날짜", ascending=False).head(n)


<<<<<<< HEAD
# ── 역방향 탐색 ───────────────────────────────────────────────────────
=======
def trend_for(trend: pd.DataFrame, 업종명: str) -> pd.DataFrame:
    """해당 업종의 분기별 추이. **없으면 빈 DataFrame** — 호출부는 이를 정상 상태로
    처리하고 '추이 데이터 없음'을 표시한다.

    업종명 표기가 화이트리스트와 다르면 조용히 빈 결과가 되므로,
    빈 결과가 계속 나오면 표기 불일치를 먼저 의심한다.
    """
    if trend.empty:
        return trend
    return trend[trend["서비스_업종_코드_명"] == 업종명]


>>>>>>> origin/main
def reverse_lookup(df: pd.DataFrame, 상권_코드: str, n: int = 5) -> pd.DataFrame:
    """④ 역방향 탐색 — 한 상권에서 공급이 부족한 업종 Top N.
    메인과 동일 로직, 축만 교체한다 (별도 점수 정의를 만들지 않는다)."""
    return df[df["상권_코드"] == 상권_코드].nlargest(n, "종합점수")
