# seams/check_master.py — 1단계(전원) → 2단계(B·C조) 인계 검증
# v3 (킥오프 확정 반영):
#   - 지도 제외 → 위도·경도 검사 삭제
#   - 행정동_코드 결측 검사 추가 (행정동 단위 폐업률의 유일한 출처)
#   - 아파트_가구_수 검사 삭제 (전 행 0으로 계약에서 제외)
#   - 유효수요·공급밀도 검사는 scores 단계로 이동 (인구 3종 가중 통합 확정 후)
# DEV_SPEC §4 아티팩트1 계약을 그대로 검사로 옮긴 것.
# 계약에 없는 검사를 추가하고 싶으면 문서에 먼저 넣는다.
# 사용: python seams/check_master.py [경로] 으악
import sys
import pandas as pd

PATH = sys.argv[1] if len(sys.argv) > 1 else "data/master.csv"
KEY = ["기준_년분기_코드", "상권_코드", "서비스_업종_코드"]
STR_COLS = KEY + ["상권_구분_코드", "상권_구분_코드_명", "상권_코드_명",
                  "서비스_업종_코드_명", "자치구_코드", "자치구_코드_명",
                  "행정동_코드", "행정동_코드_명"]
REQ_NUM = ["전체_점포_수", "프랜차이즈_점포_수", "폐업_률", "폐업_점포_수", "개업_율",
           "당월_매출_금액", "당월_매출_건수", "주중_매출_건수", "주말_매출_건수",
           "총_상주인구_수", "총_유동인구_수", "총_가구_수",
           "연령대_20_상주인구_수", "연령대_30_상주인구_수"]
QUARTERS = {"20251", "20252", "20253", "20254", "20261"}
MIN_ROWS = 100_000  # 실측 106,466행 기준 하한


def main() -> int:
    try:  # 1) 파일 존재
        df = pd.read_csv(PATH, encoding="utf-8-sig", dtype={c: str for c in STR_COLS})
    except FileNotFoundError:
        print(f"미산출: {PATH} 없음 — 1단계 완료 전이면 정상, 2일차 오전 이후면 red")
        return 1

    errs = []
    for c in STR_COLS + REQ_NUM:                      # 2) 컬럼 존재
        if c not in df.columns:
            errs.append(f"컬럼 없음: {c}")
    if not errs:
        for c in KEY + REQ_NUM:                       # 3) 결측 (타입 검사보다 먼저)
            n = df[c].isna().sum()
            if n:
                errs.append(f"필수 결측: {c} {n}건")
        n = df["행정동_코드"].isna().sum()             # 행정동 폐업률의 유일한 출처
        if n:
            errs.append(f"행정동_코드 결측 {n}건 — 영역-상권 조인 실패 의심. "
                        f"이 파일엔 기준_년분기_코드가 없다: on='상권_코드' 단일 키로 조인할 것")
    if not errs:                                      # 4) 값 형식·유일성·규모
        if df.duplicated(subset=KEY).any():
            errs.append(f"유일 키 중복: {df.duplicated(subset=KEY).sum()}건")
        if not set(df["기준_년분기_코드"].unique()) <= QUARTERS:
            errs.append(f"허용 외 분기: {set(df['기준_년분기_코드'].unique()) - QUARTERS}")
        if df["상권_코드"].str.len().ne(7).any():
            errs.append("상권_코드 7자리 아님 — dtype=str 누락으로 앞자리 소실 의심")
        if not df["서비스_업종_코드"].str.match(r"^CS\d{6}$").all():
            errs.append("서비스_업종_코드 형식(CS######) 위반")
        if (df["총_상주인구_수"] <= 0).any():
            errs.append(f"총_상주인구_수 0 이하 {(df['총_상주인구_수'] <= 0).sum()}건 — 유입강도 분모")
        if (df["총_가구_수"] <= 0).any():
            errs.append(f"총_가구_수 0 이하 {(df['총_가구_수'] <= 0).sum()}건 — 가구당인구 분모")
        if not df["폐업_률"].between(0, 300).all():
            errs.append("폐업_률 범위(0~300) 벗어남")
        if len(df) < MIN_ROWS:
            errs.append(f"행 수 미달: {len(df):,} < {MIN_ROWS:,}")

    if errs:
        print("\n".join(errs)); return 1
    print(f"OK: {PATH} {len(df):,}행 · 상권 {df['상권_코드'].nunique()}개 "
          f"· 업종 {df['서비스_업종_코드'].nunique()}종 · 행정동 {df['행정동_코드'].nunique()}개 "
          f"· 분기 {df['기준_년분기_코드'].nunique()}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
