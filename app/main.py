"""app/main.py — 대시보드 메인 엔트리포인트

탐색 모드 4종: 📊 종합 분석 / 📰 상권 뉴스 / 📍 입지 탐색 / ☕ 업종 후보 확인
DEV_SPEC §6 준수: 종합 분석 모드에서 사이드바 조건 변경 시 목록/산점도/지표 동시 갱신.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 프로젝트 루트 경로 등록
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import streamlit as st

try:
    from app.logic import (
        filter_candidates,
        load_master,
        load_news,
        load_scores,
        rescore,
        summary,
    )
    from app.views_c2 import render_reverse_view, render_scatter_view
    from app.views_c3 import render_detail_view, render_news_view
    from app.views_forward import render_forward_view
    from app import style, theme, ui
except ImportError:
    from logic import (
        filter_candidates,
        load_master,
        load_news,
        load_scores,
        rescore,
        summary,
    )
    from views_c2 import render_reverse_view, render_scatter_view
    from views_c3 import render_detail_view, render_news_view
    from views_forward import render_forward_view
    import style, theme, ui

st.set_page_config(page_title="서울 창업 입지 탐색기", page_icon="🧭", layout="wide")

# 표시 계층 — 로직과 무관하다. 이 두 줄을 지우면 Streamlit 기본 화면으로 돌아온다.
style.inject()   # app/style.py — 전역 CSS
theme.apply()    # app/theme.py — plotly 차트 공통 테마


@st.cache_data
def get_data():
    # 1. scores 로드 (실데이터 우선, 실패 시 mock 폴백)
    df_sc = None
    for path in ["data/scores.csv", "data/mock/scores.csv"]:
        try:
            if os.path.exists(path):
                df_sc = load_scores(path)
                if not df_sc.empty:
                    break
        except Exception:
            continue
    if df_sc is None or df_sc.empty:
        df_sc = load_scores("data/mock/scores.csv")

    # 2. news 로드 (실제 크롤링 파일들을 최우선으로 탐색)
    df_nw = None
    news_candidates = [
        "data/seoul_food_news.csv",
        "data/news.csv",
        "data/unique_news.csv",
        "data/mock/news.csv",
    ]
    for path in news_candidates:
        try:
            if os.path.exists(path):
                temp_df = load_news(path)
                if not temp_df.empty:
                    df_nw = temp_df
                    break
        except Exception:
            continue
    if df_nw is None or df_nw.empty:
        df_nw = load_news("data/mock/news.csv")

    # 3. master 로드
    df_ma = None
    for path in ["data/master.csv", "data/mock/master.csv"]:
        try:
            if os.path.exists(path):
                df_ma = load_master(path)
                if not df_ma.empty:
                    break
        except Exception:
            continue
    if df_ma is None:
        df_ma = pd.DataFrame()

    return df_sc, df_nw, df_ma


df_raw, df_news, df_master = get_data()

ui.appbar(
    "서울 창업 입지 탐색기",
    "같은 유형 상권끼리 비교해 공급이 부족하고 폐업률이 안정적인 상권 × 업종을 검토 후보로 제시합니다.",
    chips=[
        f"검토 후보 {len(df_raw):,}건",
        f"상권 {df_raw['상권_코드'].nunique():,}개",
        f"업종 {df_raw['서비스_업종_코드_명'].nunique()}종",
        f"유형 {df_raw['유형'].nunique()}종",
        "서울 열린데이터광장 · 공공누리 1유형",
    ],
)

# ── 탐색 모드 순서 (종합분석 바로 옆에 상권 뉴스 배치) ──────────────
MODE_ANALYSIS = "📊 종합 분석"
MODE_NEWS = "📰 상권 뉴스"
MODE_FORWARD = "📍 입지 탐색"
MODE_REVERSE = "☕ 업종 후보 확인"

mode = st.radio(
    "탐색 모드",
    [MODE_ANALYSIS, MODE_NEWS, MODE_FORWARD, MODE_REVERSE],
    horizontal=True,
    label_visibility="collapsed",
)
st.divider()

if mode == MODE_ANALYSIS:
    # 사이드바는 종합 분석 모드에서만 활성화
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
    df_filtered = filter_candidates(
        df_rescored, 업종=selected_jongs, 유형=selected_types, 자치구=selected_gus
    )

    stats = summary(df_filtered)
    ui.kpi_row([
        {"icon": "🎯", "label": "검토 후보", "value": f"{stats['후보_수']:,}", "unit": "건",
         "foot": "공급갭이 양(+)인 상권 × 업종 조합"},
        {"icon": "📍", "label": "해당 상권", "value": f"{stats['상권_수']:,}", "unit": "개",
         "foot": "후보에 포함된 서로 다른 상권"},
        {"icon": "⭐", "label": "평균 종합점수", "value": f"{stats['평균_종합점수']:.3f}",
         "foot": f"공급갭 {w_gap:.2f} : 안정성 {w_stab:.2f} 기준"},
        {"icon": "📉", "label": "평균 공급갭", "value": f"{stats['평균_공급갭']:.3f}",
         "foot": "동일 유형 중앙 공급밀도 대비 여유분"},
    ])

    tab1, tab2, tab3 = st.tabs([
        "① 후보 목록",
        "② 상권 포지셔닝 (산점도)",
        "③ 상권 상세 패널",
    ])

    with tab1:
        ui.section(
            "검토 후보 목록",
            "사이드바 가중치로 계산한 종합점수 순입니다. 매출은 점수에 들어가지 않고, "
            "공급갭이 비슷한 후보 간 규모 차이를 판단하시라고 함께 표시합니다.",
        )
        if df_filtered.empty:
            ui.empty_state(
                "조건을 만족하는 검토 후보가 없습니다",
                "사이드바의 업종·유형·자치구 조건을 하나씩 풀어 보세요. "
                "조건을 모두 비우면 서울 전체 후보가 표시됩니다.",
            )
        else:
            ui.candidate_table(df_filtered, n=100)

    with tab2:
        render_scatter_view(df_filtered, df_master)

    with tab3:
        render_detail_view(df_filtered, df_master)

elif mode == MODE_NEWS:
    ui.news_page(df_news)

elif mode == MODE_FORWARD:
    df_rescored = rescore(df_raw)
    render_forward_view(df_rescored)
    st.caption("종합점수는 DEV_SPEC §5-6 확정 기본 가중치(공급갭 0.6 : 안정성 0.4) 기준입니다.")

elif mode == MODE_REVERSE:
    df_rescored = rescore(df_raw)
    render_reverse_view(df_rescored)
    st.caption("종합점수는 DEV_SPEC §5-6 확정 기본 가중치(공급갭 0.6 : 안정성 0.4) 기준입니다.")

ui.footer(
    "서울 창업 입지 탐색기 · 서울 열린데이터광장 상권분석서비스(서울신용보증재단) · 공공누리 1유형   |   "
    "본 서비스는 특정 입지의 성공을 보장하지 않으며, 현장 조사 전 검토 대상을 좁히는 의사결정 보조 도구입니다. "
    "임대료·권리금 등 데이터로 확보할 수 없는 요소는 반영되어 있지 않습니다."
)
