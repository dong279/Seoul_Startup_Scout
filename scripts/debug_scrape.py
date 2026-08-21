"""scripts/debug_scrape.py — 뉴스 수집 0건이 어느 단계에서 막혔는지 단계별 진단.

실행:  uv run python scripts/debug_scrape.py
       uv run python scripts/debug_scrape.py 성수동
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.news_filter import (  # noqa: E402
    DAYS, MIN_SCORE, clean, press_of, relevance,
)
from scripts.scrape_news import (  # noqa: E402
    NAVER_ARTICLE_RE, UA, parse_article_detail,
)

AREA = sys.argv[1] if len(sys.argv) > 1 else "성수동"


def main() -> int:
    now = datetime.now()
    cutoff = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d")

    query = f"서울 {AREA} 상권"
    url = f"https://search.naver.com/search.naver?where=news&query={quote(query)}&sm=tab_opt&sort=0"

    sess = requests.Session()
    sess.headers["User-Agent"] = UA

    r = sess.get(url, timeout=10)
    print(f"[0] HTTP {r.status_code} · HTML {len(r.text):,}자 · 검색어: {query}")
    if r.status_code != 200:
        print("    → 요청 실패. IP 차단 또는 네트워크 확인")
        return 1

    soup = BeautifulSoup(r.text, "html.parser")

    # 1. 인링크 탐색
    all_naver_links = []
    economy_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if NAVER_ARTICLE_RE.search(href):
            all_naver_links.append(href)
            if press_of(href):
                economy_links.append(href)

    print(f"[1] 네이버 뉴스 인링크: 전체 {len(all_naver_links)}개 / 경제지 화이트리스트 {len(economy_links)}개")
    if not all_naver_links:
        print("    → 검색 결과에 네이버 뉴스 인링크가 없습니다.")
        return 1

    # 2. 상세 페이지 파싱 검증
    stat = Counter()
    samples = []
    visited = set()

    for link in economy_links:
        if link in visited:
            continue
        visited.add(link)

        detail = parse_article_detail(link, sess, now, cutoff)
        if not detail:
            stat["상세파싱실패"] += 1
            continue
        stat["상세파싱성공"] += 1

        score = relevance(AREA, detail["title"], detail["desc"])
        if score < MIN_SCORE:
            stat["관련도미달"] += 1
            continue
        stat["관련도통과"] += 1
        samples.append(detail)

    print(f"[2] 상세 파싱 결과: 성공 {stat['상세파싱성공']}개 / 실패 {stat['상세파싱실패']}개")
    print(f"[3] 관련도 점수 {MIN_SCORE}점 이상: {stat['관련도통과']}개")

    print("\n[수집된 샘플 기사]")
    for item in samples[:5]:
        print(f"  · [{item['press']}] ({item['date']}) {item['title']}")
        print(f"    원문: {item['link']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
