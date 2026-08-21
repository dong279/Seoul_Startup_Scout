"""app/ui.py — 화면 구성 요소 (UI 계층 · 재사용 컴포넌트)

**로직이 없다.** 데이터 변환·점수 계산은 `app/logic.py` 담당이고, 이 파일은
넘겨받은 값을 "어떻게 보여줄 것인가"만 맡는다. 표시용 파생(억원 환산·순위
번호)은 원본 DataFrame을 복사해 만들고 반환하지 않는다 — 계산에 흘러들어가지
않게 하려는 것이다.

호출부는 `app/main.py` 하나뿐이며, 다른 뷰 파일(`views_c2/c3/forward`)은
이 파일을 몰라도 된다. 스타일 정의는 전부 `app/style.py` 의 CSS에 있다.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

_WS = re.compile(r"\n\s*")


def _html(markup: str) -> str:
    """줄바꿈·들여쓰기를 지운다.

    st.markdown 은 4칸 들여쓴 줄을 코드 블록으로 해석하므로, HTML을 여러 줄로
    쓰면 화면에 태그가 그대로 노출된다. 한 줄로 눌러서 넘긴다.
    """
    return _WS.sub("", markup).strip()


# ── 히어로 헤더 ───────────────────────────────────────────────────────
def hero(title: str, subtitle: str, chips: list[str] | None = None) -> None:
    """상단 브랜드 헤더. 페이지당 1회."""
    chip_html = "".join(
        f'<span class="ss-chip">{c}</span>' for c in (chips or [])
    )
    st.markdown(_html(f"""
        <div class="ss-hero">
          <div class="ss-hero-glow"></div>
          <div class="ss-hero-body">
            <div class="ss-eyebrow">SEOUL STARTUP SCOUT</div>
            <div class="ss-hero-title">{title}</div>
            <div class="ss-hero-sub">{subtitle}</div>
            <div class="ss-chips">{chip_html}</div>
          </div>
        </div>
    """), unsafe_allow_html=True)


# ── 요약 지표 ─────────────────────────────────────────────────────────
def kpi_row(items: list[dict]) -> None:
    """지표 카드를 한 줄에 배치한다.

    items: [{"label", "value", "unit"(선택), "foot"(선택), "icon"(선택)}, ...]
    st.metric 대신 직접 그리는 이유는 보조 설명줄과 단위 표기를 붙이기
    위해서다 — st.metric 은 delta 외 슬롯이 없다.
    """
    cards = []
    for it in items:
        icon = it.get("icon", "")
        unit = it.get("unit", "")
        foot = it.get("foot", "")
        cards.append(_html(f"""
            <div class="ss-kpi">
              <div class="ss-kpi-head">
                <span class="ss-kpi-icon">{icon}</span>
                <span class="ss-kpi-label">{it['label']}</span>
              </div>
              <div class="ss-kpi-value">{it['value']}<span class="ss-kpi-unit">{unit}</span></div>
              <div class="ss-kpi-foot">{foot}</div>
            </div>
        """))
    st.markdown(
        f'<div class="ss-kpi-row">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


# ── 섹션 제목 ─────────────────────────────────────────────────────────
def section(title: str, desc: str = "") -> None:
    """본문 구획 제목. 좌측 세로 룰 + 설명 한 줄."""
    desc_html = f'<div class="ss-section-desc">{desc}</div>' if desc else ""
    st.markdown(_html(f"""
        <div class="ss-section">
          <div class="ss-section-title">{title}</div>
          {desc_html}
        </div>
    """), unsafe_allow_html=True)


# ── 빈 상태 ───────────────────────────────────────────────────────────
def empty_state(title: str, body: str, icon: str = "🔍") -> None:
    """결과 0건 화면. 계약(§6)이 요구하는 '조건 완화 안내'를 담는 자리다."""
    st.markdown(_html(f"""
        <div class="ss-empty">
          <div class="ss-empty-icon">{icon}</div>
          <div class="ss-empty-title">{title}</div>
          <div class="ss-empty-body">{body}</div>
        </div>
    """), unsafe_allow_html=True)


# ── 후보 목록 표 ──────────────────────────────────────────────────────
# 화면 표기명 ← scores.csv 원본 컬럼명
_RENAME = {
    "상권_코드_명": "상권",
    "서비스_업종_코드_명": "업종",
    "유형": "상권 유형",
    "자치구_코드_명": "자치구",
    "종합점수": "종합점수",
    "공급갭": "공급갭",
    "행정동_폐업률": "폐업률",
    "전체_점포_수": "점포 수",
    "당월_매출_건수": "매출 건수",
}


def candidate_table(df: pd.DataFrame, n: int = 100) -> None:
    """검토 후보 목록.

    종합점수·공급갭을 막대로 보여주는 이유는 두 값 모두 0~1 범위라
    숫자만 나열하면 상위권 간 격차가 눈에 안 들어오기 때문이다.
    매출은 원 단위 그대로면 자릿수가 열 폭을 넘겨 억원으로 환산한다.
    """
    view = df.head(n).copy()
    view.insert(0, "순위", range(1, len(view) + 1))
    view["매출(억원)"] = view["당월_매출_금액"] / 1e8

    cols = (["순위"] + list(_RENAME.keys())[:7]
            + ["매출(억원)", "전체_점포_수", "당월_매출_건수"])
    cols = [c for c in dict.fromkeys(cols) if c in view.columns]
    view = view[cols].rename(columns=_RENAME)

    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "순위": st.column_config.NumberColumn("#", width="small", format="%d"),
            "상권": st.column_config.TextColumn("상권", width="medium"),
            "업종": st.column_config.TextColumn("업종", width="small"),
            "상권 유형": st.column_config.TextColumn("상권 유형", width="small"),
            "자치구": st.column_config.TextColumn("자치구", width="small"),
            "종합점수": st.column_config.ProgressColumn(
                "종합점수", min_value=0.0, max_value=1.0, format="%.3f",
                help="공급갭 점수와 안정성 점수의 가중합 (사이드바 슬라이더 반영)",
            ),
            "공급갭": st.column_config.ProgressColumn(
                "공급갭", min_value=0.0, max_value=1.0, format="%.3f",
                help="같은 유형 상권의 중앙 공급밀도 대비 여유분. 클수록 공급이 부족하다",
            ),
            "폐업률": st.column_config.NumberColumn(
                "폐업률", format="%.2f%%",
                help="해당 행정동의 외식 11종 4분기 누적 폐업률. 낮을수록 안정적",
            ),
            "매출(억원)": st.column_config.NumberColumn("당월 매출", format="%.2f억"),
            "점포 수": st.column_config.NumberColumn("점포 수", format="%d"),
            "매출 건수": st.column_config.NumberColumn("매출 건수", format="%d"),
        },
    )
