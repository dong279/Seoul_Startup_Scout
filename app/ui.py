"""app/ui.py — 화면 구성 요소 (UI 계층 · 재사용 컴포넌트)

**로직이 없다.** 데이터 변환·점수 계산은 `app/logic.py` 담당이고, 이 파일은
넘겨받은 값을 어떻게 보여줄지만 맡는다. 표시용 파생(억원 환산·순위 번호)은
원본 DataFrame을 복사해 만들고 반환하지 않는다 — 계산에 흘러들어가지 않게 하려는 것이다.

호출부는 `app/main.py` 하나뿐이다. `views_c2/c3/forward` 는 이 파일을 몰라도 되고,
스타일 정의는 전부 `app/style.py` 의 CSS에 있다.
"""
from __future__ import annotations

import html
import re

import pandas as pd
import streamlit as st

_WS = re.compile(r"\n\s*")


def _h(markup: str) -> str:
    """줄바꿈·들여쓰기를 지운다.

    st.markdown 은 4칸 들여쓴 줄을 코드 블록으로 해석하므로, HTML을 여러 줄로
    쓰면 화면에 태그가 그대로 노출된다. 한 줄로 눌러서 넘긴다.
    """
    return _WS.sub("", markup).strip()


def _esc(v) -> str:
    """사용자에게 보이는 외부 문자열은 반드시 이스케이프한다.

    기사 제목에 `<`, `&`, 따옴표가 실제로 들어온다 — 그대로 넣으면 레이아웃이
    깨지거나 태그로 해석된다.
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return html.escape(str(v), quote=True)


# ── 앱바 ──────────────────────────────────────────────────────────────
def appbar(title: str, subtitle: str, chips: list[str] | None = None,
           mark: str = "🧭") -> None:
    """상단 브랜드 바. 페이지당 1회.

    큰 마케팅형 배너 대신 좌측 마크 + 제목 + 우측 메타 칩의 앱바 형태로 둔다 —
    데이터 도구는 첫 화면에서 배너보다 지표가 먼저 보이는 편이 낫다.
    """
    chip_html = "".join(f'<span class="sc-chip">{_esc(c)}</span>' for c in (chips or []))
    st.markdown(_h(f"""
        <div class="sc-appbar">
          <div class="sc-mark">{mark}</div>
          <div class="sc-appbar-txt">
            <div class="sc-appbar-title">{_esc(title)}</div>
            <div class="sc-appbar-sub">{_esc(subtitle)}</div>
          </div>
          <div class="sc-chips">{chip_html}</div>
        </div>
    """), unsafe_allow_html=True)


# ── 지표 카드 ─────────────────────────────────────────────────────────
def kpi_row(items: list[dict]) -> None:
    """지표 카드를 한 줄에 배치한다.

    items: [{"label", "value", "unit"(선택), "foot"(선택), "icon"(선택)}, ...]
    st.metric 대신 직접 그리는 이유는 보조 설명줄과 단위 표기를 붙이기 위해서다 —
    st.metric 은 delta 외에 슬롯이 없다.
    """
    cards = "".join(_h(f"""
        <div class="sc-kpi">
          <div class="sc-kpi-h">
            <span class="sc-kpi-ico">{_esc(it.get('icon',''))}</span>
            <span class="sc-kpi-lab">{_esc(it['label'])}</span>
          </div>
          <div class="sc-kpi-val">{_esc(it['value'])}<span class="sc-kpi-unit">{_esc(it.get('unit',''))}</span></div>
          <div class="sc-kpi-foot">{_esc(it.get('foot',''))}</div>
        </div>
    """) for it in items)
    st.markdown(f'<div class="sc-kpis">{cards}</div>', unsafe_allow_html=True)


# ── 섹션 제목 ─────────────────────────────────────────────────────────
def section(title: str, desc: str = "") -> None:
    """본문 구획 제목. 좌측 세로 룰 + 설명 한 줄."""
    d = f'<div class="sc-sec-d">{_esc(desc)}</div>' if desc else ""
    st.markdown(_h(f"""
        <div class="sc-sec"><div class="sc-sec-t">{_esc(title)}</div>{d}</div>
    """), unsafe_allow_html=True)


# ── 빈 상태 ───────────────────────────────────────────────────────────
def empty_state(title: str, body: str, icon: str = "🔍") -> None:
    """결과 0건 화면. 계약(§6)이 요구하는 '조건 완화 안내'를 담는 자리다."""
    st.markdown(_h(f"""
        <div class="sc-empty">
          <div class="sc-empty-i">{_esc(icon)}</div>
          <div class="sc-empty-t">{_esc(title)}</div>
          <div class="sc-empty-b">{_esc(body)}</div>
        </div>
    """), unsafe_allow_html=True)


def footer(text: str) -> None:
    st.markdown(f'<div class="sc-foot">{_esc(text)}</div>', unsafe_allow_html=True)


# ── 후보 목록 표 ──────────────────────────────────────────────────────
_RENAME = {
    "상권_코드_명": "상권",
    "서비스_업종_코드_명": "업종",
    "유형": "상권 유형",
    "자치구_코드_명": "자치구",
    "행정동_폐업률": "폐업률",
    "전체_점포_수": "점포 수",
    "당월_매출_건수": "매출 건수",
}


def candidate_table(df: pd.DataFrame, n: int = 100) -> None:
    """검토 후보 목록.

    종합점수·공급갭을 막대로 보여주는 이유는 두 값 모두 0~1 범위라 숫자만
    나열하면 상위권 간 격차가 눈에 들어오지 않기 때문이다. 매출은 원 단위
    그대로면 자릿수가 열 폭을 넘겨 억원으로 환산한다(정렬은 그대로 가능).
    """
    view = df.head(n).copy()
    view.insert(0, "순위", range(1, len(view) + 1))
    if "당월_매출_금액" in view.columns:
        view["매출"] = view["당월_매출_금액"] / 1e8

    order = ["순위", "상권_코드_명", "서비스_업종_코드_명", "유형", "자치구_코드_명",
             "종합점수", "공급갭", "행정동_폐업률", "매출", "전체_점포_수", "당월_매출_건수"]
    cols = [c for c in order if c in view.columns]
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
            "매출": st.column_config.NumberColumn(
                "당월 매출", format="%.2f억", help="점수에 반영되지 않는 참고 지표"),
            "점포 수": st.column_config.NumberColumn("점포 수", format="%d"),
            "매출 건수": st.column_config.NumberColumn("매출 건수", format="%d"),
        },
    )


# ── 뉴스 ──────────────────────────────────────────────────────────────
# 언론사별 배지 색 — 표기가 아니라 눈으로 출처를 구분하게 하는 용도다.
_PRESS_COLOR = {
    "한국경제": ("#E8F0FB", "#1E4C8A"),
    "매일경제": ("#FBEFEF", "#A32B2B"),
    "서울경제": ("#EDF6F1", "#2C6E49"),
    "머니투데이": ("#FFF4E6", "#9A5B00"),
    "아시아경제": ("#F1EEFA", "#5B3E9E"),
    "파이낸셜뉴스": ("#E9F5F5", "#1F6F6F"),
    "이데일리": ("#FDF0F5", "#9B2C5B"),
    "조선비즈": ("#EEF2F7", "#33506E"),
    "헤럴드경제": ("#F5F0E8", "#7A5A20"),
}
_DEFAULT_BADGE = ("#F1F5F9", "#475569")

_PAGE = 12
_SHOWN_KEY = "sc_news_shown"
_SIG_KEY = "sc_news_sig"


def _news_card(row: pd.Series) -> str:
    press = str(row.get("언론사", "") or "")
    bg, fg = _PRESS_COLOR.get(press, _DEFAULT_BADGE)
    link = row.get("링크")
    link = str(link).strip() if pd.notna(link) else ""
    title = _esc(row.get("제목", ""))
    title_html = f'<a href="{_esc(link)}" target="_blank" rel="noopener">{title}</a>' if link else title
    summary = _esc(row.get("요약", ""))
    summary_html = f'<div class="sc-card-s">{summary}</div>' if summary else ""
    foot = (f'<div class="sc-card-f"><a href="{_esc(link)}" target="_blank" rel="noopener">'
            f'원문 보기 →</a></div>') if link else ""
    return _h(f"""
        <div class="sc-card">
          <div class="sc-card-h">
            <span class="sc-badge" style="background:{bg};color:{fg}">{_esc(press)}</span>
            <span class="sc-date">{_esc(row.get('날짜',''))}</span>
          </div>
          <div class="sc-card-t">{title_html}</div>
          {summary_html}
          {foot}
        </div>
    """)


def news_page(news: pd.DataFrame) -> None:
    """화면 ④ 상권 뉴스 — 서울 외식·창업 동향.

    수치가 담지 못하는 최근 맥락을 보완하는 참고 화면이다(기획서 목표 4).
    점수·순위에 영향을 주지 않으므로 기사가 없어도 다른 화면은 정상 동작한다.
    """
    section(
        "서울 외식·창업 동향",
        "최근 3개월 경제지 기사입니다. 수치가 담지 못하는 최근 맥락을 보완하는 "
        "참고 자료이며, 검토 후보의 점수·순위에는 반영되지 않습니다.",
    )

    if news is None or news.empty:
        empty_state(
            "최근 3개월 수집된 기사가 없습니다",
            "uv run python scripts/scrape_news.py 로 수집한 뒤 새로고침하세요.",
            "📰",
        )
        return

    df = news.drop_duplicates(subset=["제목"]).copy()
    if "날짜" in df.columns:
        df = df.sort_values("날짜", ascending=False)

    presses = sorted(df["언론사"].dropna().unique().tolist()) if "언론사" in df else []
    c1, c2 = st.columns([3, 2])
    with c1:
        sel = st.multiselect("언론사", presses, default=[], placeholder="전체")
    with c2:
        kw = st.text_input("검색어", placeholder="예: 카페, 임대료, 폐업")

    shown = df
    if sel:
        shown = shown[shown["언론사"].isin(sel)]
    if kw and kw.strip():
        q = kw.strip()
        hit = shown["제목"].fillna("").str.contains(q, case=False, regex=False)
        if "요약" in shown.columns:
            hit = hit | shown["요약"].fillna("").str.contains(q, case=False, regex=False)
        shown = shown[hit]

    kpi_row([
        {"icon": "📰", "label": "기사", "value": f"{len(shown):,}", "unit": "건",
         "foot": f"전체 {len(df):,}건 중"},
        {"icon": "🏢", "label": "언론사", "value": f"{shown['언론사'].nunique() if len(shown) else 0}",
         "unit": "곳", "foot": "경제지 화이트리스트 기준"},
        {"icon": "🗓️", "label": "수집 기간",
         "value": f"{shown['날짜'].min()} ~ {shown['날짜'].max()}" if len(shown) else "—",
         "unit": "", "foot": "원문 게재일 기준 최근 90일"},
    ])

    if shown.empty:
        empty_state(
            "조건에 맞는 기사가 없습니다",
            f"검색어를 지우거나 언론사 선택을 해제하면 전체 {len(df)}건을 볼 수 있습니다.",
        )
        return

    # 필터가 바뀌면 처음부터 — 12건만 보이는 채로 조건을 바꾸면
    # "왜 결과가 안 늘지"로 읽힌다
    sig = (tuple(sel), kw)
    if st.session_state.get(_SIG_KEY) != sig:
        st.session_state[_SIG_KEY] = sig
        st.session_state[_SHOWN_KEY] = _PAGE

    limit = st.session_state.get(_SHOWN_KEY, _PAGE)
    cards = "".join(_news_card(r) for _, r in shown.head(limit).iterrows())
    st.markdown(f'<div class="sc-news">{cards}</div>', unsafe_allow_html=True)

    if limit < len(shown):
        if st.button(f"더 보기  ({limit} / {len(shown)}건)", use_container_width=True):
            st.session_state[_SHOWN_KEY] = limit + _PAGE
            st.rerun()
    else:
        st.caption(f"전체 {len(shown)}건을 모두 표시했습니다.")
