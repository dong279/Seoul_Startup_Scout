# seams/check_app.py — C조 앱 로직 게이트
# 화면을 검사하지 않는다. app/logic.py의 함수가 DEV_SPEC 계약대로 동작하는지만 본다.
# 이 파일이 있어야 C조 에이전트 지시서의 [수용 기준]을 기계 검사로 쓸 수 있다.
#
# 사용: uv run python seams/check_app.py [scores경로] [news경로]
#   mock으로 선착수: uv run python seams/check_app.py data/mock/scores.csv data/mock/news.csv
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    errs = []

    try:
        from app import logic
    except Exception as e:                                   # noqa: BLE001
        print(f"import 실패: app/logic.py — {e}")
        return 1

    # 0) 로직 모듈은 streamlit에 의존하지 않는다 (분리의 전제)
    src = open(os.path.join(os.path.dirname(__file__), "..", "app", "logic.py"),
               encoding="utf-8").read()
    if "import streamlit" in src:
        errs.append("app/logic.py가 streamlit을 import — UI와 로직 분리 규약 위반")

    scores_path = sys.argv[1] if len(sys.argv) > 1 else logic.SCORES_PATH
    news_path = sys.argv[2] if len(sys.argv) > 2 else logic.NEWS_PATH
    try:
        df = logic.load_scores(scores_path)
    except FileNotFoundError:
        print(f"미산출: {scores_path} 없음 — B조 산출 전이면 "
              f"data/mock/scores.csv 로 먼저 돌린다")
        return 1

    # 1) 기본 가중치로 재계산한 값이 scores.csv의 종합점수와 일치해야 한다
    #    → build_scores.py와 app/logic.py가 같은 공식을 쓰는지의 기계 검사
    base = logic.rescore(df, 0.6, 0.4)
    merged = df.merge(base[["상권_코드", "서비스_업종_코드", "종합점수"]],
                      on=["상권_코드", "서비스_업종_코드"], suffixes=("_파일", "_재계산"))
    d = (merged["종합점수_파일"] - merged["종합점수_재계산"]).abs().max()
    if pd.isna(d) or d > 1e-9:
        errs.append(f"기본 가중치(0.6:0.4) 재계산이 파일값과 불일치 (최대차 {d}) — "
                    f"build_scores.py와 공식이 다르다")

    # 2) 극단 가중치에서 순위가 해당 지표 단독 순위와 같아야 한다
    for w, col in [((1.0, 0.0), "갭점수"), ((0.0, 1.0), "안정성점수")]:
        got = logic.rescore(df, *w).head(20)["상권_코드"].tolist()
        want = df.sort_values(col, ascending=False, kind="mergesort") \
                 .head(20)["상권_코드"].tolist()
        if got != want:
            errs.append(f"가중치 {w}에서 {col} 단독 순위와 불일치 — 가중합 구현 확인")

    # 3) 슬라이더를 둘 다 0으로 내려도 죽지 않는다
    try:
        logic.rescore(df, 0.0, 0.0)
    except Exception as e:                                   # noqa: BLE001
        errs.append(f"가중치 (0,0)에서 예외: {e} — 분모 0 방어 누락")

    # 4) 필터는 부분집합이고, 조건을 만족하며, 빈 결과에서도 죽지 않는다
    t = df["유형"].iloc[0]
    j = df["서비스_업종_코드_명"].iloc[0]
    sub = logic.filter_candidates(df, 업종=[j], 유형=[t])
    if not set(sub.index) <= set(df.index):
        errs.append("filter_candidates 결과가 부분집합이 아니다")
    if len(sub) and not (sub["유형"].eq(t).all() and sub["서비스_업종_코드_명"].eq(j).all()):
        errs.append("filter_candidates 결과가 조건을 만족하지 않는다")
    if len(logic.filter_candidates(df, 업종=[j], 유형=["존재하지_않는_유형"])):
        errs.append("없는 조건에 결과가 나온다")
    try:
        s = logic.summary(logic.filter_candidates(df, 유형=["존재하지_않는_유형"]))
        if s["후보_수"] != 0:
            errs.append("빈 결과의 summary 후보_수가 0이 아니다")
    except Exception as e:                                   # noqa: BLE001
        errs.append(f"빈 결과 summary에서 예외: {e} — 빈 상태 처리 누락")

    # 5) 뉴스 없는 상권은 예외가 아니라 빈 결과다
    news = logic.load_news(news_path)
    try:
        empty = logic.news_for(news, "0000000")
        if len(empty):
            errs.append("존재하지 않는 상권_코드에 기사가 반환된다")
    except Exception as e:                                   # noqa: BLE001
        errs.append(f"기사 없는 상권에서 예외: {e} — '기사 없음'은 정상 상태다")

    # 6) 역방향 탐색은 해당 상권만, N건 이하
    code = df["상권_코드"].iloc[0]
    rev = logic.reverse_lookup(logic.rescore(df), code, n=5)
    if len(rev) > 5 or (len(rev) and not rev["상권_코드"].eq(code).all()):
        errs.append("reverse_lookup 결과가 상권/건수 조건 위반")

    if errs:
        print("\n".join(errs))
        return 1
    print(f"OK: app/logic.py 계약 준수 · {scores_path} {len(df):,}행 · "
          f"뉴스 {len(news):,}행 · 가중치 재계산 일치")
    return 0


if __name__ == "__main__":
    sys.exit(main())
