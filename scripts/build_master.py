"""scripts/build_master.py — 1단계 산출물 data/master.csv 생성.

v4 (킥오프 확정 반영):
  - 직장인구-상권 추가 (인구 3종 가중 통합용)
  - 지도 제외 → 좌표 변환·pyproj 삭제
  - 영역-상권은 행정동_코드·자치구_코드_명만 사용 (행정동 폐업률의 유일한 출처)
  - 아파트_가구_수 제외 (21개 분기 전 상권 0)
  - 유효수요·공급밀도는 build_scores.py에서 산출 (가중치가 분석 규약에 속하므로)

원본 CSV를 data/raw/ 에 두고 실행: python scripts/build_master.py
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.loader import load, QUARTERS  # noqa: E402

POP_COLS = ["기준_년분기_코드", "상권_코드", "총_상주인구_수", "총_가구_수",
            "연령대_10_상주인구_수", "연령대_20_상주인구_수", "연령대_30_상주인구_수",
            "연령대_40_상주인구_수", "연령대_50_상주인구_수", "연령대_60_이상_상주인구_수"]
WORK_COLS = ["기준_년분기_코드", "상권_코드", "총_직장_인구_수"]
FLOW_COLS = ["기준_년분기_코드", "상권_코드", "총_유동인구_수"]
AREA_COLS = ["상권_코드", "자치구_코드", "자치구_코드_명",
             "행정동_코드", "행정동_코드_명", "영역_면적"]


def main() -> None:
    st = load("점포-상권")
    sal = load("추정매출-상권")
    pop = load("상주인구-상권")
    work = load("직장인구-상권")
    flo = load("길단위인구-상권")
    area = load("영역-상권")

    # 인구 3종은 21개 분기를 담고 있다 → 분석 구간으로 자른다
    pop = pop[pop["기준_년분기_코드"].isin(QUARTERS)]
    work = work[work["기준_년분기_코드"].isin(QUARTERS)]
    flo = flo[flo["기준_년분기_코드"].isin(QUARTERS)]

    key3 = ["기준_년분기_코드", "상권_코드", "서비스_업종_코드"]
    key2 = ["기준_년분기_코드", "상권_코드"]

    # 점포 × 매출: inner — 매출이 커버하는 업종(실측 62종)만 남는 것이 의도된 동작
    m = st.merge(sal.drop(columns=["상권_구분_코드", "상권_구분_코드_명",
                                   "상권_코드_명", "서비스_업종_코드_명"]),
                 on=key3, how="inner")

    m = m.merge(pop[POP_COLS], on=key2, how="left")
    m = m.merge(work[WORK_COLS], on=key2, how="left")
    m = m.merge(flo[FLOW_COLS], on=key2, how="left")

    # 영역-상권에는 기준_년분기_코드가 없다(상권당 1행) → 단일 키 조인. 실측 결측 0.
    m = m.merge(area[AREA_COLS], on="상권_코드", how="left")

    # 인구 3종 중 하나라도 없으면 유효수요를 만들 수 없다 → 제거
    before = m["상권_코드"].nunique()
    m = m[m["총_상주인구_수"].notna() & m["총_유동인구_수"].notna()
          & m["총_직장_인구_수"].notna()].copy()
    dropped = before - m["상권_코드"].nunique()

    os.makedirs("data", exist_ok=True)
    m.to_csv("data/master.csv", index=False, encoding="utf-8-sig")
    print(f"master.csv: {len(m):,}행 × {len(m.columns)}컬럼 · "
          f"상권 {m['상권_코드'].nunique():,} · 업종 {m['서비스_업종_코드'].nunique()} · "
          f"행정동 {m['행정동_코드'].nunique()} · 인구 미매칭 제거 {dropped}개 상권")


if __name__ == "__main__":
    main()
