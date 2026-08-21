"""scripts/news_filter.py — 서울 음식/외식 정밀 필터 모듈."""
from __future__ import annotations

import html
import re
import pandas as pd

DAYS = 90
TOP_SANGWON = 100
PER_AREA = 3
MIN_AREAS = 20
MIN_TITLE_LEN = 10
MIN_SCORE = 1

PRESS = {
    "hankyung.com": "한국경제", "mk.co.kr": "매일경제", "sedaily.com": "서울경제",
    "mt.co.kr": "머니투데이", "asiae.co.kr": "아시아경제",
    "fnnews.com": "파이낸셜뉴스", "edaily.co.kr": "이데일리",
}

# 서울 음식/외식/식음료 상권 주요 키워드
FOOD_TOPIC = re.compile(
    r"음식|외식|식당|음식점|카페|푸드|베이커리|디저트|주점|먹거리|배달|"
    r"외식업|요리|맛집|프랜차이즈|상권|매출|임대료|개업|폐업|오픈|소비"
)

TAG = re.compile(r"<[^>]+>")
OID_PRESS = {
    "015": "한국경제", "009": "매일경제", "011": "서울경제",
    "008": "머니투데이", "277": "아시아경제",
    "014": "파이낸셜뉴스", "018": "이데일리",
}
OID_PATTERN = re.compile(r"/article/(\d{3})/")
OUT_COLS = ["상권_코드", "행정동_base", "제목", "언론사", "날짜", "링크"]


def clean(s: str) -> str:
    if not s:
        return ""
    return html.unescape(TAG.sub("", str(s))).strip()


def press_of(url: str) -> str | None:
    if not url:
        return None
    for dom, name in PRESS.items():
        if dom in url:
            return name
    m = OID_PATTERN.search(url)
    if m and m.group(1) in OID_PRESS:
        return OID_PRESS[m.group(1)]
    return None


def relevance(area: str, title: str, desc: str) -> int:
    """서울 단어 및 음식 키워드가 포함된 유의미 기사 판별"""
    if not title:
        return 0

    text = f"{title} {desc}"

    # 필수 1: 서울 포함
    if "서울" not in text:
        return 0

    # 필수 2: 음식 관련 키워드 포함
    if not FOOD_TOPIC.search(text):
        return 0

    score = 1

    # 해당 행정동 키워드가 직접 들어있으면 우선순위 가점
    short_area = area[:-1] if (area.endswith("동") or area.endswith("구")) and len(area) > 2 else area
    if area in text or short_area in text:
        score += 1

    return score


def target_areas(scores_path: str = "data/scores.csv") -> pd.Series:
    try:
        scores = pd.read_csv(scores_path, encoding="utf-8-sig", dtype={"상권_코드": str, "행정동_코드": str})
        top = (scores.sort_values("종합점수", ascending=False)
                     .drop_duplicates("상권_코드").head(TOP_SANGWON))
        top = top.assign(행정동_base=top["행정동_코드_명"].str.replace(r"\d+가?", "", regex=True))
        return top.groupby("행정동_base")["상권_코드"].apply(list)
    except Exception as e:
        print(f"[오류] target_areas 로드 실패: {e}")
        return pd.Series(dtype=object)


def expand(area: str, codes: list[str], picks: list[tuple]) -> list[dict]:
    return [{"상권_코드": code, "행정동_base": area, "제목": title,
             "언론사": press, "날짜": date, "링크": link}
            for title, press, date, link in picks
            for code in codes]


def save(rows: list[dict], path: str = "data/news.csv") -> pd.DataFrame:
    import os
    out = pd.DataFrame(rows, columns=OUT_COLS)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return out