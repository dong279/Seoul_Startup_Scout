"""common/loader.py — 원본 CSV 로더.

모든 원본 읽기는 이 모듈을 통한다. 개별 pd.read_csv 직접 호출 금지
(인코딩·dtype 누락이 조인 실패의 최대 원인).
"""
from __future__ import annotations
import os
import pandas as pd

RAW_DIR = "data/raw/"
ENCODING = "cp949"

# 코드 컬럼은 반드시 문자열. 정수로 읽히면 앞자리 0이 소실되어 조인이 깨진다.
KEY_DTYPES = {
    "상권_코드": str, "서비스_업종_코드": str, "기준_년분기_코드": str,
    "자치구_코드": str, "행정동_코드": str, "상권_구분_코드": str, "서울시_코드": str,
}

# 분석 대상 분기 (상권×업종 데이터 제공 구간). 문자열 산술 금지 — 이 리스트의 인덱스로만 처리.
QUARTERS = ["20251", "20252", "20253", "20254", "20261"]
QUARTERS_4 = ["20252", "20253", "20254", "20261"]   # 폐업률 4분기 평균용


def load(name: str, raw_dir: str = RAW_DIR, **kw) -> pd.DataFrame:
    """서울시 상권분석서비스 CSV를 읽는다. 두 가지 파일명 형식을 모두 허용:
    ① 서울시_상권분석서비스_{name}_.csv   ② 서울시 상권분석서비스({name}).csv (포털 원본)
    """
    candidates = [
        f"{raw_dir}서울시_상권분석서비스_{name}_.csv",
        f"{raw_dir}서울시 상권분석서비스({name}).csv",
    ]
    for path in candidates:
        if os.path.exists(path):
            return pd.read_csv(path, encoding=ENCODING, dtype=KEY_DTYPES, **kw)
    raise FileNotFoundError(
        f"data/raw/ 에서 '{name}' CSV를 찾지 못했다. 허용 이름:\n  "
        + "\n  ".join(candidates))

def load_master(path: str = "data/master.csv") -> pd.DataFrame:
    """산출된 master.csv 를 읽는다 (utf-8-sig + 코드 컬럼 str)."""
    return pd.read_csv(path, encoding="utf-8-sig", dtype=KEY_DTYPES)


def load_whitelist(path: str = "config/업종_whitelist.csv") -> list[str]:
    """확정 분석 업종 목록."""
    return pd.read_csv(path)["서비스_업종_코드_명"].tolist()


def safe_ratio(numer: pd.Series, denom: pd.Series) -> pd.Series:
    """분모 0을 NaN으로 처리한 나눗셈.

    유입강도·가구당인구·청년비율은 전부 나눗셈이다. 분모 0을 막지 않으면
    inf가 생기고 분위수 계산이 조용히 왜곡된다.
    """
    return numer / denom.replace(0, pd.NA)
