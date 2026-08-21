"""scripts/scrape_news.py — 서울 전체 음식점/외식 관련 고품질 뉴스 자동 수집 (창업, 상권, 배달, 경기, 임대료 등)."""
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
from scripts.news_filter import (
    DAYS, MIN_TITLE_LEN, PRESS, clean, press_of, FOOD_TOPIC,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 서울 전체 음식점 관련 필수 검색 쿼리 (창업, 상권, 배달, 경기, 임대료 등)
SEOUL_FOOD_QUERIES = [
    "서울 음식점 창업",
    "서울 외식업 창업",
    "서울 식당 상권",
    "서울 골목상권 음식점",
    "서울 음식점 배달",
    "서울 외식 경기",
    "서울 음식점 임대료",
    "서울 상가 임대료 외식",
    "서울 식당 자영업",
    "서울 카페 창업",
    "서울 음식점 폐업 공실",
    "서울 외식 물가 소비",
]


def parse_article_detail(link: str, sess: requests.Session, now: datetime, cutoff: str) -> dict | None:
    try:
        res = sess.get(link, timeout=8)
        if res.status_code != 200 or not res.text:
            return None
        soup = BeautifulSoup(res.text, "html.parser")

        # 1. 날짜 추출
        date_str = None
        date_meta = (
            soup.select_one("meta[property='article:published_time']")
            or soup.select_one("meta[property='og:regDate']")
        )
        if date_meta and date_meta.get("content"):
            date_str = date_meta["content"][:10].replace(".", "-").replace("/", "-")
        else:
            date_elem = soup.select_one(
                "span.media_end_head_info_datestamp_time, span._ARTICLE_DATE_TIME, em.media_end_head_info_datestamp_time"
            )
            if date_elem:
                m = re.search(r"(\d{4})[\.-](\d{2})[\.-](\d{2})", date_elem.get_text())
                if m:
                    date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        if not date_str or date_str < cutoff:
            return None

        # 2. 제목 추출
        title_elem = soup.select_one("h2#title_area, h2.media_end_head_headline, div.media_end_head_title h2, h2")
        if not title_elem:
            return None
        title = clean(title_elem.get_text(strip=True))
        if len(title) < MIN_TITLE_LEN or "네이버뉴스" in title:
            return None

        # 3. 언론사 추출
        origin_elem = soup.select_one("a.media_end_head_origin_link")
        origin_url = origin_elem["href"] if (origin_elem and origin_elem.get("href")) else link
        press = press_of(origin_url) or press_of(link)
        if not press:
            # 메타 태그 언론사 확인
            press_meta = soup.select_one("meta[property='og:article:author'], meta[name='twitter:creator']")
            if press_meta and press_meta.get("content"):
                p_name = press_meta["content"].strip()
                for dom_name in PRESS.values():
                    if dom_name in p_name:
                        press = dom_name
                        break
        if not press:
            return None

        final_link = origin_url if any(dom in origin_url for dom in PRESS) else link

        # 4. 본문 및 요약 추출
        body_elem = soup.select_one("article#dic_area, div#articeBody, div#newsct_article")
        body_text = clean(body_elem.get_text(" ", strip=True)) if body_elem else ""

        # 키워드 관련성 검증 (음식점/외식 + 창업/상권/배달/경기/임대료 등)
        full_text = f"{title} {body_text}"
        if not FOOD_TOPIC.search(full_text):
            return None

        summary = body_text[:200] + ("..." if len(body_text) > 200 else "")

        return {
            "제목": title,
            "언론사": press,
            "날짜": date_str,
            "링크": final_link,
            "요약": summary,
        }
    except Exception:
        return None


def scrape_seoul_food_news(output_path: str = "data/seoul_food_news.csv") -> pd.DataFrame:
    """서울 전체 범위 음식점 관련 뉴스(창업, 상권, 배달, 경기, 임대료 등) 스크래핑."""
    now = datetime.now()
    cutoff = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d")

    sess = requests.Session()
    sess.headers.update(HEADERS)

    seen_links = set()
    seen_titles = set()
    collected_articles = []

    print(f"[스크래핑 시작] 대상: 서울 전체 음식점 관련 뉴스 (기간: {cutoff} ~ {now.strftime('%Y-%m-%d')})")

    for query in SEOUL_FOOD_QUERIES:
        print(f"  -> 쿼리 검색 중: '{query}'")
        for page in range(1, 3):  # 페이지별 검색
            start = (page - 1) * 10 + 1
            url = f"https://search.naver.com/search.naver?where=news&query={quote(query)}&sort=0&start={start}"
            try:
                r = sess.get(url, timeout=10)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")

                links = [
                    a["href"]
                    for a in soup.find_all("a", href=True)
                    if "news.naver.com/mnews/article/" in a["href"]
                ]

                for link in links:
                    if link in seen_links:
                        continue
                    seen_links.add(link)

                    detail = parse_article_detail(link, sess, now, cutoff)
                    if not detail:
                        continue

                    # 제목 중복 제거
                    if detail["제목"] in seen_titles:
                        continue
                    seen_titles.add(detail["제목"])

                    collected_articles.append(detail)
                    time.sleep(0.1)

            except Exception as e:
                print(f"    [오류] {query} 페이지 {page} 수집 중 예외: {e}")
                continue

    # DataFrame 생성 및 정렬
    df = pd.DataFrame(collected_articles, columns=["제목", "언론사", "날짜", "링크", "요약"])
    if not df.empty:
        df = df.sort_values(by="날짜", ascending=False).reset_index(drop=True)
        # 최종 중복 제거 (링크, 제목)
        df = df.drop_duplicates(subset=["링크"]).drop_duplicates(subset=["제목"]).reset_index(drop=True)

    # 1. seoul_food_news.csv 저장
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    # 2. data/news.csv (요약 제외 기본 버전)에도 저장
    news_csv_path = "data/news.csv"
    df[["제목", "언론사", "날짜", "링크"]].to_csv(news_csv_path, index=False, encoding="utf-8-sig")

    print(f"\n[성공] 스크래핑 완료: 총 {len(df)}건의 고유 기사 저장 -> '{output_path}' 및 '{news_csv_path}'")
    return df


def main() -> int:
    df = scrape_seoul_food_news("data/seoul_food_news.csv")
    if df.empty:
        print("[경고] 수집된 기사가 없습니다.")
        return 1

    print("\n" + "=" * 90)
    print(f"[서울 전체 음식점 관련 핵심 뉴스 수집 결과] (총 {len(df)}건)")
    print("=" * 90)
    for idx, row in df.iterrows():
        print(f"[{idx+1:02d}] [{row['언론사']}] ({row['날짜']}) {row['제목']}")
        print(f"     링크: {row['링크']}")
        print(f"     요약: {row['요약'][:120]}...\n")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())