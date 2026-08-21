"""scripts/news_filter.py — 뉴스 정밀도 필터 공유 모듈 (주력·백업 공통).

`scrape_news.py`(주력, requests+bs4)와 `collect_news.py`(백업, 검색 API)가
**이 모듈 하나만** 사용한다. 필터를 각자 구현하면 한쪽만 고쳐지고,
그 차이는 게이트가 잡지 못한다 — 두 경로의 산출물 스키마는 같은데
필터 결과만 달라지기 때문이다.

계약: DEV_SPEC §4 아티팩트 3 · 정밀도 필터 4단계
"""
from __future__ import annotations

import html
import re

import pandas as pd

# ── 계약 파라미터 (DEV_SPEC §4 아티팩트 3) ──────────────────────────────
DAYS = 90                 # 최근 3개월 (수집일 기준 상대 계산 — 하드코딩 금지)
TOP_SANGWON = 100         # 종합점수 상위 상권 수
PER_AREA = 3              # 지역당 저장 기사 수
MIN_AREAS = 20            # 확보 지역이 이 밑이면 수집 실패 → 백업 경로 전환
MIN_TITLE_LEN = 15        # 제목 최소 길이 — "네이버뉴스"(6자) 버튼 라벨이 걸러지는 지점
MIN_SCORE = 1             # 관련도 하한 (3단계). **1 = 계약 그대로(0점 탈락)** —
                          # 현재 동작과 동일하다. 확보율에 여유가 생기면 2로 올려
                          # "제목에 지역명" 또는 "요약 지역명+상권 키워드"만 통과시킨다.
                          # 주력·백업이 **같은 값**을 써야 게이트가 의미를 갖는다.

# 경제지 화이트리스트 — **링크 도메인으로 판정**한다.
# API 응답에는 언론사 필드가 없고, 스크래핑에서는 표기가 변형되기 때문이다.
PRESS = {
    "hankyung.com": "한국경제", "mk.co.kr": "매일경제", "sedaily.com": "서울경제",
    "mt.co.kr": "머니투데이", "asiae.co.kr": "아시아경제",
    "fnnews.com": "파이낸셜뉴스", "edaily.co.kr": "이데일리",
}
# 관련도 가점 키워드
TOPIC = re.compile(r"상권|창업|점포|임대료|골목|매출|개업|폐업|오픈|입점")

TAG = re.compile(r"<[^>]+>")

OUT_COLS = ["상권_코드", "행정동_base", "제목", "언론사", "날짜", "링크"]


def clean(s: str) -> str:
    """`<b>` 태그·HTML 엔티티 제거. 저장 전 반드시 통과시킨다
    (`check_news.py`가 잔존 여부를 검사한다)."""
    return html.unescape(TAG.sub("", s)).strip()


def press_of(url: str) -> str | None:
    """1단계 — 경제지 화이트리스트. 해당 없으면 None(탈락).

    ⚠️ 네이버 인링크(n.news.naver.com/mnews/article/{oid}/{aid})는 여기서 탈락한다.
    oid 매핑을 추가하면 확보율이 오르지만, `check_news.py`가 `링크` 컬럼을
    화이트리스트 도메인 정규식으로 검사하므로 **게이트가 red가 된다**.
    도입하려면 게이트의 허용 도메인 확장을 같은 커밋에 담아야 한다.
    """
    for dom, name in PRESS.items():
        if dom in url:
            return name
    return None


def relevance(area: str, title: str, desc: str) -> int:
    """3단계 — 관련도 점수. `MIN_SCORE` 미만은 탈락.

    제목에도 요약 앞부분에도 지역명이 없으면 지역이 스쳐 지나가는 기사
    (예: 전국 유통 기사에 '성수동 팝업' 한 줄)일 가능성이 높다 — 실측 확인된 패턴.
    """
    score = 0
    if area in title:
        score += 2
    elif area in desc[:60]:
        score += 1
    if score and TOPIC.search(title + " " + desc):
        score += 1
    return score


def target_areas(scores_path: str = "data/scores.csv") -> pd.Series:
    """수집 대상: 종합점수 상위 상권이 속한 행정동 base → 소속 상권 코드 목록.

    검색 단위를 행정동 base로 두는 이유는 기사 확보율이다
    ('성수1가1동'으로는 기사가 잡히지 않는다).

    ⚠️ **여기서 이미 base형으로 정규화된 값이 나온다.** 호출부에서 `re.sub`로
    다시 숫자·특수문자를 제거하지 말 것 — `행정동_base`는 C조가 쓰는 조인 키라
    한 글자만 달라져도 화면에서 기사가 통째로 사라지고, 원인은 앱 쪽처럼 보인다.
    """
    scores = pd.read_csv(scores_path, encoding="utf-8-sig",
                         dtype={"상권_코드": str, "행정동_코드": str})
    top = (scores.sort_values("종합점수", ascending=False)
                 .drop_duplicates("상권_코드").head(TOP_SANGWON))
    top = top.assign(행정동_base=top["행정동_코드_명"]
                     .str.replace(r"\d+가?", "", regex=True))
    return top.groupby("행정동_base")["상권_코드"].apply(list)


def expand(area: str, codes: list[str], picks: list[tuple]) -> list[dict]:
    """지역 기사를 소속 상권들로 전개한다.
    picks: (제목, 언론사, 날짜YYYY-MM-DD, 링크) 튜플 목록."""
    return [{"상권_코드": code, "행정동_base": area, "제목": title,
             "언론사": press, "날짜": date, "링크": link}
            for title, press, date, link in picks
            for code in codes]


def save(rows: list[dict], path: str = "data/news.csv") -> pd.DataFrame:
    """산출 파일 저장. 빈 결과에서도 컬럼 순서가 계약대로 유지되도록 명시한다."""
    import os
    out = pd.DataFrame(rows, columns=OUT_COLS)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return out
