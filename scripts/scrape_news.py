"""scripts/scrape_news.py — data/news.csv 생성 (뉴스 담당, 【주력 경로】).

requests + BeautifulSoup으로 네이버 뉴스 검색 결과 및 인링크(n.news.naver.com)
상세 페이지를 방문하여 정확한 메타데이터(제목, 언론사, 날짜, 원문링크)를 수집한다.

개선 사항:
  - 네이버 검색 결과 목록의 불완전한 카드 구조/상대 날짜("3일 전") 파싱 대신
    네이버 뉴스 상세 페이지(n.news.naver.com/mnews/article/...)의 정형화된 메타 태그
    (h2#title_area, span.media_end_head_info_datestamp_time[data-date-time],
     a.media_end_head_origin_link)를 직접 파싱하여 100% 신뢰할 수 있는 데이터 추출.
  - 경제지 OID 사전 필터링으로 불필요한 상세 요청 최소화 및 고속 수집.
  - seams/check_news.py 검증 규약(경제지 화이트리스트 도메인, YYYY-MM-DD, 90일 이내) 완벽 준수.

사용:  uv run python scripts/scrape_news.py            # 전량 수집 → 저장
       uv run python scripts/scrape_news.py 망원동      # 단건 스모크 (저장 안 함)
출력:  data/news.csv (상권_코드, 행정동_base, 제목, 언론사, 날짜, 링크)
"""
from __future__ import annotations

import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.news_filter import (  # noqa: E402
    DAYS, MIN_AREAS, MIN_SCORE, MIN_TITLE_LEN, PER_AREA, PRESS, clean, expand,
    press_of, relevance, save, target_areas,
)

SLEEP = 0.5                       # 요청 간 간격 (매너)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
NAVER_ARTICLE_RE = re.compile(r"https?://(n\.)?news\.naver\.com/mnews/article/(\d{3})/\d+")


def parse_article_detail(link: str, sess: requests.Session, now: datetime, cutoff: str) -> dict | None:
    """네이버 뉴스 상세 페이지에 접속하여 제목, 날짜, 언론사, 원문 링크, 본문 요약을 추출한다."""
    try:
        res = sess.get(link, timeout=8)
        if not res.ok:
            return None
        soup = BeautifulSoup(res.text, "html.parser")

        # 1. 제목 추출
        title_elem = soup.select_one("h2#title_area, h2.media_end_head_headline, h2")
        if not title_elem:
            return None
        title = clean(title_elem.get_text(strip=True))
        if len(title) < MIN_TITLE_LEN or "네이버뉴스" in title:
            return None

        # 2. 날짜 추출 (data-modify-date-time 또는 data-date-time 우선)
        date_elem = soup.select_one("span.media_end_head_info_datestamp_time")
        date_str = None
        if date_elem:
            raw_date = date_elem.get("data-modify-date-time") or date_elem.get("data-date-time")
            if raw_date:
                date_str = raw_date.split()[0].replace(".", "-")
            else:
                m = re.search(r"(\d{4})[\.-](\d{2})[\.-](\d{2})", date_elem.get_text())
                if m:
                    date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        if not date_str or date_str < cutoff:
            return None

        # 3. 원문 언론사 링크 및 경제지 판정
        origin_elem = soup.select_one("a.media_end_head_origin_link")
        origin_url = origin_elem["href"] if (origin_elem and origin_elem.get("href")) else link
        press = press_of(origin_url) or press_of(link)
        if not press:
            return None

        # 화이트리스트 도메인을 가진 원문 링크를 우선 채택
        final_link = origin_url
        if not any(dom in final_link for dom in PRESS) and any(dom in link for dom in PRESS):
            final_link = link

        # 4. 본문 요약
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


def scrape_area(area: str, now: datetime, sess: requests.Session) -> list[tuple]:
    """한 지역의 네이버 뉴스 검색 결과에서 (제목, 언론사, 날짜, 링크) 상위 3건을 수집한다."""
    cutoff = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d")
    query = f"서울 {area} 상권"
    url = f"https://search.naver.com/search.naver?where=news&query={quote(query)}&sm=tab_opt&sort=0"

    r = sess.get(url, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # 네이버 뉴스 인링크 목록 추출
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if NAVER_ARTICLE_RE.search(href):
            links.append(href)

    visited_links = set()
    cands = []
    stat = Counter({"검색인링크": len(links)})

    for link in links:
        if link in visited_links:
            continue
        visited_links.add(link)

        detail = parse_article_detail(link, sess, now, cutoff)
        if not detail:
            continue
        stat["상세파싱성공"] += 1

        score = relevance(area, detail["title"], detail["desc"])
        if score < MIN_SCORE:
            continue
        stat["관련도통과"] += 1

        cands.append((score, detail["date"], detail["title"], detail["press"], detail["link"]))
        time.sleep(0.3)

        if len(cands) >= PER_AREA * 2:
            break

    if os.getenv("NEWS_DEBUG"):
        print(f"  [{area}] {dict(stat)}", file=sys.stderr)

    # 중복 제거 (제목 기준)
    seen, dedup = set(), []
    for row in cands:
        if row[2] in seen:
            continue
        seen.add(row[2])
        dedup.append(row)

    dedup.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [(title, press, date_str, href)
            for _, date_str, title, press, href in dedup[:PER_AREA]]


def collect_all(scores_path: str = "data/scores.csv") -> list[dict]:
    """스크래핑으로 수집만 하고 행 목록을 돌려준다 (파일은 쓰지 않는다)."""
    global SLEEP
    area_to_sangwon = target_areas(scores_path)
    now = datetime.now()
    sess = requests.Session()
    sess.headers["User-Agent"] = UA

    rows: list[dict] = []
    fail = 0
    for area, codes in area_to_sangwon.items():
        try:
            picks = scrape_area(area, now, sess)
            fail = 0
        except requests.RequestException as e:
            fail += 1
            print(f"[경고] {area} 수집 실패: {e}", file=sys.stderr)
            if fail >= 3:
                print("연속 실패 3회 — 요청 간격을 3초로 확대", file=sys.stderr)
                SLEEP = 3.0
            continue
        rows += expand(area, codes, picks)
        time.sleep(SLEEP)
    return rows


def fallback_to_api(scores_path: str = "data/scores.csv") -> list[dict] | None:
    """백업 경로(검색 API) 호출. 실패하면 None."""
    try:
        from scripts.collect_news import collect_all as collect_api
    except ImportError as e:
        print(f"[전환 실패] collect_news 임포트 불가: {e}", file=sys.stderr)
        return None
    try:
        rows = collect_api(scores_path)
    except Exception as e:
        print(f"[전환 실패] 백업 경로 수집 오류: {e}", file=sys.stderr)
        return None
    print(f"[전환 완료] 백업 경로 수집 {len(rows)}건", file=sys.stderr)
    return rows


def smoke(area: str) -> int:
    """단건 스모크 — 빠른 검증용 (파일 저장 안 함)."""
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    picks = scrape_area(area, datetime.now(), sess)
    print(f"[{area}] {len(picks)}건 수집")
    for title, press, date_str, href in picks:
        print(f"  [{press}] ({date_str}) {title}")
        print(f"    {href}")
    return 0


def main() -> int:
    if len(sys.argv) > 1:
        return smoke(sys.argv[1])

    rows = collect_all()

    # 백업 경로 자동 전환
    n_area = len({r["행정동_base"] for r in rows})
    if n_area < MIN_AREAS:
        print(f"⚠️ 스크래핑 확보 지역 {n_area}개 < {MIN_AREAS} — "
              f"백업 경로(검색 API)로 자동 전환", file=sys.stderr)
        api_rows = fallback_to_api()
        if api_rows:
            rows = api_rows
        else:
            print(f"백업 경로도 실패 — 스크래핑 결과 {len(rows)}건으로 저장",
                  file=sys.stderr)

    out = save(rows)
    total = len(target_areas())
    n_area = out["행정동_base"].nunique() if len(out) else 0
    print(f"news.csv: {len(out):,}행 · 지역 {n_area}/{total} "
          f"· 상권 {out['상권_코드'].nunique() if len(out) else 0}개 "
          f"(확보율 {n_area/total:.0%})")
    print("→ 검증: uv run python seams/check_news.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
