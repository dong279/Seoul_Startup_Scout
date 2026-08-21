"""app/views_c2.py — C2 담당 화면 컴포넌트 (② 산점도, ④ 역방향 탐색)"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from common.viz import TYPE_COLORS
    from app.logic import reverse_lookup
except ImportError:
    from common.viz import TYPE_COLORS
    from logic import reverse_lookup

# 유형 색상 팔레트 방어 (유입 집중형 보정)
SAFE_COLORS = {**TYPE_COLORS, "유입 집중형": "#2E5C8A"}


def render_scatter_view(df: pd.DataFrame, master_df: pd.DataFrame) -> None:
    """분석 노트북 기준의 업종별 개업률·폐업률 산점도를 표시한다."""
    st.subheader("업종별 개업률 vs 폐업률")
    st.caption("점은 업종별 평균이며, 점 크기는 전체 점포 수를 의미합니다. 기준선은 현재 선택된 업종의 평균입니다.")

    required = {"상권_코드", "서비스_업종_코드_명", "개업_율", "폐업_률", "전체_점포_수"}
    if df.empty:
        st.warning("선택한 조건에 해당하는 후보 상권이 없습니다. 사이드바 필터를 조정해 주세요.")
        return
    if not required.issubset(master_df.columns):
        st.error("업종별 개업률·폐업률 산점도에 필요한 원본 데이터 컬럼이 없습니다.")
        return

    selected_pairs = df[["상권_코드", "서비스_업종_코드_명"]].drop_duplicates()
    source_df = master_df.merge(
        selected_pairs,
        on=["상권_코드", "서비스_업종_코드_명"],
        how="inner",
    )
    if source_df.empty:
        st.warning("선택한 후보에 연결된 개업률·폐업률 원본 데이터가 없습니다.")
        return

    industry_scatter = (
        source_df.groupby("서비스_업종_코드_명", as_index=False)[["개업_율", "폐업_률", "전체_점포_수"]]
        .mean()
        .sort_values("폐업_률", ascending=False)
    )
    x_mean = industry_scatter["개업_율"].mean()
    y_mean = industry_scatter["폐업_률"].mean()

    fig = px.scatter(
        industry_scatter,
        x="개업_율",
        y="폐업_률",
        size="전체_점포_수",
        color="서비스_업종_코드_명",
        text="서비스_업종_코드_명",
        size_max=58,
        color_discrete_sequence=px.colors.qualitative.Safe,
        hover_name="서비스_업종_코드_명",
        hover_data={
            "개업_율": ":.2f",
            "폐업_률": ":.2f",
            "전체_점포_수": ":,.0f",
            "서비스_업종_코드_명": False,
        },
        labels={
            "개업_율": "개업률 (%)",
            "폐업_률": "폐업률 (%)",
            "전체_점포_수": "전체 점포 수",
            "서비스_업종_코드_명": "업종",
        },
        template="plotly_white",
    )
    fig.update_traces(
        marker={"line": {"color": "#333333", "width": 1.1}, "opacity": 0.85},
        textposition="top center",
    )
    fig.add_vline(
        x=x_mean, line_dash="dash", line_color="#E53935",
        annotation_text=f"개업률 평균 ({x_mean:.1f}%)", annotation_position="top left",
    )
    fig.add_hline(
        y=y_mean, line_dash="dash", line_color="#4B5563",
        annotation_text=f"폐업률 평균 ({y_mean:.1f}%)", annotation_position="bottom right",
    )
    fig.add_annotation(
        xref="paper", yref="paper", x=0.98, y=0.98,
        text="<b>고개업 · 고폐업</b><br>레드오션(고위험 시장)",
        showarrow=False, align="right", bgcolor="rgba(255, 235, 235, 0.85)",
        bordercolor="#E53935", borderwidth=1,
    )
    fig.add_annotation(
        xref="paper", yref="paper", x=0.98, y=0.04,
        text="<b>고개업 · 저폐업</b><br>성장 확장형 시장",
        showarrow=False, align="right", bgcolor="rgba(235, 248, 255, 0.85)",
        bordercolor="#2B5C8F", borderwidth=1,
    )
    fig.update_layout(
        height=620,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

def render_reverse_view(df: pd.DataFrame) -> None:
    """화면 ④ 역방향 탐색 (상권 선택 → 공급 부족 업종 Top 5)"""
    st.subheader("🔍 상권 기준 역방향 업종 탐색")
    st.caption("특정 상권을 지정하면 해당 지역에서 공급 갭과 종합점수가 높은 검토 후보 업종 Top 5를 도출합니다.")

    if df.empty:
        st.warning("⚠️ 탐색 가능한 상권 데이터가 없습니다.")
        return

    col_gu, col_area = st.columns(2)
    with col_gu:
        gu_list = ["전체"] + sorted(df["자치구_코드_명"].dropna().unique().tolist())
        selected_gu = st.selectbox("자치구 필터", gu_list)

    filtered_df = df if selected_gu == "전체" else df[df["자치구_코드_명"] == selected_gu]
    area_dict = dict(zip(filtered_df["상권_코드_명"], filtered_df["상권_코드"]))

    if not area_dict:
        st.info("해당 자치구에 데이터가 없습니다.")
        return

    with col_area:
        selected_name = st.selectbox("탐색할 상권 선택", sorted(area_dict.keys()))

    target_code = area_dict[selected_name]
    top_jobs = reverse_lookup(df, target_code, n=5)

    if top_jobs.empty:
        st.info(f"[{selected_name}] 상권에 공급 부족으로 도출된 검토 후보 업종이 없습니다.")
        return

    st.markdown(f"##### **[{selected_name}]** 공급 부족 업종 Top {len(top_jobs)}")

    c_chart, c_table = st.columns([3, 2])
    with c_chart:
        fig_bar = px.bar(
            top_jobs,
            x="서비스_업종_코드_명",
            y="종합점수",
            color="종합점수",
            color_continuous_scale="Blues",
            labels={"서비스_업종_코드_명": "업종명", "종합점수": "종합 적합도"},
            text_auto=".3f",
            title=f"{selected_name} 검토 후보 업종 종합점수",
        )
        fig_bar.update_layout(height=350, coloraxis_showscale=False, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_bar, use_container_width=True)

    with c_table:
        display_df = top_jobs[["서비스_업종_코드_명", "종합점수", "공급갭", "행정동_폐업률"]].rename(
            columns={
                "서비스_업종_코드_명": "업종",
                "종합점수": "종합점수",
                "공급갭": "공급갭",
                "행정동_폐업률": "폐업률(%)",
            }
        )
        st.dataframe(
            display_df.style.format({"종합점수": "{:.3f}", "공급갭": "{:.3f}", "폐업률(%)": "{:.2f}%"}),
            use_container_width=True,
            hide_index=True,
        )
