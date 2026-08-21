"""scripts/collect_news.py — 뉴스 수집 【백업 경로】

네이버 검색 API로 후보 상권 관련 최근 3개월 경제지 기사를 수집한다.
주력은 `scrape_news.py`(requests+bs4)이며, 이 스크립트는 스크래핑 확보 지역이
`MIN_AREAS` 미만일 때 **자동 호출**되는 백업이다 (DEV_SPEC §4 아티팩트 3).

정밀도 필터는 여기서 구현하지 않는다 — `news_filter.py`를 주력과 **공유**한다.
각자 구현하면 한쪽만 고쳐지고, 두 경로의 스키마는 같은데 결과만 달라져
게이트가 그 차이를 잡지 못한다.

⚠️ **현재 이 경로는 키 미설정으로 동작하지 않는다.** `.env`에 키가 없으면
`collect_all()`이 RuntimeError를 던지고 주력이 그 사실을 stderr에 남긴다
(설계대로다 — 조용히 빈 결과를 돌려주면 전환 실패를 아무도 모른다).
확보율이 부족해 백업이 실제로 필요해지면 ① 키를 발급하거나
② 이 파일을 구글 뉴스 RSS 수집으로 교체한다. 둘 다 정본 개정 대상이다.

사용:  NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 를 .env 에 두고
       uv run python scripts/collect_news.py     # 단독 실행 (파일까지 저장)
       또는 scrape_news.py 가 collect_all() 을 호출  # 자동 전환
출력:  data/news.csv (상권_코드, 행정동_base, 제목, 언론사, 날짜, 링크)
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.news_filter import (  # noqa: E402
    DAYS, MIN_SCORE, PER_AREA, clean, expand, press_of, relevance, save,
    target_areas,
)

SLEEP = 0.3               # API 호출 간격 (일 25,000건 한도 내 매너)


def search(query: str, cid: str, secret: str) -> list[dict]:
    r = requests.get(
        "https://openapi.naver.com/v1/search/news.json",
        params={"query": query, "display": 30, "sort": "date"},
        headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("items", [])


def collect_all(scores_path: str = "data/scores.csv") -> list[dict]:
    """수집만 하고 행 목록을 돌려준다. **파일은 쓰지 않는다** —
    `scrape_news.py`가 폴백으로 호출할 때 저장 시점을 한 곳으로 모으기 위해서다.

    키가 없으면 RuntimeError를 던진다 (호출부가 전환 실패를 기록할 수 있도록).
    """
    load_dotenv()
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not (cid and secret):
        raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 .env 에 없다")

    area_to_sangwon = target_areas(scores_path)
    cutoff = datetime.now().astimezone() - timedelta(days=DAYS)

    rows: list[dict] = []
    for area, codes in area_to_sangwon.items():
        try:
            items = search(f"서울 {area} 상권", cid, secret)
        except requests.RequestException as e:
            print(f"[경고] {area} API 수집 실패: {e}", file=sys.stderr)
            continue
        cands = []
        for item in items:
            title, desc = clean(item["title"]), clean(item["description"])
            press = press_of(item.get("originallink", ""))
            if press is None:                      # 1) 경제지만
                continue
            pub = parsedate_to_datetime(item["pubDate"])
            if pub < cutoff:                       # 2) 최근 90일만
                continue
            score = relevance(area, title, desc)
            if score < MIN_SCORE:                  # 3) 관련도 하한 미달 탈락
                continue                           #    (주력과 같은 값을 써야 한다)
            cands.append((score, pub, title, press,
                          item.get("link") or item["originallink"]))
        cands.sort(key=lambda x: (-x[0], -x[1].timestamp()))   # 4) 점수 → 최신순
        picks = [(title, press, pub.strftime("%Y-%m-%d"), link)
                 for _, pub, title, press, link in cands[:PER_AREA]]
        rows += expand(area, codes, picks)
        time.sleep(SLEEP)
    return rows


def main() -> int:
    try:
        rows = collect_all()
    except RuntimeError as e:
        print(e)
        return 1
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
