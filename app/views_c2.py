"""app/views_c2.py — C2 담당 화면 컴포넌트 (② 산점도, ④ 역방향 탐색)
DEV_SPEC §6 및 common/viz.py 팔레트 준수
"""
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
except ModuleNotFoundError:
    from common.viz import TYPE_COLORS
    from logic import reverse_lookup


def render_scatter_view(df: pd.DataFrame) -> None:
    """화면 ② 상권 포지셔닝 산점도 (메인 시각화)"""
    st.subheader("📊 상권 포지셔닝 산점도")
    st.caption("유효수요 대비 점포당 매출을 비교하여 검토 후보 상권의 시장 기회 영역(4사분면)을 탐색합니다.")

    if df.empty:
        st.warning("⚠️ 선택된 조건에 해당하는 검토 후보 상권이 없습니다. 사이드바 필터 조건을 완화해 주세요.")
        return

    plot_df = df.copy()
    plot_df["유효수요"] = plot_df.apply(
        lambda r: (r["전체_점포_수"] / r["공급밀도"]) if r["공급밀도"] > 0 else 0, axis=1
    )
    plot_df["점포당_매출"] = plot_df.apply(
        lambda r: (r["당월_매출_금액"] / r["전체_점포_수"]) if r["전체_점포_수"] > 0 else 0, axis=1
    )

    med_x = plot_df["유효수요"].median()
    med_y = plot_df["점포당_매출"].median()

    fig = px.scatter(
        plot_df,
        x="유효수요",
        y="점포당_매출",
        size="전체_점포_수",
        color="유형",
        hover_name="상권_코드_명",
        hover_data={
            "서비스_업종_코드_명": True,
            "종합점수": ":.3f",
            "공급갭": ":.3f",
            "행정동_폐업률": ":.2f",
            "유효수요": ":,.1f",
            "점포당_매출": ":,.0f",
            "전체_점포_수": True,
            "유형": False,
        },
        color_discrete_map=TYPE_COLORS,
        labels={
            "유효수요": "유효수요 (상주·직장·유동 정규화합 역산)",
            "점포당_매출": "점포당 평균 매출액 (원)",
            "전체_점포_수": "점포 수",
            "유형": "상권 유형",
        },
        template="plotly_white",
    )

    fig.add_vline(x=med_x, line_dash="dash", line_color="gray", annotation_text="수요 중앙값", annotation_position="top left")
    fig.add_hline(y=med_y, line_dash="dash", line_color="gray", annotation_text="매출 중앙값", annotation_position="bottom right")

    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.98, y=0.05,
        text="<b>💡 기회 영역</b><br>수요 높음 × 점포당 매출 낮음",
        showarrow=False,
        bgcolor="rgba(255, 235, 235, 0.85)",
        bordercolor="#D94F4F",
        borderwidth=1,
        align="right",
    )

    fig.update_layout(
        height=580,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📌 사분면 해석 가이드"):
        st.markdown(
            "- **4사분면 (우하단 — 고수요·저매출)**: **핵심 검토 후보 영역.** 잠재 수요가 풍부하나 기존 점포당 매출/밀도가 낮아 신규 진입 여력이 큽니다.\n"
            "- **1사분면 (우상단 — 고수요·고매출)**: 대형 중심 상권. 시장 규모가 크나 경쟁 강도가 높습니다.\n"
            "- **2사분면 (좌상단 — 저수요·고매출)**: 특정 목적형 단골 중심 상권입니다.\n"
            "- **3사분면 (좌하단 — 저수요·저매출)**: 배후 수요와 매출이 모두 낮아 리스크가 높은 영역입니다."
        )


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
        st.dataframe(display_df.style.format({"종합점수": "{:.3f}", "공급갭": "{:.3f}", "폐업률(%)": "{:.2f}%"}), use_container_width=True, hide_index=True)