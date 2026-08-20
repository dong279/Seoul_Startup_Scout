"""scripts/debug_scrape.py — 뉴스 수집 0건이 어느 단계에서 막혔는지로 좁힌다.

일회용 진단 도구다. 원인이 확정되면 지운다 (4일차 기능 동결 전).

**v6에서 고친 것 — 이전 버전은 본 실행과 조건이 달라 비교가 성립하지 않았다.**
  ① URL에 기간 파라미터(pd/ds/de)가 없었다 → 정본과 동일하게 맞춤
  ② 날짜 단계가 아예 없어 `press_of` 다음이 바로 `relevance`였다.
     그래서 "망원동 관련도 2개"는 날짜 검증을 안 거친 숫자였다 → 단계 추가
  ③ 제목·요약이 같은 URL을 가리키는 별개 <a>인데 각각 세어 실제 기사 수의
     두 배가 나왔다 → href 그룹 수로 집계
  로직은 복제하지 않고 `scrape_news`의 함수를 **그대로 호출**한다. 복제본을 고치면
  "디버그는 되는데 본 실행은 0건"이 반복된다.

실행:  uv run python -m scripts.debug_scrape
       uv run python -m scripts.debug_scrape 망원동
       (프로젝트 루트에서. `-m`으로 돌려야 scripts 패키지를 찾는다)
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.news_filter import (  # noqa: E402
    DAYS, MIN_SCORE, MIN_TITLE_LEN, clean, press_of, relevance,
)
from scripts.scrape_news import (  # noqa: E402
    SKIP, UA, card_root, parse_date, strip_tail,
)

AREA = sys.argv[1] if len(sys.argv) > 1 else "성수동"


def main() -> int:
    now = datetime.now()
    since = (now - timedelta(days=DAYS)).strftime("%Y.%m.%d")
    until = now.strftime("%Y.%m.%d")
    cutoff = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d")

    # 정본 scrape_area()와 **동일한 URL** — 기간 파라미터 포함
    url = ("https://search.naver.com/search.naver?where=news&sm=tab_opt"
           f"&query={quote(f'서울 {AREA} 상권')}"
           f"&pd=3&ds={since}&de={until}&sort=1")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=10)
    print(f"[0] HTTP {r.status_code} · HTML {len(r.text):,}자 · 검색어: 서울 {AREA} 상권")
    if r.status_code != 200:
        print("    → 차단. IP·User-Agent·간격 확인 (403은 셀렉터 문제가 아니다)")
        return 1

    soup = BeautifulSoup(r.text, "html.parser")

    # ── 1단계: a 태그가 있는가 (없으면 JS 렌더링 의심) ────────────────
    links = soup.find_all("a", href=True)
    print(f"[1] a 태그 전체: {len(links):,}개")
    if len(links) < 50:
        print("    → 너무 적다. 자바스크립트 렌더링이라 requests로는 기사가 안 온다")
        return 1

    # ── 2단계: 경제지 화이트리스트 + href 그룹 (= 실제 기사 수) ────────
    groups: dict[str, list] = {}
    all_domains = Counter()
    for a in links:
        href = a["href"]
        all_domains[urlparse(href).netloc] += 1
        if not href.startswith("http") or SKIP.search(href):
            continue
        if press_of(href) is None:
            continue
        groups.setdefault(href, []).append(a)

    print(f"[2] 경제지 기사(href 그룹): {len(groups)}개")
    print("    실제 링크 도메인 상위 10:")
    for dom, n in all_domains.most_common(10):
        mark = "  ← 화이트리스트" if press_of(dom) else ""
        print(f"      {n:4d}  {dom or '(상대경로)'}{mark}")
    if not groups:
        print("    → 경제지 도메인 0개. 화이트리스트 7종이 이 지역을 안 다루거나,")
        print("       링크가 n.news.naver.com 인링크로 감싸져 있다")
        return 1

    # ── 3~5단계: 제목 → 날짜 → 관련도 (정본과 같은 순서·같은 함수) ────
    stat = Counter()
    dropped_date = []
    for href, tags in groups.items():
        head = tags[0]
        title = clean(strip_tail(head.get("title")
                                 or head.get_text(" ", strip=True)))
        if len(title) < MIN_TITLE_LEN:
            continue
        stat["제목"] += 1

        block = card_root(head, now)
        texts = block.get_text(" ", strip=True) if block else ""
        date = parse_date(texts, now)
        if date is None or date < cutoff:
            dropped_date.append((title, date, texts[:90]))
            continue
        stat["날짜"] += 1

        desc = clean(strip_tail(" ".join(t.get_text(" ", strip=True)
                                         for t in tags[1:])))
        if not desc:
            desc = clean(texts.replace(title, " ")[:200])
        if relevance(AREA, title, desc) >= MIN_SCORE:
            stat["관련도"] += 1

    print(f"[3] 제목 {MIN_TITLE_LEN}자 이상: {stat['제목']}개")
    print(f"[4] 날짜 파싱·90일 이내: {stat['날짜']}개")
    print(f"[5] 관련도 {MIN_SCORE}점 이상: {stat['관련도']}개")

    if stat["제목"] and not stat["날짜"]:
        print("    → 날짜 단계에서 전멸. card_root가 날짜를 못 찾고 있다.")
        print("       CARD_MAX_UP(현재 4)을 5~6으로 올려볼 것. 탈락 표본:")
        for title, date, texts in dropped_date[:3]:
            print(f"       · {title[:40]} / date={date}")
            print(f"         카드텍스트: {texts}")
    if stat["날짜"] and not stat["관련도"]:
        print(f"    → 제목·요약 앞 60자에 '{AREA}'이 없다. 검색 단위 확인")

    # ── 표본 ────────────────────────────────────────────────────────
    print(f"\n[표본] 경제지 기사 {min(5, len(groups))}건 (그룹당 링크 수 = 제목+요약)")
    for href, tags in list(groups.items())[:5]:
        head = tags[0]
        title = clean(strip_tail(head.get("title")
                                 or head.get_text(" ", strip=True)))
        print(f"  {href[:75]}  (링크 {len(tags)}개)")
        print(f"    └ {title[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
