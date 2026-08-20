"""scripts/debug_scrape.py — 뉴스 수집 0건의 원인을 어느 단계에서 막혔는지로 좁힌다.

일회용 진단 도구다. 원인이 확정되면 지운다.

실행:  uv run python -m scripts.debug_scrape
       (프로젝트 루트에서. `-m`으로 돌려야 scripts 패키지를 찾는다)
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.news_filter import MIN_TITLE_LEN, press_of, relevance  # noqa: E402

AREA = sys.argv[1] if len(sys.argv) > 1 else "성수동"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def main() -> int:
    url = ("https://search.naver.com/search.naver?where=news&sm=tab_opt"
           f"&query={quote(f'서울 {AREA} 상권')}&sort=1")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=10)
    print(f"[0] HTTP {r.status_code} · HTML {len(r.text):,}자 · 검색어: 서울 {AREA} 상권")
    if r.status_code != 200:
        print("    → 차단. User-Agent·간격 확인")
        return 1

    soup = BeautifulSoup(r.text, "html.parser")

    # ── 1단계: a 태그 자체가 있는가 (없으면 JS 렌더링 의심) ──────────────
    links = soup.find_all("a", href=True)
    print(f"[1] a 태그 전체: {len(links):,}개")
    if len(links) < 50:
        print("    → 너무 적다. 자바스크립트 렌더링이라 requests로는 기사가 안 온다")
        return 1

    # ── 2단계: 제목 길이 필터 ────────────────────────────────────────
    long_ = [a for a in links if len(a.get_text(" ", strip=True)) >= MIN_TITLE_LEN]
    print(f"[2] 텍스트 {MIN_TITLE_LEN}자 이상: {len(long_)}개")
    if not long_:
        print("    → 제목이 링크 텍스트에 없다. 구조가 바뀌었을 가능성")
        return 1

    # ── 3단계: 경제지 화이트리스트 (여기서 전멸하는 경우가 가장 흔하다) ──
    econ = [a for a in long_ if press_of(a["href"])]
    print(f"[3] 경제지 도메인: {len(econ)}개")

    # 어떤 도메인이 실제로 오는지 — 화이트리스트 밖이면 여기서 원인이 보인다
    domains = Counter(urlparse(a["href"]).netloc for a in long_)
    print("    실제 링크 도메인 상위 10:")
    for dom, n in domains.most_common(10):
        mark = "  ← 화이트리스트" if press_of(dom) else ""
        print(f"      {n:4d}  {dom or '(상대경로)'}{mark}")

    if not econ:
        print("    → 경제지 도메인이 0개. 링크가 네이버로 감싸져 있거나")
        print("       화이트리스트에 없는 언론사만 잡히고 있다")

    # ── 4단계: 관련도 ────────────────────────────────────────────────
    if econ:
        passed = 0
        for a in econ:
            title = a.get_text(" ", strip=True)
            block = a.find_parent(["li", "div"])
            desc = block.get_text(" ", strip=True) if block else ""
            if relevance(AREA, title, desc.replace(title, " ")[:200]):
                passed += 1
        print(f"[4] 관련도 통과: {passed}개")
        if not passed:
            print(f"    → 제목·요약 앞 60자에 '{AREA}'이 없다. 검색 단위 확인")

    # ── 표본 출력 ────────────────────────────────────────────────────
    print("\n[표본] 길이 통과한 링크 10개")
    for a in long_[:10]:
        print(f"  {a['href'][:75]}")
        print(f"    └ {a.get_text(' ', strip=True)[:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
