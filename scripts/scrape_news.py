"""scripts/scrape_news.py — data/news.csv 생성 (뉴스 담당, 【주력 경로】).

requests + BeautifulSoup으로 네이버 뉴스 검색 결과를 수집한다.

1일차 스파이크에서 확인된 문제와 해결:
  - 초기 셀렉터가 기사 제목 대신 "네이버뉴스" 버튼 라벨을 잡음 (44건 전부 동일 문자열)
  → 클래스명이 아니라 **구조 기반**으로 재설계: 제목은 경제지 도메인을 가리키는 링크 중
    텍스트 길이가 MIN_TITLE_LEN 이상인 a 태그로 판별한다.

정밀도 필터는 여기서 구현하지 않는다 — `news_filter.py`를 백업 경로와 **공유**한다.
각자 구현하면 한쪽만 고쳐지고, 두 경로의 스키마는 같은데 결과만 달라져
게이트가 그 차이를 잡지 못한다.

수집 매너: 요청 간 time.sleep(1) 이상 · 브라우저 User-Agent · 검색 첫 페이지만.
연속 실패 3회면 간격을 3초로 확대한다.

**백업 전환은 코드가 한다** (DEV_SPEC §4 아티팩트 3): 수집 완료 시점에 확보 지역이
MIN_AREAS 미만이면 `collect_news.collect_all()`을 자동 호출하고 stderr에 기록한다.
사람의 판단에 걸어두면 마감 직전에 전환이 일어나지 않는다.

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

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.news_filter import (  # noqa: E402
    DAYS, MIN_AREAS, MIN_TITLE_LEN, PER_AREA, clean, expand, press_of,
    relevance, save, target_areas,
)

SLEEP = 1.0                       # 요청 간 최소 간격 (매너)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

REL_DATE = re.compile(r"(\d+)(분|시간|일|주)\s*전")


def parse_date(text: str, now: datetime) -> str | None:
    """'3일 전' / '2026.08.12.' 두 형식을 YYYY-MM-DD로.

    **파싱 실패 시 None을 돌려준다.** 예전에는 오늘 날짜로 대체했는데,
    그러면 90일이 지난 기사가 오늘 기사로 둔갑해 게이트를 통과한다.
    날짜를 모르는 기사는 버리는 편이 낫다.
    """
    m = REL_DATE.search(text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"분": timedelta(minutes=n), "시간": timedelta(hours=n),
                 "일": timedelta(days=n), "주": timedelta(weeks=n)}[unit]
        return (now - delta).strftime("%Y-%m-%d")
    m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def scrape_area(area: str, now: datetime, sess: requests.Session) -> list[tuple]:
    """한 지역의 검색 첫 페이지에서 (제목, 언론사, 날짜, 링크) 상위 3건을 뽑는다."""
    since = (now - timedelta(days=DAYS)).strftime("%Y.%m.%d")
    until = now.strftime("%Y.%m.%d")
    url = ("https://search.naver.com/search.naver?where=news&sm=tab_opt"
           f"&query={quote(f'서울 {area} 상권')}"
           f"&pd=3&ds={since}&de={until}&sort=1")   # pd=3: 기간 직접 지정, sort=1: 최신순
    r = sess.get(url, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    cutoff = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d")
    out = []
    # 구조 기반 판별: 뉴스 기사 블록의 제목 링크는
    #  ① href가 경제지 원문 도메인을 가리키고
    #  ② 링크 텍스트가 실제 제목이다 ← "네이버뉴스"(6자) 버튼 라벨이 걸러지는 지점
    for a in soup.find_all("a", href=True):
        href, title = a["href"], clean(a.get_text(" ", strip=True))
        if len(title) < MIN_TITLE_LEN:           # 버튼 라벨·언론사명 제외
            continue
        press = press_of(href)
        if press is None:                        # 1) 경제지만
            continue
        block = a.find_parent(["li", "div"])
        texts = block.get_text(" ", strip=True) if block else ""
        desc = clean(texts.replace(title, " ")[:200])
        date = parse_date(texts, now)
        if date is None or date < cutoff:        # 2) 날짜 불명·90일 초과 탈락
            continue
        score = relevance(area, title, desc)
        if score == 0:                           # 3) 관련도 0 탈락
            continue
        out.append((score, date, title, press, href))

    # 같은 제목 중복 제거 (원문/네이버뉴스 이중 링크 대비)
    seen, dedup = set(), []
    for row in out:
        if row[2] in seen:
            continue
        seen.add(row[2])
        dedup.append(row)
    # 4) 관련도 높은 순 → 같은 점수면 최신순, 상위 3건
    dedup.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [(title, press, date, href)
            for _, date, title, press, href in dedup[:PER_AREA]]


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
    """백업 경로(검색 API) 호출. 실패하면 None — 호출부가 주력 결과를 유지한다."""
    try:
        from scripts.collect_news import collect_all as collect_api
    except ImportError as e:
        print(f"[전환 실패] collect_news 임포트 불가: {e}", file=sys.stderr)
        return None
    try:
        rows = collect_api(scores_path)
    except Exception as e:                      # API 키 미설정·한도 초과 등
        print(f"[전환 실패] 백업 경로 수집 오류: {e}", file=sys.stderr)
        return None
    print(f"[전환 완료] 백업 경로 수집 {len(rows)}건", file=sys.stderr)
    return rows


def main() -> int:
    rows = collect_all()

    # ── 백업 경로 자동 전환 (DEV_SPEC §4 아티팩트 3) ──────────────────
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
