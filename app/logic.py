"""app/logic.py — 대시보드 로직 (Streamlit 비의존 · C조 오너)
seams/check_app.py 계약 100% 준수
"""
from __future__ import annotations

import pandas as pd

SCORES_PATH = "data/scores.csv"
NEWS_PATH = "data/news.csv"
MASTER_PATH = "data/master.csv"
LATEST_QUARTER = "20261"

STR_COLS = [
    "상권_코드", "상권_코드_명", "서비스_업종_코드", "서비스_업종_코드_명",
    "상권_구분_코드_명", "유형", "자치구_코드_명", "행정동_코드", "행정동_코드_명",
]
NEWS_COLS = ["상권_코드", "행정동_base", "제목", "언론사", "날짜", "링크"]

W_GAP_DEFAULT = 0.6
W_STAB_DEFAULT = 0.4


# ── 로드 ──────────────────────────────────────────────────────────────
def load_scores(path: str = SCORES_PATH) -> pd.DataFrame:
    """후보 테이블 로드."""
    return pd.read_csv(path, encoding="utf-8-sig", dtype={c: str for c in STR_COLS})


def load_news(path: str = NEWS_PATH) -> pd.DataFrame:
    """뉴스 테이블 로드 (미수집 시 빈 DataFrame 반환)."""
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    except FileNotFoundError:
        return pd.DataFrame(columns=NEWS_COLS)
    for c in NEWS_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    return df


def load_master(path: str = MASTER_PATH) -> pd.DataFrame:
    """상세 패널용 master 데이터 로드 (미존재 시 빈 DataFrame 반환)."""
    try:
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
    except FileNotFoundError:
        return pd.DataFrame()


# ── 점수 재계산 ───────────────────────────────────────────────────────
def rescore(
    df: pd.DataFrame,
    w_gap: float = W_GAP_DEFAULT,
    w_stab: float = W_STAB_DEFAULT,
) -> pd.DataFrame:
    """가중치 슬라이더 기반 종합점수 가중합 재계산."""
    total = w_gap + w_stab
    if total <= 0:
        w_gap, w_stab, total = W_GAP_DEFAULT, W_STAB_DEFAULT, 1.0
    g, s = w_gap / total, w_stab / total

    out = df.copy()
    out["종합점수"] = g * out["갭점수"] + s * out["안정성점수"]
    return out.sort_values("종합점수", ascending=False, kind="mergesort")


# ── 필터 ──────────────────────────────────────────────────────────────
def filter_candidates(
    df: pd.DataFrame,
    업종: list[str] | None = None,
    유형: list[str] | None = None,
    자치구: list[str] | None = None,
) -> pd.DataFrame:
    """사이드바 다중 필터 적용."""
    out = df
    if 업종:
        out = out[out["서비스_업종_코드_명"].isin(업종)]
    if 유형:
        out = out[out["유형"].isin(유형)]
    if 자치구:
        out = out[out["자치구_코드_명"].isin(자치구)]
    return out


def summary(df: pd.DataFrame) -> dict:
    """상단 요약 메트릭 계산."""
    if df.empty:
        return {"후보_수": 0, "평균_종합점수": 0.0, "상권_수": 0, "평균_공급갭": 0.0}
    return {
        "후보_수": int(len(df)),
        "평균_종합점수": float(df["종합점수"].mean()),
        "상권_수": int(df["상권_코드"].nunique()),
        "평균_공급갭": float(df["공급갭"].mean()),
    }


# ── 상세 패널 & 기사 & 역방향 ─────────────────────────────────────────
def detail_for(
    scores: pd.DataFrame,
    master: pd.DataFrame,
    상권_코드: str,
    서비스_업종_코드: str,
) -> dict:
    """③ 상세 패널용 데이터 조회 (master 부재 시 scores 기반 안전 대체)."""
    score = scores[
        (scores["상권_코드"] == 상권_코드)
        & (scores["서비스_업종_코드"] == 서비스_업종_코드)
    ]
    if score.empty:
        return {}
    s = score.iloc[0]

    detail = pd.DataFrame()
    if not master.empty and "기준_년분기_코드" in master.columns:
        latest = master[master["기준_년분기_코드"] == LATEST_QUARTER]
        detail = latest[
            (latest["상권_코드"] == 상권_코드)
            & (latest["서비스_업종_코드"] == 서비스_업종_코드)
        ]

    if not detail.empty:
        d = detail.iloc[0]
        연령_구성 = pd.DataFrame({
            "연령대": ["10대", "20대", "30대", "40대", "50대", "60대 이상"],
            "상주인구": [
                int(d.get("연령대_10_상주인구_수", 0)),
                int(d.get("연령대_20_상주인구_수", 0)),
                int(d.get("연령대_30_상주인구_수", 0)),
                int(d.get("연령대_40_상주인구_수", 0)),
                int(d.get("연령대_50_상주인구_수", 0)),
                int(d.get("연령대_60_이상_상주인구_수", 0)),
            ],
        })
        요일별_매출 = pd.DataFrame({
            "요일": ["월", "화", "수", "목", "금", "토", "일"],
            "매출금액": [
                float(d.get("월요일_매출_금액", 0)),
                float(d.get("화요일_매출_금액", 0)),
                float(d.get("수요일_매출_금액", 0)),
                float(d.get("목요일_매출_금액", 0)),
                float(d.get("금요일_매출_금액", 0)),
                float(d.get("토요일_매출_금액", 0)),
                float(d.get("일요일_매출_금액", 0)),
            ],
        })
    else:
        # master 데이터가 아직 없거나 mock 상태일 때 기본 프로파일 생성
        base_sales = float(s.get("당월_매출_금액", 10000000))
        연령_구성 = pd.DataFrame({
            "연령대": ["10대", "20대", "30대", "40대", "50대", "60대 이상"],
            "상주인구": [350, 1420, 1850, 1200, 890, 610],
        })
        요일별_매출 = pd.DataFrame({
            "요일": ["월", "화", "수", "목", "금", "토", "일"],
            "매출금액": [round(base_sales * r) for r in [0.12, 0.13, 0.14, 0.15, 0.18, 0.16, 0.12]],
        })

    return {
        "상권명": str(s.get("상권_코드_명", 상권_코드)),
        "업종": str(s.get("서비스_업종_코드_명", 서비스_업종_코드)),
        "유형": str(s.get("유형", "일반 주거·생활형")),
        "공급밀도": float(s.get("공급밀도", 0.0)),
        "동일유형_중앙_공급밀도": float(s.get("동일유형_중앙_공급밀도", 0.0)),
        "행정동_폐업률": float(s.get("행정동_폐업률", 0.0)),
        "당월_매출_금액": int(s.get("당월_매출_금액", 0)),
        "당월_매출_건수": int(s.get("당월_매출_건수", 0)),
        "연령_구성": 연령_구성,
        "요일별_매출": 요일별_매출,
    }


def news_for(news: pd.DataFrame, 상권_코드: str, n: int = 3) -> pd.DataFrame:
    """해당 상권 관련 기사 조회."""
    if news.empty:
        return news
    return news[news["상권_코드"] == 상권_코드].sort_values("날짜", ascending=False).head(n)


def reverse_lookup(df: pd.DataFrame, 상권_코드: str, n: int = 5) -> pd.DataFrame:
    """④ 역방향 탐색 — 상권 기준 공급 부족 업종 Top N."""
    return df[df["상권_코드"] == 상권_코드].nlargest(n, "종합점수")