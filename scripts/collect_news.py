"""scripts/collect_news.py — data/news.csv 생성 (뉴스 담당).

【백업 경로】네이버 검색 API로 후보 상권 관련 최근 3개월 경제지 기사를 수집한다.
주력은 scrape_news.py (requests+bs4)이며, 이 스크립트는 차단·페이지 구조 변경 시
전환하는 백업이다. 정밀도 필터 규칙은 주력과 동일하다.

정밀도 필터 (이 순서대로):
  1) 경제지 화이트리스트 — originallink 도메인으로 판정
  2) 최근 90일 — pubDate 기준 (수집일 상대 계산, 하드코딩 금지)
  3) 관련도 점수 — 제목에 지역명(2점) > 요약 앞부분에 지역명(1점), 0점 탈락
     + 상권 키워드(상권/창업/점포/임대료/골목/매출/오픈) 포함 시 +1
  4) 지역(행정동 base)당 점수순 상위 3건

사용:  NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 를 .env 에 두고
       python scripts/collect_news.py
출력:  data/news.csv (상권_코드, 행정동_base, 제목, 언론사, 날짜, 링크)
"""
from __future__ import annotations
import html
import os
import re
import sys
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.loader import load_master  # noqa: E402

# ── 계약 파라미터 (DEV_SPEC §4 아티팩트 3) ──────────────────────────────
DAYS = 90                 # 최근 3개월 (수집일 기준 상대 계산)
TOP_SANGWON = 100         # 종합점수 상위 상권 수
PER_AREA = 3              # 지역당 저장 기사 수
SLEEP = 0.3               # API 호출 간격 (일 25,000건 한도 내 매너)

# 경제지 화이트리스트 — originallink 도메인으로 판정 (API 응답에 언론사 필드가 없다)
PRESS = {
    "hankyung.com": "한국경제", "mk.co.kr": "매일경제", "sedaily.com": "서울경제",
    "mt.co.kr": "머니투데이", "asiae.co.kr": "아시아경제",
    "fnnews.com": "파이낸셜뉴스", "edaily.co.kr": "이데일리",
}
# 관련도 키워드 — 하나 이상 포함해야 상권 기사로 인정
TOPIC = re.compile(r"상권|창업|점포|임대료|골목|매출|개업|폐업|오픈|입점")

TAG = re.compile(r"<[^>]+>")


def clean(s: str) -> str:
    """API 응답의 <b> 태그·HTML 엔티티 제거."""
    return html.unescape(TAG.sub("", s)).strip()


def press_of(url: str) -> str | None:
    for dom, name in PRESS.items():
        if dom in url:
            return name
    return None


def relevance(area: str, title: str, desc: str) -> int:
    """정밀도 점수. 0점은 탈락.

    제목에 지역명이 없고 요약 앞부분에도 없으면, 지역이 스쳐 지나가는 기사
    (예: 전국 유통 기사에 '성수동 팝업' 한 줄)일 가능성이 높다 — 실측으로 확인된 패턴.
    """
    score = 0
    if area in title:
        score += 2
    elif area in desc[:60]:
        score += 1
    if score and TOPIC.search(title + " " + desc):
        score += 1
    return score


def search(query: str, cid: str, secret: str) -> list[dict]:
    r = requests.get(
        "https://openapi.naver.com/v1/search/news.json",
        params={"query": query, "display": 30, "sort": "date"},
        headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("items", [])


def main() -> int:
    load_dotenv()
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not (cid and secret):
        print("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 .env 에 없다"); return 1

    scores = pd.read_csv("data/scores.csv", encoding="utf-8-sig",
                         dtype={"상권_코드": str, "행정동_코드": str})
    top = (scores.sort_values("종합점수", ascending=False)
                 .drop_duplicates("상권_코드").head(TOP_SANGWON))

    # 검색 단위: 행정동 base (숫자 제거 — '성수1가1동' → '성수동', '망원1동' → '망원동')
    top = top.assign(행정동_base=top["행정동_코드_명"]
                     .str.replace(r"\d+가?", "", regex=True))
    area_to_sangwon = top.groupby("행정동_base")["상권_코드"].apply(list)

    cutoff = datetime.now().astimezone() - timedelta(days=DAYS)
    rows = []
    for area, sangwon_codes in area_to_sangwon.items():
        cands = []
        for item in search(f"서울 {area} 상권", cid, secret):
            title, desc = clean(item["title"]), clean(item["description"])
            press = press_of(item.get("originallink", ""))
            if press is None:                      # 1) 경제지만
                continue
            pub = parsedate_to_datetime(item["pubDate"])
            if pub < cutoff:                       # 2) 최근 90일만
                continue
            score = relevance(area, title, desc)
            if score == 0:                         # 3) 관련도 0점 탈락
                continue
            cands.append((score, pub, title, press,
                          item.get("link") or item["originallink"]))
        cands.sort(key=lambda x: (-x[0], -x[1].timestamp()))
        for score, pub, title, press, link in cands[:PER_AREA]:   # 4) 상위 3건
            for code in sangwon_codes:             # 지역 기사 → 소속 상권 전개
                rows.append({"상권_코드": code, "행정동_base": area, "제목": title,
                             "언론사": press, "날짜": pub.strftime("%Y-%m-%d"),
                             "링크": link})
        time.sleep(SLEEP)

    out = pd.DataFrame(rows)
    os.makedirs("data", exist_ok=True)
    out.to_csv("data/news.csv", index=False, encoding="utf-8-sig")
    n_area = out["행정동_base"].nunique() if len(out) else 0
    print(f"news.csv: {len(out):,}행 · 지역 {n_area}/{len(area_to_sangwon)} "
          f"· 상권 {out['상권_코드'].nunique() if len(out) else 0}개 "
          f"(확보율 {n_area/len(area_to_sangwon):.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
