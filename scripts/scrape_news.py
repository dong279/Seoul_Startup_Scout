"""scripts/scrape_news.py — data/news.csv 생성 (뉴스 담당, 【주력 경로】).

requests + BeautifulSoup으로 네이버 뉴스 검색 결과를 수집한다.

3일차 실측에서 확인된 문제와 해결 (v6):
  - 초기 403은 **IP 차단**이었다 (PC 변경 후 HTTP 200 정상). 셀렉터 문제가 아니었다.
  - 남은 0건의 원인은 파싱 두 곳:
    ① `a.find_parent(["li","div"])`가 '가장 가까운' 부모를 잡는데 날짜는 그보다
       위 카드 루트에 있다 → `parse_date`가 전건 None → 계약(날짜 불명은 탈락)대로
       모두 버려졌다. `card_root()`로 날짜가 나올 때까지 최대 4단계 거슬러 올라간다.
    ② 네이버 카드는 **제목과 요약이 같은 URL을 가리키는 별개의 `<a>`** 다. a 태그를
       하나씩 순회하면 한 기사가 두 행이 되고, 요약문이 `제목` 컬럼에 들어간다.
       → href로 먼저 묶고(`groups`) 그룹의 첫 링크만 제목으로 쓴다.
    ③ 화면용으로 잘린 텍스트 대신 `a["title"]` 속성의 원본 제목을 쓰고,
       접근성 숨김 텍스트('새 창 열림' 등)를 꼬리에서 제거한다.

정밀도 필터는 여기서 구현하지 않는다 — `news_filter.py`를 백업 경로와 **공유**한다.
각자 구현하면 한쪽만 고쳐지고, 두 경로의 스키마는 같은데 결과만 달라져
게이트가 그 차이를 잡지 못한다.

수집 매너: 요청 간 time.sleep(1) 이상 · 브라우저 User-Agent · 검색 첫 페이지만.
연속 실패 3회면 간격을 3초로 확대한다.

**백업 전환은 코드가 한다** (DEV_SPEC §4 아티팩트 3): 수집 완료 시점에 확보 지역이
MIN_AREAS 미만이면 `collect_news.collect_all()`을 자동 호출하고 stderr에 기록한다.
사람의 판단에 걸어두면 마감 직전에 전환이 일어나지 않는다.

사용:  uv run python scripts/scrape_news.py            # 전량 수집 → 저장
       uv run python scripts/scrape_news.py 망원동      # 단건 스모크 (저장 안 함)
       NEWS_DEBUG=1 uv run python scripts/scrape_news.py 망원동   # 단계별 카운터
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
    DAYS, MIN_AREAS, MIN_SCORE, MIN_TITLE_LEN, PER_AREA, clean, expand,
    press_of, relevance, save, target_areas,
)

SLEEP = 1.0                       # 요청 간 최소 간격 (매너)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

REL_DATE = re.compile(r"(\d+)(분|시간|일|주)\s*전")

# 기사가 아닌 네이버 내부 링크 — 디버그 표본에서 실제로 잡힌 것들
SKIP = re.compile(r"//(keep|mkt|blog|cafe|shopping|search)\.naver\.com"
                  r"|/main/static/")
# 접근성 숨김 텍스트가 제목 꼬리에 붙는다 ("… 새 창 열림")
TAIL = re.compile(r"\s*(새 창 열림|네이버뉴스|언론사 선정|전체 기사 보기"
                  r"|본문 듣기|다른 기사 보기)\s*$")
CARD_MAX_LEN = 1200               # 이보다 크면 결과 목록 전체 — 옆 기사 날짜를 집는다
CARD_MAX_UP = 4                   # 카드 루트를 찾아 올라갈 최대 단계


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


def strip_tail(s: str) -> str:
    """제목 꼬리의 접근성 숨김 텍스트를 반복 제거한다 (두 개가 겹쳐 붙기도 한다)."""
    prev = None
    while prev != s:
        prev, s = s, TAIL.sub("", s).strip()
    return s


def card_root(a, now: datetime):
    """날짜 문자열이 나올 때까지 부모를 거슬러 올라가 기사 카드를 찾는다.

    `find_parent(["li","div"])`는 '가장 가까운' 부모라 제목만 감싼 래퍼를 잡는다.
    날짜는 그보다 위에 있어서 `parse_date`가 전건 None을 돌려주고, 계약상
    '날짜 불명은 탈락'이므로 조용히 전부 버려진다 — 3일차 0건의 주원인.
    """
    node = a
    for _ in range(CARD_MAX_UP):
        node = node.parent
        if node is None:
            return None
        text = node.get_text(" ", strip=True)
        if len(text) > CARD_MAX_LEN:      # 목록 전체로 올라갔다 — 옆 기사 날짜 오염
            return None
        if parse_date(text, now):
            return node
    return None


def scrape_area(area: str, now: datetime, sess: requests.Session) -> list[tuple]:
    """한 지역의 검색 첫 페이지에서 (제목, 언론사, 날짜, 링크) 상위 3건을 뽑는다."""
    since = (now - timedelta(days=DAYS)).strftime("%Y.%m.%d")
    until = now.strftime("%Y.%m.%d")
    url = ("https://search.naver.com/search.naver?where=news&sm=tab_opt"
           f"&query={quote(f'서울 {area} 상권')}"
           f"&pd=3&ds={since}&de={until}&sort=1")   # pd=3: 기간 지정, sort=1: 최신순
    r = sess.get(url, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    cutoff = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d")

    # ── 1) 경제지 화이트리스트 + href로 묶기 ────────────────────────────
    # 네이버 카드는 제목과 요약이 같은 URL을 가리키는 별개의 <a>다.
    # 묶지 않으면 한 기사가 두 행이 되고 요약문이 제목 컬럼에 들어간다.
    groups: dict[str, list] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http") or SKIP.search(href):
            continue
        if press_of(href) is None:
            continue
        groups.setdefault(href, []).append(a)

    stat = Counter({"경제지": len(groups)})
    out = []
    for href, tags in groups.items():
        head = tags[0]                    # 문서 순서상 첫 링크가 제목
        # 화면용으로 잘린 텍스트 대신 title 속성의 원본 제목을 우선한다
        title = clean(strip_tail(head.get("title")
                                 or head.get_text(" ", strip=True)))
        if len(title) < MIN_TITLE_LEN:    # 버튼 라벨·언론사명 제외
            continue
        stat["제목"] += 1

        block = card_root(head, now)
        texts = block.get_text(" ", strip=True) if block else ""
        date = parse_date(texts, now)
        if date is None or date < cutoff:  # 2) 날짜 불명·90일 초과 탈락
            continue
        stat["날짜"] += 1

        # 요약은 같은 카드의 나머지 링크에서 — 없으면 카드 텍스트에서 제목을 뺀 나머지
        desc = clean(strip_tail(" ".join(t.get_text(" ", strip=True)
                                         for t in tags[1:])))
        if not desc:
            desc = clean(texts.replace(title, " ")[:200])

        score = relevance(area, title, desc)
        if score < MIN_SCORE:              # 3) 관련도 하한 미달 탈락
            continue
        stat["관련도"] += 1
        out.append((score, date, title, press_of(href), href))

    if os.getenv("NEWS_DEBUG"):
        print(f"  [{area}] {dict(stat)}", file=sys.stderr)

    # 같은 제목 중복 제거 (원문 링크와 네이버 인링크가 별개 URL인 경우 대비)
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


def smoke(area: str) -> int:
    """단건 스모크 — 60개를 다 돌리고 0건을 확인하는 사이클을 3초로 줄인다.
    **파일을 쓰지 않는다.**"""
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    picks = scrape_area(area, datetime.now(), sess)
    print(f"[{area}] {len(picks)}건")
    for title, press, date, href in picks:
        print(f"  {date} · {press} · {title}")
        print(f"    {href}")
    if not picks:
        print("→ NEWS_DEBUG=1 로 다시 실행해 어느 단계에서 0이 되는지 확인", file=sys.stderr)
    return 0


def main() -> int:
    if len(sys.argv) > 1:
        return smoke(sys.argv[1])

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
