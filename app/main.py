"""app/main.py — 대시보드 메인 엔트리포인트
DEV_SPEC §6 준수: 사이드바 조건 변경 시 산점도/목록/지표 동시 갱신
"""
from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트 경로 등록
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st

# 실행 환경 호환 import
try:
    from app.logic import filter_candidates, load_master, load_news, load_scores, rescore, summary
    from app.views_c2 import render_reverse_view, render_scatter_view
    from app.views_c3 import render_detail_view
except ModuleNotFoundError:
    from logic import filter_candidates, load_master, load_news, load_scores, rescore, summary
    from views_c2 import render_reverse_view, render_scatter_view
    from views_c3 import render_detail_view

st.set_page_config(page_title="서울 창업 입지 탐색기", page_icon="🧭", layout="wide")

@st.cache_data
def get_data():
    try:
        df_sc = load_scores("data/scores.csv")
    except FileNotFoundError:
        df_sc = load_scores("data/mock/scores.csv")
    try:
        df_nw = load_news("data/news.csv")
    except Exception:
        df_nw = load_news("data/mock/news.csv")
    try:
        df_ma = load_master("data/master.csv")
    except FileNotFoundError:
        df_ma = load_master("data/mock/master.csv")
    return df_sc, df_nw, df_ma

df_raw, df_news, df_master = get_data()

st.sidebar.header("🔍 탐색 조건 설정")

w_gap = st.sidebar.slider("공급갭 가중치", 0.0, 1.0, 0.6, 0.05)
w_stab = st.sidebar.slider("안정성 가중치", 0.0, 1.0, 0.4, 0.05)

all_jongs = sorted(df_raw["서비스_업종_코드_명"].dropna().unique().tolist())
selected_jongs = st.sidebar.multiselect("업종 선택 (다중 선택 가능)", all_jongs, default=[])

all_types = sorted(df_raw["유형"].dropna().unique().tolist())
selected_types = st.sidebar.multiselect("상권 유형 선택", all_types, default=[])

all_gus = sorted(df_raw["자치구_코드_명"].dropna().unique().tolist())
selected_gus = st.sidebar.multiselect("자치구 선택", all_gus, default=[])

df_rescored = rescore(df_raw, w_gap, w_stab)
df_filtered = filter_candidates(df_rescored, 업종=selected_jongs, 유형=selected_types, 자치구=selected_gus)

st.title("🧭 서울 창업 입지 탐색기 (Seoul Startup Scout)")
st.caption("서울시 상권 데이터 기반 공급 부족 & 안정성 기반 창업 검토 후보 탐색")

stats = summary(df_filtered)
c1, c2, c3, c4 = st.columns(4)
c1.metric("검토 후보 건수", f"{stats['후보_수']:,}건")
c2.metric("해당 상권 수", f"{stats['상권_수']:,}개")
c3.metric("평균 종합점수", f"{stats['평균_종합점수']:.3f}점")
c4.metric("평균 공급갭", f"{stats['평균_공급갭']:.3f}")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs([
    "① 후보 탐색 (목록)",
    "② 상권 포지셔닝 (산점도)",
    "③ 상권 상세 패널",
    "④ 역방향 탐색"
])

with tab1:
    st.subheader("📋 검토 후보 목록")
    if df_filtered.empty:
        st.info("조건을 만족하는 검토 후보가 없습니다. 사이드바 조건을 완화해 주세요.")
    else:
        disp_cols = ["상권_코드_명", "서비스_업종_코드_명", "유형", "자치구_코드_명", "종합점수", "공급갭", "행정동_폐업률", "당월_매출_금액", "당월_매출_건수", "전체_점포_수"]
        st.dataframe(df_filtered[disp_cols].head(100), use_container_width=True, hide_index=True)

with tab2:
    render_scatter_view(df_filtered)

with tab3:
    render_detail_view(df_filtered, df_master, df_news)

with tab4:
    render_reverse_view(df_rescored)