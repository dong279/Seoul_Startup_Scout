"""scripts/make_mock.py — 계약대로 생긴 가짜 데이터 생성 (팀장 전담).

목적은 **병렬 착수**다. 하류(EDA 4~6·앱·뉴스)가 B조의 실물 산출을 기다리지 않고
첫 시간부터 달리게 한다. 실물 전환은 경로만 바꾸면 끝이다 — 스키마가 같으므로.

실물과 **분포가 아니라 형태**만 같다. 결측·이상치를 일부러 섞어 두므로
하류는 "빈 결과", "동점", "극단값" 같은 상태를 미리 만나게 된다.

행 수를 계약 하한(2,000) 이상으로 만들기 때문에 mock으로도 게이트가 green이 된다.
즉 C조는 실물 전에 `check_scores.py`·`check_app.py`를 통과시킬 수 있다.

사용:  uv run python scripts/make_mock.py
출력:  data/mock/scores.csv · data/mock/news.csv · data/mock/industry_trend.csv
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

N_SANGWON = 1_300
N_ROWS = 2_500
SEED = 20260820

JONG = ["한식음식점", "중식음식점", "일식음식점", "양식음식점", "분식전문점",
        "패스트푸드점", "제과점", "커피-음료", "치킨전문점", "호프-간이주점",
        "반찬가게"]                                    # 확정 11종 (DEV_SPEC §5-1)
TYPES = ["유입 집중형", "청년 밀집형", "가족 주거형", "일반 주거·생활형",
         "발달상권형", "전통시장형", "관광특구형"]      # 확정 7종 (§5-2)
GUBUN = ["골목상권", "발달상권", "전통시장", "관광특구"]
QUARTERS = ["20251", "20252", "20253", "20254", "20261"]   # 제공 5분기 (§2)
PRESS = {"한국경제": "hankyung.com", "매일경제": "mk.co.kr",
         "서울경제": "sedaily.com", "머니투데이": "mt.co.kr"}


def make_scores(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for i in range(N_ROWS):
        s = i % N_SANGWON
        rows.append({
            "상권_코드": f"{3_000_000 + s:07d}",
            "상권_코드_명": f"목상권{s}",
            "서비스_업종_코드": f"CS{100_000 + i % 11:06d}",
            "서비스_업종_코드_명": JONG[i % 11],
            "상권_구분_코드_명": GUBUN[s % 4],
            "자치구_코드_명": f"목구{s % 25}",
            "행정동_코드": f"{11_000_000 + s % 396:08d}",
            "행정동_코드_명": f"목{s % 396}동",
            "유형": TYPES[s % 7],
            "유효수요": rng.beta(2, 3),          # §5-3 결과 — 0~1, 산점도 x축
            "공급밀도": rng.uniform(1, 50),
            "동일유형_중앙_공급밀도": rng.uniform(20, 60),
            "공급갭": rng.uniform(0.01, 0.9),
            "행정동_폐업률": rng.uniform(0, 8),
            "전체_점포_수": int(rng.integers(5, 200)),
            "당월_매출_금액": int(rng.integers(1e6, 1e9)),
            "당월_매출_건수": int(rng.integers(100, 50_000)),
        })
    df = pd.DataFrame(rows)

    # 이상치를 일부러 섞는다 — 하류가 이걸로 일한다
    df.loc[0, "공급갭"] = 0.999                       # 극단 상위
    df.loc[6, "유효수요"] = 0.998                     # 산점도 우측 극단
    df.loc[7, "유효수요"] = 0.002                     # 산점도 좌측 극단
    df.loc[1, "행정동_폐업률"] = 0.0                   # 폐업률 0 (안정성 만점)
    df.loc[2:5, "행정동_폐업률"] = df.loc[2, "행정동_폐업률"]  # 동점 — 정렬 안정성 시험

    mm = lambda s: (s - s.min()) / (s.max() - s.min())   # noqa: E731
    df["갭점수"] = mm(df["공급갭"])
    df["안정성점수"] = 1 - mm(df["행정동_폐업률"])        # 방향 반전 (§5-5)
    df["종합점수"] = 0.6 * df["갭점수"] + 0.4 * df["안정성점수"]
    return df


def make_news(scores: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """상위 상권 중 **일부에만** 기사를 붙인다.
    기사 없는 상권이 정상 상태이므로, 앱이 그 경우를 반드시 만나게 만든다."""
    top = (scores.sort_values("종합점수", ascending=False)
                 .drop_duplicates("상권_코드").head(100))
    today = date.today()
    rows = []
    for i, r in enumerate(top.itertuples()):
        if i % 3 == 0:                                # 1/3만 기사 보유
            continue
        for k in range(int(rng.integers(1, 4))):      # 1~3건
            press, dom = list(PRESS.items())[k % 4]
            rows.append({
                "상권_코드": r.상권_코드,
                "행정동_base": r.행정동_코드_명,
                "제목": f"서울 {r.행정동_코드_명} 상권 임대료 동향 분석 결과 {i}-{k}",
                "언론사": press,
                "날짜": str(today - timedelta(days=int(rng.integers(0, 89)))),
                "링크": f"https://{dom}/article/{i}{k}",
            })
    return pd.DataFrame(rows)


def make_trend(rng: np.random.Generator) -> pd.DataFrame:
    """아티팩트 5 — 업종별 서울시 전체 개·폐업률 추이 (11종 × 5분기 = 55행).

    상세 패널의 참고 표시용이다. 계산에 들어가지 않으므로 분포는 아무래도 좋고,
    **업종명 표기가 화이트리스트와 정확히 같은지**만 중요하다 —
    한 글자라도 다르면 C1의 조회가 조용히 빈 결과가 된다.
    """
    rows = []
    for jong in JONG:
        base_open = rng.uniform(1.2, 3.5)      # 업종마다 기준선이 다르게
        base_close = rng.uniform(1.0, 3.0)
        for i, q in enumerate(QUARTERS):
            rows.append({
                "서비스_업종_코드_명": jong,
                "기준_년분기_코드": q,
                "개업률": round(base_open + rng.normal(0, 0.25), 2),
                "폐업률": round(base_close + rng.normal(0, 0.25) + i * 0.05, 2),
            })
    return pd.DataFrame(rows)


def main() -> int:
    rng = np.random.default_rng(SEED)
    os.makedirs("data/mock", exist_ok=True)

    scores = make_scores(rng)
    scores.to_csv("data/mock/scores.csv", index=False, encoding="utf-8-sig")

    news = make_news(scores, rng)
    news.to_csv("data/mock/news.csv", index=False, encoding="utf-8-sig")

    trend = make_trend(rng)
    trend.to_csv("data/mock/industry_trend.csv", index=False, encoding="utf-8-sig")

    print(f"data/mock/scores.csv: {len(scores):,}행 · 유형 {scores['유형'].nunique()}종 "
          f"· 업종 {scores['서비스_업종_코드'].nunique()}종")
    print(f"data/mock/news.csv:   {len(news):,}행 · "
          f"기사 보유 상권 {news['상권_코드'].nunique()}개 (나머지는 '기사 없음')")
    print(f"data/mock/industry_trend.csv: {len(trend)}행 · "
          f"업종 {trend['서비스_업종_코드_명'].nunique()}종 × "
          f"분기 {trend['기준_년분기_코드'].nunique()}개")
    print("\n게이트를 mock으로 돌리려면 경로를 인자로 준다:")
    print("  uv run python seams/check_scores.py data/mock/scores.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
