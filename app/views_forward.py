"""app/views_forward.py — 입지 탐색 화면 (업종 → 검토 후보 상권)

`views_c2.py`의 역방향 탐색과 대칭을 이루는 정방향 화면이다. 기존 뷰 파일을
건드리지 않도록 별도 파일로 둔다(오너십 규약 §3-9).

문구는 DEV_SPEC §6에 따라 "추천"이 아닌 **"검토 후보"**로 통일한다.
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
    from app.logic import filter_candidates, forward_lookup
except ImportError:
    from common.viz import TYPE_COLORS
    from logic import filter_candidates, forward_lookup

# 유형 색상 팔레트 방어 (TYPE_COLORS에 없는 "유입 집중형" 보정 — views_c2와 동일)
SAFE_COLORS = {**TYPE_COLORS, "유입 집중형": "#2E5C8A"}

ALL = "전체"


def _options(df: pd.DataFrame, col: str) -> list[str]:
    return [ALL] + sorted(df[col].dropna().unique().tolist())


def render_forward_view(df: pd.DataFrame) -> None:
    """입지 탐색 — 창업 업종을 고르면 그 업종의 검토 후보 상권 Top N을 제시한다."""
    st.subheader("📍 창업 아이템 기준 입지 탐색")
    st.caption(
        "창업하려는 업종을 선택하면, 같은 유형 상권 대비 공급이 부족하고 "
        "폐업률이 낮은 **검토 후보 상권**을 종합점수 순으로 제시합니다."
    )

    if df.empty:
        st.warning("⚠️ 탐색 가능한 검토 후보 데이터가 없습니다.")
        return

    c_job, c_type, c_gu, c_n = st.columns([2, 2, 2, 1])
    with c_job:
        업종명 = st.selectbox("창업 업종", sorted(df["서비스_업종_코드_명"].dropna().unique()))
    with c_type:
        유형 = st.selectbox("상권 유형", _options(df, "유형"))
    with c_gu:
        자치구 = st.selectbox("자치구", _options(df, "자치구_코드_명"))
    with c_n:
        n = st.slider("표시 개수", 5, 20, 10, 5)

    # 업종 전체 모수 — 필터를 좁히기 전 "이 업종의 서울 전체 후보"가 몇 곳인지 먼저 알린다
    전체_후보 = filter_candidates(df, 업종=[업종명])
    top = forward_lookup(
        df,
        업종명,
        유형=None if 유형 == ALL else [유형],
        자치구=None if 자치구 == ALL else [자치구],
        n=n,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("서울 전체 검토 후보 상권", f"{전체_후보['상권_코드'].nunique():,}곳")
    m2.metric("현재 조건 내 후보", f"{len(top):,}곳")
    m3.metric(
        "평균 종합점수",
        f"{top['종합점수'].mean():.3f}점" if not top.empty else "—",
    )

    if 전체_후보.empty:
        st.info(
            f"**{업종명}** 은 서울 전체에서 공급 갭이 발생한 상권이 없습니다. "
            "이미 공급이 충분한 업종이므로 다른 업종을 검토해 보세요."
        )
        return
    if top.empty:
        st.info(
            f"선택한 조건(유형 {유형} · 자치구 {자치구})에 **{업종명}** 검토 후보가 없습니다. "
            f"조건을 '{ALL}'로 완화하면 서울 전체 {전체_후보['상권_코드'].nunique()}곳을 볼 수 있습니다."
        )
        return
    if len(전체_후보) <= 3:
        st.warning(
            f"⚠️ **{업종명}** 의 검토 후보는 서울 전체에 {len(전체_후보)}곳뿐입니다. "
            "표본이 적어 순위의 의미가 제한적입니다."
        )

    st.markdown(f"##### **{업종명}** 검토 후보 상권 Top {len(top)}")

    c_chart, c_table = st.columns([3, 2])
    with c_chart:
        fig = px.bar(
            top,
            x="종합점수",
            y="상권_코드_명",
            color="유형",
            orientation="h",
            color_discrete_map=SAFE_COLORS,
            text_auto=".3f",
            hover_data={
                "자치구_코드_명": True,
                "공급갭": ":.3f",
                "행정동_폐업률": ":.2f",
                "전체_점포_수": True,
            },
            labels={
                "상권_코드_명": "상권",
                "종합점수": "종합점수",
                "유형": "상권 유형",
                "자치구_코드_명": "자치구",
                "행정동_폐업률": "폐업률(%)",
                "전체_점포_수": "점포 수",
            },
            template="plotly_white",
        )
        # nlargest 순서(내림차순)를 그대로 유지 — 가로 막대는 아래에서 위로 쌓인다
        fig.update_yaxes(categoryorder="array", categoryarray=top["상권_코드_명"].tolist()[::-1])
        fig.update_layout(
            height=max(360, 42 * len(top)),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

    with c_table:
        disp = top[[
            "상권_코드_명", "자치구_코드_명", "유형", "종합점수",
            "공급갭", "행정동_폐업률", "당월_매출_금액", "전체_점포_수",
        ]].rename(columns={
            "상권_코드_명": "상권",
            "자치구_코드_명": "자치구",
            "행정동_폐업률": "폐업률(%)",
            "당월_매출_금액": "당월 매출",
            "전체_점포_수": "점포 수",
        })
        st.dataframe(
            disp.style.format({
                "종합점수": "{:.3f}",
                "공급갭": "{:.3f}",
                "폐업률(%)": "{:.2f}%",
                "당월 매출": "{:,.0f}원",
            }),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("📌 이 화면을 읽는 법"):
        st.markdown(
            "- **종합점수**는 공급갭 점수와 안정성 점수의 가중합입니다(DEV_SPEC §5-6 확정 가중치 0.6 : 0.4).\n"
            "- **공급갭**은 같은 유형 상권의 중앙 공급밀도 대비 여유분입니다. "
            "목록에는 공급갭이 양(+)인 상권만 담기므로, 후보가 적은 업종은 그만큼 이미 포화된 업종입니다.\n"
            "- **폐업률**은 해당 행정동의 외식 11종 4분기 폐업률입니다. 낮을수록 안정적입니다.\n"
            "- 상권 유형이 다르면 배후 수요의 성격이 다릅니다. 점수가 비슷하다면 "
            "창업 아이템과 맞는 유형을 먼저 보세요.\n"
            "- 개별 상권의 인구 구성·요일별 매출·최근 기사는 **종합 분석 → 상권 상세 패널**에서 확인합니다."
        )
