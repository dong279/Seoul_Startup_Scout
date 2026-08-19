"""scripts/scrape_news.py — data/news.csv 생성 (뉴스 담당, 주력 경로).

requests + BeautifulSoup으로 네이버 뉴스 검색 결과를 수집한다.

1일차 스파이크에서 확인된 문제와 해결:
  - 초기 셀렉터가 기사 제목 대신 "네이버뉴스" 버튼 라벨을 잡음 (44건 전부 동일 문자열)
  → 클래스명이 아니라 **구조 기반**으로 재설계: 제목은 news.naver.com 또는 원문 도메인을
    가리키는 링크 중 텍스트 길이가 충분한 a 태그로 판별한다.

정밀도 필터 4단계 (collect_news.py와 동일 규칙):
  1) 경제지 화이트리스트 — 링크 도메인으로 판정
  2) 최근 90일 — 검색 URL 기간 파라미터(수집일 상대 계산) + 날짜 텍스트 파싱
  3) 관련도 점수 — 제목에 지역명 2점 > 요약 앞 60자 1점 > 0점 탈락, 상권 키워드 +1
  4) 지역(행정동 base)당 상위 3건

수집 매너: 요청 간 time.sleep(1) 이상 · 브라우저 User-Agent · 검색 첫 페이지만.
차단 징후(HTTP 4xx/빈 결과 연속) 시 간격 3초로 확대, 계속되면 백업 경로
`collect_news.py`(검색 API)로 전환한다 — DEV_SPEC §4 아티팩트 3 전환 기준 참조.

사용:  uv run python scripts/scrape_news.py
출력:  data/news.csv (상권_코드, 행정동_base, 제목, 언론사, 날짜, 링크)
"""
from __future__ import annotations
import os
import re
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import quote

import pandas as pd
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 계약 파라미터 (DEV_SPEC §4 아티팩트 3) ──────────────────────────────
DAYS = 90
TOP_SANGWON = 100
PER_AREA = 3
SLEEP = 1.0                       # 요청 간 최소 간격 (매너)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

PRESS = {
    "hankyung.com": "한국경제", "mk.co.kr": "매일경제", "sedaily.com": "서울경제",
    "mt.co.kr": "머니투데이", "asiae.co.kr": "아시아경제",
    "fnnews.com": "파이낸셜뉴스", "edaily.co.kr": "이데일리",
}
TOPIC = re.compile(r"상권|창업|점포|임대료|골목|매출|개업|폐업|오픈|입점")
REL_DATE = re.compile(r"(\d+)(분|시간|일|주)\s*전")


def press_of(url: str) -> str | None:
    for dom, name in PRESS.items():
        if dom in url:
            return name
    return None


def relevance(area: str, title: str, desc: str) -> int:
    """제목에 지역명(2) > 요약 앞 60자(1) > 탈락(0). 상권 키워드 포함 시 +1."""
    score = 2 if area in title else (1 if area in desc[:60] else 0)
    if score and TOPIC.search(title + " " + desc):
        score += 1
    return score


def parse_date(text: str, now: datetime) -> str:
    """'3일 전' / '2026.08.12.' 두 형식을 YYYY-MM-DD로."""
    m = REL_DATE.search(text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"분": timedelta(minutes=n), "시간": timedelta(hours=n),
                 "일": timedelta(days=n), "주": timedelta(weeks=n)}[unit]
        return (now - delta).strftime("%Y-%m-%d")
    m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return now.strftime("%Y-%m-%d")


def scrape_area(area: str, now: datetime, sess: requests.Session) -> list[tuple]:
    """한 지역의 검색 첫 페이지에서 후보 기사들을 추출한다."""
    since = (now - timedelta(days=DAYS)).strftime("%Y.%m.%d")
    until = now.strftime("%Y.%m.%d")
    url = ("https://search.naver.com/search.naver?where=news&sm=tab_opt"
           f"&query={quote(f'서울 {area} 상권')}"
           f"&pd=3&ds={since}&de={until}&sort=1")   # pd=3: 기간 직접 지정, sort=1: 최신순
    r = sess.get(url, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    out = []
    # 구조 기반 판별: 뉴스 기사 블록의 제목 링크는
    #  ① href가 언론사 원문 또는 n.news.naver.com 을 가리키고
    #  ② 링크 텍스트가 실제 제목(15자 이상)이다  ← "네이버뉴스"(6자) 버튼 라벨이 걸러지는 지점
    for a in soup.find_all("a", href=True):
        href, title = a["href"], a.get_text(" ", strip=True)
        if len(title) < 15:                      # 버튼 라벨·언론사명 제외
            continue
        press = press_of(href)
        if press is None:                        # 1) 경제지만
            continue
        block = a.find_parent(["li", "div"])
        desc, date_text = "", ""
        if block:
            texts = block.get_text(" ", strip=True)
            desc = texts.replace(title, " ")[:200]
            date_text = texts
        score = relevance(area, title, desc)
        if score == 0:                           # 3) 관련도 0 탈락
            continue
        out.append((score, parse_date(date_text, now), title, press, href))
    # 같은 제목 중복 제거 (원문/네이버뉴스 이중 링크 대비)
    seen, dedup = set(), []
    for row in out:
        if row[2] in seen:
            continue
        seen.add(row[2]); dedup.append(row)
    # 4) 관련도 높은 순 → 같은 점수면 최신순, 상위 3건
    dedup.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return dedup[:PER_AREA]


def main() -> int:
    scores = pd.read_csv("data/scores.csv", encoding="utf-8-sig",
                         dtype={"상권_코드": str, "행정동_코드": str})
    top = (scores.sort_values("종합점수", ascending=False)
                 .drop_duplicates("상권_코드").head(TOP_SANGWON))
    top = top.assign(행정동_base=top["행정동_코드_명"]
                     .str.replace(r"\d+가?", "", regex=True))
    area_to_sangwon = top.groupby("행정동_base")["상권_코드"].apply(list)

    now = datetime.now()
    sess = requests.Session()
    sess.headers["User-Agent"] = UA

    rows, fail = [], 0
    for area, codes in area_to_sangwon.items():
        try:
            picks = scrape_area(area, now, sess)
            fail = 0
        except requests.RequestException as e:
            fail += 1
            print(f"[경고] {area} 수집 실패: {e}")
            if fail >= 3:
                print("연속 실패 3회 — 간격을 3초로 확대. 지속되면 collect_news.py(API)로 전환할 것")
                globals()["SLEEP"] = 3.0
            continue
        for score, date, title, press, link in picks:
            for code in codes:
                rows.append({"상권_코드": code, "행정동_base": area, "제목": title,
                             "언론사": press, "날짜": date, "링크": link})
        time.sleep(SLEEP)

    out = pd.DataFrame(rows)
    os.makedirs("data", exist_ok=True)
    out.to_csv("data/news.csv", index=False, encoding="utf-8-sig")
    n_area = out["행정동_base"].nunique() if len(out) else 0
    print(f"news.csv: {len(out):,}행 · 지역 {n_area}/{len(area_to_sangwon)} "
          f"(확보율 {n_area/len(area_to_sangwon):.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
