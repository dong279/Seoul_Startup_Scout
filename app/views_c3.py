"""상권 상세 패널(화면 ③) Streamlit 컴포넌트."""
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
    from app.logic import detail_for, news_for
except ImportError:
    from logic import detail_for, news_for


TYPE_REASONS = {
    "유입 집중형": "골목상권 중 유입강도가 상위 25%인 상권입니다.",
    "청년 밀집형": "골목상권 중 유입강도 25~75% 구간이면서 청년비율이 상위 25%인 상권입니다.",
    "가족 주거형": "골목상권 중 유입강도가 하위 50%이고 가구당인구가 상위 50%인 상권입니다.",
    "일반 주거·생활형": "골목상권 규칙 분류의 나머지 상권입니다.",
    "발달상권형": "상권 구분이 발달상권으로 분류된 상권입니다.",
    "전통시장형": "상권 구분이 전통시장으로 분류된 상권입니다.",
    "관광특구형": "상권 구분이 관광특구로 분류된 상권입니다.",
}


def _candidate_options(scores: pd.DataFrame) -> pd.DataFrame:
    """선택 상자용 상권×업종 후보를 중복 없이 생성."""
    cols = ["상권_코드", "상권_코드_명", "서비스_업종_코드", "서비스_업종_코드_명"]
    options = scores[cols].drop_duplicates(["상권_코드", "서비스_업종_코드"]).copy()
    options["label"] = (
        options["상권_코드_명"].astype(str)
        + " · "
        + options["서비스_업종_코드_명"].astype(str)
    )
    return options.sort_values("label", kind="stable").reset_index(drop=True)


def _render_news(articles: pd.DataFrame) -> None:
    """최근 기사 최대 3건을 빈 상태까지 포함해 표시한다."""
    st.subheader("📰 최근 3개월 경제지 기사")
    if articles.empty:
        st.info("최근 3개월 관련 기사 없음")
        return

    for _, article in articles.iterrows():
        title = str(article["제목"])
        press = str(article["언론사"])
        published_at = str(article["날짜"])
        link = article["링크"]

        text_col, link_col = st.columns([5, 1])
        with text_col:
            st.markdown(f"**{title}**")
            st.caption(f"{press} · {published_at}")
        with link_col:
            if pd.notna(link) and str(link).strip():
                st.link_button("기사 보기", str(link), use_container_width=True)


def render_detail_view(
    scores: pd.DataFrame,
    master: pd.DataFrame,
    news: pd.DataFrame,
) -> None:
    """화면 ③: 검토 후보 하나의 근거·인구·매출·뉴스 표시."""
    st.subheader("🏢 상권 상세 패널")
    st.caption("검토 후보의 유형·공급 구조·인구·매출·최근 동향을 함께 확인합니다.")

    if scores.empty:
        st.info("상세 정보를 확인할 검토 후보가 없습니다. 사이드바 조건을 완화해 주세요.")
        return

    options = _candidate_options(scores)
    selected_index = st.selectbox(
        "상세 확인할 검토 후보 선택",
        options.index,
        format_func=lambda index: options.at[index, "label"],
    )
    selected = options.loc[selected_index]
    detail = detail_for(
        scores,
        master,
        selected["상권_코드"],
        selected["서비스_업종_코드"],
    )

    if not detail:
        st.warning("선택한 검토 후보의 상세 데이터가 없습니다.")
        return

    st.markdown(f"### {detail['상권명']} · {detail['업종']}")
    type_col, reason_col = st.columns([1, 3])
    with type_col:
        st.metric("상권 유형", detail["유형"])
    with reason_col:
        st.markdown("##### 판정 근거")
        st.write(TYPE_REASONS.get(detail["유형"], "유형 판정 근거 정보가 없습니다."))

    density_col, closure_col, sales_col = st.columns(3)
    density_col.metric("공급밀도", f"{detail['공급밀도']:.3f}")
    closure_col.metric("행정동 4분기 폐업률", f"{detail['행정동_폐업률']:.2f}%")
    sales_col.metric("당월 매출액", f"{detail['당월_매출_금액']:,}원")
    st.caption(
        f"동일 유형 중앙 공급밀도: {detail['동일유형_중앙_공급밀도']:.3f} (낮을수록 같은 유형 대비 공급 여유가 큼)"
    )

    age_col, weekday_col = st.columns(2)
    with age_col:
        st.markdown("##### 연령 구성")
        fig_age = px.bar(
            detail["연령_구성"],
            x="연령대",
            y="상주인구",
            text_auto=",",
            labels={"연령대": "연령대", "상주인구": "상주인구(명)"},
            color_discrete_sequence=["#2E5C8A"],
            template="plotly_white",
        )
        fig_age.update_layout(height=330, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig_age, use_container_width=True)

    with weekday_col:
        st.markdown("##### 요일별 매출")
        weekday_sales = detail["요일별_매출"].copy()
        st.dataframe(
            weekday_sales.style.format({"매출금액": "{:,.0f}원"}),
            use_container_width=True,
            hide_index=True,
        )

    _render_news(news_for(news, selected["상권_코드"], n=3))
