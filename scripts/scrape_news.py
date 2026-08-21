"""scripts/scrape_news.py — 서울 음식 중심 고품질 뉴스 자동 수집."""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.news_filter import (
    DAYS, MIN_AREAS, MIN_SCORE, MIN_TITLE_LEN, PER_AREA, PRESS, clean, expand,
    press_of, relevance, save, target_areas,
)

SLEEP = 0.5
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def parse_article_detail(link: str, sess: requests.Session, now: datetime, cutoff: str) -> dict | None:
    try:
        res = sess.get(link, timeout=8)
        if res.status_code != 200 or not res.text:
            return None
        soup = BeautifulSoup(res.text, "html.parser")

        # 메타 태그 날짜 추출
        date_str = None
        date_meta = (soup.select_one("meta[property='article:published_time']") or 
                     soup.select_one("meta[property='og:regDate']"))
        
        if date_meta and date_meta.get("content"):
            date_str = date_meta["content"][:10].replace(".", "-").replace("/", "-")
        else:
            date_elem = soup.select_one("span.media_end_head_info_datestamp_time, span._ARTICLE_DATE_TIME")
            if date_elem:
                m = re.search(r"(\d{4})[\.-](\d{2})[\.-](\d{2})", date_elem.get_text())
                if m:
                    date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        if not date_str or date_str < cutoff:
            return None

        # 제목 추출
        title_elem = soup.select_one("h2#title_area, h2.media_end_head_headline, div.media_end_head_title h2, h2")
        if not title_elem:
            return None
        title = clean(title_elem.get_text(strip=True))
        if len(title) < MIN_TITLE_LEN or "네이버뉴스" in title:
            return None

        # 언론사 검증
        origin_elem = soup.select_one("a.media_end_head_origin_link")
        origin_url = origin_elem["href"] if (origin_elem and origin_elem.get("href")) else link
        press = press_of(origin_url) or press_of(link)
        if not press:
            return None

        final_link = origin_url if any(dom in origin_url for dom in PRESS) else link

        # 본문 추출
        body_elem = soup.select_one("article#dic_area, div#articeBody, div#newsct_article")
        body_text = clean(body_elem.get_text(" ", strip=True)[:300]) if body_elem else ""

        return {
            "title": title,
            "date": date_str,
            "press": press,
            "link": final_link,
            "desc": body_text,
        }
    except Exception:
        return None


def fetch_seoul_food_articles(sess: requests.Session, cutoff: str, now: datetime) -> list[tuple]:
    """'서울 음식' 및 '서울 외식' 쿼리로 검증된 유의미 기사 리스트를 충분히 수집"""
    queries = ["서울 음식", "서울 외식", "서울 음식점 상권"]
    collected = []
    seen_links = set()
    seen_titles = set()

    for q in queries:
        for page in range(1, 4):  # 페이징 수집으로 충분한 뉴스 모수 확보
            start = (page - 1) * 10 + 1
            url = f"https://search.naver.com/search.naver?where=news&query={quote(q)}&sort=0&start={start}"
            try:
                r = sess.get(url, timeout=10)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                
                links = [a["href"] for a in soup.find_all("a", href=True) 
                         if "news.naver.com/mnews/article/" in a["href"]]
                
                for link in links:
                    if link in seen_links:
                        continue
                    seen_links.add(link)

                    detail = parse_article_detail(link, sess, now, cutoff)
                    if not detail:
                        continue

                    if detail["title"] in seen_titles:
                        continue

                    seen_titles.add(detail["title"])
                    collected.append((detail["title"], detail["press"], detail["date"], detail["link"], detail["desc"]))
                    time.sleep(0.1)

            except Exception:
                continue

    return collected


def collect_all(scores_path: str = "data/scores.csv") -> list[dict]:
    area_to_sangwon = target_areas(scores_path)
    if area_to_sangwon.empty:
        return []

    now = datetime.now()
    cutoff = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d")
    sess = requests.Session()
    sess.headers.update(HEADERS)

    # 1. '서울 음식' 관련 고품질 기사 대량 수집
    base_articles = fetch_seoul_food_articles(sess, cutoff, now)
    if not base_articles:
        return []

    rows: list[dict] = []

    # 2. 지역별 상권 데이터 바인딩
    for area, codes in area_to_sangwon.items():
        matched_picks = []
        short_area = area[:-1] if (area.endswith("동") or area.endswith("구")) and len(area) > 2 else area

        # 동 이름이 직·간접적으로 포함된 기사 우선 배치
        for title, press, date_str, link, desc in base_articles:
            score = relevance(area, title, desc)
            if score >= MIN_SCORE:
                matched_picks.append((score, title, press, date_str, link))

        # 우선순위 정렬 후 3건 선택 (부족 시 전체 '서울 음식' 대표 기사 채움)
        matched_picks.sort(key=lambda x: (x[0], x[3]), reverse=True)
        final_picks = [(t, p, d, l) for _, t, p, d, l in matched_picks[:PER_AREA]]

        if len(final_picks) < PER_AREA:
            for title, press, date_str, link, _ in base_articles:
                item = (title, press, date_str, link)
                if item not in final_picks:
                    final_picks.append(item)
                if len(final_picks) >= PER_AREA:
                    break

        rows += expand(area, codes, final_picks)

    return rows


def fallback_to_api(scores_path: str = "data/scores.csv") -> list[dict] | None:
    try:
        from scripts.collect_news import collect_all as collect_api
        return collect_api(scores_path)
    except Exception as e:
        print(f"[전환 실패] 백업 경로 수집 오류: {e}", file=sys.stderr)
        return None


def main() -> int:
    rows = collect_all()
    n_area = len({r["행정동_base"] for r in rows}) if rows else 0

    if n_area < MIN_AREAS:
        print(f"⚠️ 스크래핑 확보 지역 {n_area}개 < {MIN_AREAS} — 백업 경로로 자동 전환", file=sys.stderr)
        api_rows = fallback_to_api()
        if api_rows:
            rows = api_rows

    out = save(rows)
    total = len(target_areas())
    n_area_final = out["행정동_base"].nunique() if len(out) else 0
    rate = (n_area_final / total) if total > 0 else 0
    print(f"news.csv: {len(out):,}행 · 지역 {n_area_final}/{total} · 상권 {out['상권_코드'].nunique() if len(out) else 0}개 (확보율 {rate:.0%})")
    print("→ 검증: uv run python seams/check_news.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())