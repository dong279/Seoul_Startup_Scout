"""scripts/build_scores.py — 2단계 산출물 data/scores.csv 생성 (B조).

DEV_SPEC §5 분석 규약을 순서대로 구현한다. 적용 순서가 계약이다.
  5-1 업종 한정(확정 11종) → 5-2 유형 분류(7종) → 5-3 유효수요·공급밀도
  → 5-4 공급갭(>0만 유지) → 5-5 안정성(행정동) → 5-6 종합점수

실행: python scripts/build_scores.py
검증: python seams/check_scores.py
"""
from __future__ import annotations
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.loader import load_master, load_whitelist, QUARTERS_4, safe_ratio  # noqa: E402

SNAPSHOT = "20261"          # scores는 최신 분기 스냅샷 (시계열 아님)
W_POP = (1, 1, 1)           # 유효수요 가중치 w_r : w_w : w_f  ← 회의 확정값
W_SCORE = (0.6, 0.4)        # 종합점수 기본 가중치 (갭 : 안정성) ← 앱 슬라이더가 덮어씀
PRE = {"발달상권": "발달상권형", "전통시장": "전통시장형", "관광특구": "관광특구형"}


def minmax(s: pd.Series) -> pd.Series:
    return (s - s.min()) / (s.max() - s.min())


def log_norm(s: pd.Series) -> pd.Series:
    """로그 변환 후 0~1 정규화.

    직장인구는 중앙값 494인데 최대 199,667(404배)이라 원단위 min-max로는
    정규화값 중앙값이 0.0025가 되어 지표에서 사라진다. 로그가 필수다.
    """
    return minmax(np.log1p(s))


def classify(g: pd.DataFrame) -> pd.Series:
    """유형 분류 — 골목상권만. 위에서부터 첫 매칭 (적용 순서가 계약)."""
    i75, i50, i25 = g["유입강도"].quantile([0.75, 0.5, 0.25])
    y75 = g["청년비율"].quantile(0.75)
    h50 = g["가구당인구"].quantile(0.5)
    out = pd.Series("일반 주거·생활형", index=g.index)
    out[(g["유입강도"] < i50) & (g["가구당인구"] >= h50)] = "가족 주거형"
    out[(g["유입강도"].between(i25, i75, inclusive="left")) & (g["청년비율"] >= y75)] = "청년 밀집형"
    out[g["유입강도"] >= i75] = "유입 집중형"
    return out


def main() -> int:
    m = load_master()
    jong = load_whitelist()

    # --- 5-2 유형 분류: 상권 단위 1행으로 축소 후 계산 (복제 상태로 분위수 계산 금지) ---
    snap = m[m["기준_년분기_코드"] == SNAPSHOT]
    u = snap.drop_duplicates("상권_코드").copy()
    u["유입강도"] = safe_ratio(u["총_유동인구_수"], u["총_상주인구_수"])
    u["가구당인구"] = safe_ratio(u["총_상주인구_수"], u["총_가구_수"])
    u["청년비율"] = safe_ratio(u["연령대_20_상주인구_수"] + u["연령대_30_상주인구_수"],
                            u["총_상주인구_수"])
    u = u.dropna(subset=["유입강도", "가구당인구", "청년비율"])

    u["유형"] = u["상권_구분_코드_명"].map(PRE)          # 선처리 3종
    gol = u[u["유형"].isna()].copy()                    # 골목상권만 규칙 분류
    u.loc[gol.index, "유형"] = classify(gol)

    # --- 5-3 유효수요 (인구 3종 로그 정규화 가중합) ---
    wr, ww, wf = W_POP
    u["유효수요"] = (wr * log_norm(u["총_상주인구_수"])
                 + ww * log_norm(u["총_직장_인구_수"])
                 + wf * log_norm(u["총_유동인구_수"])) / (wr + ww + wf)

    # --- 5-5 안정성: 행정동 4분기 폐업률 (분자·분모 각각 합산) ---
    q4 = m[m["기준_년분기_코드"].isin(QUARTERS_4)& m["서비스_업종_코드_명"].isin(jong)]
    hd = (q4.groupby("행정동_코드")
            .apply(lambda x: x["폐업_점포_수"].sum() / x["전체_점포_수"].sum() * 100,
                   include_groups=False)
            .rename("행정동_폐업률"))

    # --- 5-1 업종 한정 + 조합 단위 조립 ---
    s = snap[snap["서비스_업종_코드_명"].isin(jong)].copy()
    s = s.merge(u[["상권_코드", "유형", "유효수요"]], on="상권_코드", how="inner")
    s = s.merge(hd, on="행정동_코드", how="left")
    s = s.dropna(subset=["행정동_폐업률"])

    # --- 5-4 공급갭 ---
    s["공급밀도"] = (s["전체_점포_수"] / s["유효수요"]).round(3)
    s["동일유형_중앙_공급밀도"] = (s.groupby(["유형", "서비스_업종_코드"])["공급밀도"]
                          .transform("median").round(3))
    s["공급갭"] = ((s["동일유형_중앙_공급밀도"] - s["공급밀도"])
                / s["동일유형_중앙_공급밀도"]).round(4)
    s = s.dropna(subset=["공급갭"])

    # scores.csv 는 후보 목록이다 — 공급 과잉 조합은 담지 않는다.
    # (필터 없이 점수만으로 뽑으면 상위 100개 중 43개가 공급갭 <= 0 이었다)
    s = s[s["공급갭"] > 0].copy()

    # --- 5-6 점수화 (방향 통일: 셋 다 높을수록 좋음) ---
    s["갭점수"] = s.groupby("유형")["공급갭"].transform(minmax).round(4)
    s["안정성점수"] = (1 - minmax(s["행정동_폐업률"])).round(4)   # 반전 필수
    wg, ws = W_SCORE
    s["종합점수"] = (wg * s["갭점수"] + ws * s["안정성점수"]).round(4)

    out = s[["상권_코드", "상권_코드_명", "서비스_업종_코드", "서비스_업종_코드_명", "유효수요",
             "상권_구분_코드_명", "유형", "자치구_코드_명", "행정동_코드", "행정동_코드_명",
             "공급밀도", "동일유형_중앙_공급밀도", "공급갭", "행정동_폐업률",
             "갭점수", "안정성점수", "종합점수",
             "전체_점포_수", "당월_매출_금액", "당월_매출_건수"]].copy()

    os.makedirs("data", exist_ok=True)
    out.to_csv("data/scores.csv", index=False, encoding="utf-8-sig")
    print(f"scores.csv: {len(out):,}행(후보) · 유형 {out['유형'].nunique()}종 "
          f"· 업종 {out['서비스_업종_코드'].nunique()}종 · 상권 {out['상권_코드'].nunique():,}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
