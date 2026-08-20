# seams/check_news.py — 뉴스 담당 → C조 인계 검증
# DEV_SPEC §4 아티팩트 3 계약을 그대로 검사로 옮긴 것.
# 계약에 없는 검사를 추가하고 싶으면 문서에 먼저 넣는다.
#
# news.csv는 "비어 있어도 정상"인 유일한 아티팩트다 —
# 기사가 없는 상권은 앱에서 "최근 3개월 관련 기사 없음"으로 표시된다.
# 따라서 이 검사는 행 수 하한이 아니라 **담긴 행이 계약을 지키는지**를 본다.
# 다만 전량 0건이면 수집 실패이므로 red.
#
# 사용: uv run python seams/check_news.py [news경로] [scores경로]
#   mock끼리 대조: uv run python seams/check_news.py data/mock/news.csv
#   (scores 경로를 생략하면 news와 같은 디렉터리의 scores.csv를 본다)
import os
import re
import sys
from datetime import date, timedelta

import pandas as pd

PATH = sys.argv[1] if len(sys.argv) > 1 else "data/news.csv"
SCORES = (sys.argv[2] if len(sys.argv) > 2
          else os.path.join(os.path.dirname(PATH) or ".", "scores.csv"))

COLS = ["상권_코드", "행정동_base", "제목", "언론사", "날짜", "링크"]
PRESS_DOMAINS = {                       # DEV_SPEC §4 아티팩트 3 · 경제지 화이트리스트
    "hankyung.com", "mk.co.kr", "sedaily.com", "mt.co.kr",
    "asiae.co.kr", "fnnews.com", "edaily.co.kr",
}
DAYS = 90
PER_AREA = 3
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def main() -> int:
    try:
        df = pd.read_csv(PATH, encoding="utf-8-sig", dtype=str)
    except FileNotFoundError:
        print(f"미산출: {PATH} 없음 — 3일차 저녁 이후면 red")
        return 1

    errs = []
    for c in COLS:                                          # 1) 컬럼 존재
        if c not in df.columns:
            errs.append(f"컬럼 없음: {c}")

    if not errs:
        if df.empty:                                        # 2) 전량 0건 = 수집 실패
            errs.append("0행 — 전 지역 수집 실패. 스크래핑 차단·구조 변경 의심, "
                        "백업 경로(collect_news.py) 확인")
        else:
            for c in COLS:                                  # 3) 결측
                n = df[c].isna().sum()
                if n:
                    errs.append(f"필수 결측: {c} {n}건")

    if not errs:
        # 4) 날짜 형식·90일 이내 (하드코딩 금지 — 실행일 기준 상대 계산)
        bad_fmt = (~df["날짜"].str.match(DATE_RE)).sum()
        if bad_fmt:
            errs.append(f"날짜 형식(YYYY-MM-DD) 위반 {bad_fmt}건 — "
                        f"'N일 전' 파싱 실패 의심")
        else:
            d = pd.to_datetime(df["날짜"]).dt.date
            cutoff = date.today() - timedelta(days=DAYS)
            old = (d < cutoff).sum()
            if old:
                errs.append(f"{DAYS}일 초과 기사 {old}건 (최고참 {d.min()}) — "
                            f"기간 필터 미적용")
            future = (d > date.today()).sum()
            if future:
                errs.append(f"미래 날짜 {future}건 — 날짜 파싱 오류")

        # 5) 경제지 화이트리스트 — 링크 도메인으로 판정
        off = df.loc[~df["링크"].str.contains("|".join(
            dom.replace(".", r"\.") for dom in PRESS_DOMAINS), regex=True)]
        if len(off):
            errs.append(f"화이트리스트 외 도메인 {len(off)}건 (예: {off['링크'].iloc[0][:60]})")

        # 6) 제목 품질 — 스파이크에서 터진 실패 유형을 그대로 검사로 박는다
        short = (df["제목"].str.len() < 15).sum()
        if short:
            errs.append(f"제목 15자 미만 {short}건 — 버튼 라벨 오수집 의심")
        if (df["제목"].str.contains("네이버뉴스")).any():
            errs.append("제목에 '네이버뉴스' 포함 — 버튼 라벨 오수집")
        if df["제목"].str.contains("<b>|&amp;|&quot;|&lt;", regex=True).any():
            errs.append("제목에 HTML 태그·엔티티 잔존 — 저장 전 제거 규약 위반")

        # 7) 지역당 상위 3건
        over = (df.groupby(["행정동_base", "상권_코드"]).size() > PER_AREA).sum()
        if over:
            errs.append(f"지역당 {PER_AREA}건 초과 {over}개 조합")

        # 8) 상권_코드가 scores.csv 안에 있는지 (C조가 조인하는 키)
        try:
            sc = pd.read_csv(SCORES, encoding="utf-8-sig", dtype={"상권_코드": str})
            orphan = set(df["상권_코드"]) - set(sc["상권_코드"])
            if orphan:
                errs.append(f"scores.csv에 없는 상권_코드 {len(orphan)}개 "
                            f"(예: {sorted(orphan)[:3]}) — 조인 시 유실")
        except FileNotFoundError:
            errs.append(f"참조 실패: {SCORES} 없음 — scores 산출 후 다시 실행")

    if errs:
        print("\n".join(errs))
        return 1

    cov = df["상권_코드"].nunique()
    print(f"OK: {PATH} {len(df):,}행 · 상권 {cov}개 · 지역 {df['행정동_base'].nunique()}개 "
          f"· 언론사 {df['언론사'].nunique()}곳 · 최신 {df['날짜'].max()}")
    if cov < 30:
        print(f"⚠️ 경고(red 아님): 기사가 붙은 상권 {cov}개 — 시연 상권에 기사가 있는지 확인할 것")
    return 0


if __name__ == "__main__":
    sys.exit(main())
