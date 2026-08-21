# seams/check_news.py — 뉴스 담당 → C조 인계 검증 (v7 · 서울 전역)
# DEV_SPEC §4 아티팩트 3 계약을 그대로 검사로 옮긴 것.
# 계약에 없는 검사를 추가하고 싶으면 문서에 먼저 넣는다.
#
# ── v7 개정 ─────────────────────────────────────────────────────────
# 수집 단위가 행정동 → 서울 전역(음식·창업 주제)으로 바뀌면서 기사가 특정
# 상권에 묶이지 않게 되었다. 그래서 아래 두 검사를 **삭제**했다.
#   · 상권_코드 ↔ scores.csv 조인 검사  — 붙일 키가 없어졌다
#   · 지역당 3건 상한 검사             — '지역'이라는 단위 자체가 없어졌다
# 나머지 6종(컬럼·0건·결측·기간·도메인·제목품질)은 수집 단위와 무관하므로
# 그대로 유지한다. 중복 검사는 v7에서 계약에 들어와(같은 기사가 여러 경제지에
# 배급된다) 새로 추가했다.
#
# 이 게이트는 **형식만** 본다. 기사가 창업 검토에 쓸모 있는지는 검사하지
# 않으므로, 수집 후 사람이 목록을 눈으로 보는 절차가 여전히 수용 기준이다.
# 마지막의 '관련 키워드 없음' 줄은 그 육안 확인 대상을 좁혀 주는 경고이며
# red가 아니다.
#
# 사용: uv run python seams/check_news.py [경로]
import re
import sys
from datetime import date, timedelta

import pandas as pd

DEFAULT_PATHS = ["data/news.csv", "data/seoul_food_news.csv"]
PATH = sys.argv[1] if len(sys.argv) > 1 else None

COLS = ["제목", "언론사", "날짜", "링크"]          # 필수
OPTIONAL_COLS = ["요약"]                          # 있으면 결측만 본다

# 경제지 화이트리스트 — **링크 도메인으로 판정**한다 (언론사 표기 변형에 흔들리지 않음).
# 계약을 독립적으로 다시 적은 것이지 news_filter.PRESS를 import하지 않는다 —
# 수집기 상수를 그대로 갖다 쓰면 수집기가 틀렸을 때 게이트가 같이 틀린다.
PRESS_DOMAINS = {
    "hankyung.com", "mk.co.kr", "sedaily.com", "mt.co.kr",
    "asiae.co.kr", "fnnews.com", "edaily.co.kr",
    "chosun.com", "heraldcorp.com",               # v7 추가 — 조선비즈·헤럴드경제
}
DAYS = 90
MIN_TITLE_LEN = 10          # v7: 15 → 10 (수집기 news_filter.MIN_TITLE_LEN과 같은 값)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TOPIC = re.compile(
    r"음식|외식|식당|카페|푸드|베이커리|디저트|주점|먹거리|배달|맛집|"
    r"프랜차이즈|상권|매출|임대료|개업|폐업|오픈|자영업|창업|공실|상가|"
    r"가맹점|식음료|권리금|소비|물가"
)


def resolve_path() -> str | None:
    """계약 경로를 먼저 보고, 없으면 수집기가 함께 쓰는 이름을 찾는다."""
    if PATH:
        return PATH
    import os
    for p in DEFAULT_PATHS:
        if os.path.exists(p):
            return p
    return None


def main() -> int:
    path = resolve_path()
    if path is None:
        print(f"미산출: {' / '.join(DEFAULT_PATHS)} 모두 없음 — "
              f"uv run python scripts/scrape_news.py 먼저 실행")
        return 1

    try:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    except FileNotFoundError:
        print(f"미산출: {path} 없음")
        return 1

    errs = []
    for c in COLS:                                          # 1) 필수 컬럼
        if c not in df.columns:
            errs.append(f"컬럼 없음: {c}")

    if not errs:
        if df.empty:                                        # 2) 전량 0건 = 수집 실패
            errs.append("0행 — 수집 실패. 차단(403)·페이지 구조 변경 의심. "
                        "scripts/debug_scrape.py 로 단계별 탈락 사유 확인")
        else:
            for c in COLS + [c for c in OPTIONAL_COLS if c in df.columns]:
                n = df[c].isna().sum()                      # 3) 결측
                if n:
                    errs.append(f"필수 결측: {c} {n}건")

    if not errs:
        # 4) 날짜 형식·90일 이내 (하드코딩 금지 — 실행일 기준 상대 계산)
        bad_fmt = (~df["날짜"].str.match(DATE_RE)).sum()
        if bad_fmt:
            errs.append(f"날짜 형식(YYYY-MM-DD) 위반 {bad_fmt}건 — 날짜 파싱 실패 의심")
        else:
            d = pd.to_datetime(df["날짜"]).dt.date
            cutoff = date.today() - timedelta(days=DAYS)
            old = (d < cutoff).sum()
            if old:
                errs.append(f"{DAYS}일 초과 기사 {old}건 (최고참 {d.min()}) — 기간 필터 미적용")
            future = (d > date.today()).sum()
            if future:
                errs.append(f"미래 날짜 {future}건 — 날짜 파싱 오류")

        # 5) 경제지 화이트리스트 — 서브도메인 허용(biz./view./magazine.)
        pat = "|".join(dom.replace(".", r"\.") for dom in PRESS_DOMAINS)
        off = df.loc[~df["링크"].str.contains(pat, regex=True, na=False)]
        if len(off):
            errs.append(f"화이트리스트 외 도메인 {len(off)}건 "
                        f"(예: {off['링크'].iloc[0][:70]})")

        # 6) 제목 품질 — 1일차 스파이크에서 터진 실패 유형을 그대로 검사로 박는다
        short = (df["제목"].str.len() < MIN_TITLE_LEN).sum()
        if short:
            errs.append(f"제목 {MIN_TITLE_LEN}자 미만 {short}건 — 버튼 라벨 오수집 의심")
        if df["제목"].str.contains("네이버뉴스", na=False).any():
            errs.append("제목에 '네이버뉴스' 포함 — 버튼 라벨 오수집")
        if df["제목"].str.contains("<b>|&amp;|&quot;|&lt;", regex=True, na=False).any():
            errs.append("제목에 HTML 태그·엔티티 잔존 — 저장 전 제거 규약 위반")

        # 7) 중복 (v7 신설) — 같은 기사가 여러 경제지에 배급된다
        dup_link = df["링크"].duplicated().sum()
        dup_title = df["제목"].duplicated().sum()
        if dup_link or dup_title:
            errs.append(f"중복 잔존: 링크 {dup_link}건 · 제목 {dup_title}건 — "
                        f"저장 전 중복 제거 규약 위반")

    if errs:
        print("\n".join(errs))
        return 1

    span = f"{df['날짜'].min()} ~ {df['날짜'].max()}"
    print(f"OK: {path} {len(df):,}행 · 언론사 {df['언론사'].nunique()}곳 · 기간 {span}")

    # ── 아래는 경고 (red 아님) — 육안 확인 대상을 좁혀 준다 ──────────────
    text = df["제목"].fillna("") + " " + df.get("요약", pd.Series("", index=df.index)).fillna("")
    off_topic = (~text.str.contains(TOPIC, regex=True)).sum()
    if off_topic:
        print(f"⚠️ 경고(red 아님): 음식·창업 키워드가 없는 기사 {off_topic}건 — "
              f"목록을 눈으로 확인할 것 (게이트는 형식만 본다)")
    if len(df) < 10:
        print(f"⚠️ 경고(red 아님): {len(df)}건뿐 — 시연 화면이 빈약해 보일 수 있다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
