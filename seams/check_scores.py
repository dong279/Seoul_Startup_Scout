# seams/check_scores.py — B조 → C조 인계 검증
# v3 (킥오프 확정 반영):
#   - 수요적합도 제외 → 지표 2종(갭·안정성)
#   - 후보_인정 컬럼 폐지 → scores.csv는 공급갭 > 0 인 행만 담는다 (파일 자체가 후보 목록)
#   - 폐업률은 행정동 단위 (평균_폐업률_4분기 → 행정동_폐업률)
#   - 지도 제외 → 위도·경도 검사 삭제
#   - 유형 4종 (주중집중도 축 제외로 오피스/상업번화 통합 → 유입 집중형)
# DEV_SPEC §4 아티팩트2 계약 대응. 최신 분기(20261) 스냅샷.
# 사용: python seams/check_scores.py [경로]
import sys
import pandas as pd

PATH = sys.argv[1] if len(sys.argv) > 1 else "data/scores.csv"
KEY = ["상권_코드", "서비스_업종_코드"]
STR_COLS = KEY + ["상권_코드_명", "서비스_업종_코드_명", "상권_구분_코드_명",
                  "유형", "자치구_코드_명", "행정동_코드", "행정동_코드_명"]
NUM_COLS = ["공급밀도", "동일유형_중앙_공급밀도", "공급갭",
            "행정동_폐업률", "갭점수", "안정성점수", "종합점수"]
TYPES = {"유입 집중형", "청년 밀집형", "가족 주거형", "일반 주거·생활형",
         "발달상권형", "전통시장형", "관광특구형"}
JONG = 11          # 확정 업종 수
MIN_ROWS = 2_000   # 업종 11종 · 공급갭>0 필터 후 실측 3,443건 기준 하한


def main() -> int:
    try:
        df = pd.read_csv(PATH, encoding="utf-8-sig", dtype={c: str for c in STR_COLS})
    except FileNotFoundError:
        print(f"미산출: {PATH} 없음 — B조 산출 전이면 정상, 3일차 저녁 이후면 red")
        return 1

    errs = []
    for c in STR_COLS + NUM_COLS:                       # 1) 컬럼 존재
        if c not in df.columns:
            errs.append(f"컬럼 없음: {c}")
    if not errs:
        for c in KEY + NUM_COLS + ["유형"]:              # 2) 결측
            n = df[c].isna().sum()
            if n:
                errs.append(f"필수 결측: {c} {n}건")
    if not errs:                                        # 3) 값 형식·유일성·규모
        if df.duplicated(subset=KEY).any():
            errs.append(f"유일 키 중복: {df.duplicated(subset=KEY).sum()}건")
        bad = set(df["유형"].unique()) - TYPES
        if bad:
            errs.append(f"정의 외 유형: {bad}")
        # 이 파일은 후보 목록이다 — 공급 과잉 조합이 섞이면 프로젝트 목적과 어긋난다
        if (df["공급갭"] <= 0).any():
            errs.append(f"공급갭 0 이하 {(df['공급갭'] <= 0).sum()}건 — "
                        f"scores.csv는 공급갭 > 0 인 행만 담는다")
        if df["서비스_업종_코드"].nunique() > JONG:
            errs.append(f"확정 업종 수 초과: {df['서비스_업종_코드'].nunique()} > {JONG} "
                        f"— config/업종_whitelist.csv 적용 확인")
        for c in ["갭점수", "안정성점수", "종합점수"]:      # 방향 통일 검사
            if not df[c].between(0, 1).all():
                errs.append(f"{c} 0~1 범위 벗어남 (min-max 정규화 확인)")
        # 안정성 방향 반전 검사: 폐업률과 안정성점수는 음의 관계여야 한다
        corr = df["행정동_폐업률"].corr(df["안정성점수"])
        if pd.notna(corr) and corr > 0:
            errs.append(f"안정성점수 방향 오류: 폐업률과 양의 상관({corr:.2f}) — "
                        f"'1 - 정규화' 반전 누락")
        if len(df) < MIN_ROWS:
            errs.append(f"행 수 미달: {len(df):,} < {MIN_ROWS:,}")

    if errs:
        print("\n".join(errs)); return 1
    print(f"OK: {PATH} {len(df):,}행(후보) · 유형 {df['유형'].nunique()}종 "
          f"· 업종 {df['서비스_업종_코드'].nunique()}종 · 상권 {df['상권_코드'].nunique()}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
