"""app/style.py — 대시보드 표시 스타일 (CSS 주입 전용 · UI 계층)

**여기에는 로직이 없다.** 데이터 변환·점수 계산은 `app/logic.py`,
위젯·레이아웃은 `app/main.py`·`app/views_*.py`가 담당하고, 이 파일은
"같은 화면을 어떻게 보이게 할 것인가"만 맡는다. `main.py`가 페이지 최상단에서
`inject()`를 한 번 호출하면 끝이고, 호출을 지우면 원래 기본 화면으로 돌아온다.

**별도 파일로 둔 이유**: CSS를 `main.py` 안에 문자열로 넣으면 위젯 흐름이
150줄 밀려 읽기 어려워진다. 또 이 파일은 신규 파일이라 다른 브랜치와
충돌하지 않는다 — `main.py` 쪽 변경은 import 1줄 + 호출 1줄뿐이다.

**선택자 원칙**: Streamlit의 `st-emotion-cache-*` 클래스명은 버전마다 바뀌는
해시라 절대 쓰지 않는다. `data-testid`와 `data-baseweb`처럼 Streamlit이
테스트 훅으로 유지하는 속성만 사용한다 (streamlit 1.39 기준 확인).
"""
from __future__ import annotations

import streamlit as st

# ── 색 토큰 ───────────────────────────────────────────────────────────
# common/viz.py 의 TYPE_COLORS 와 같은 계열을 쓴다. 노트북 그래프(matplotlib)와
# 앱 화면(HTML/plotly)이 같은 색으로 읽히게 하려는 것이다.
NAVY = "#2E5C8A"     # 주색 — 유형 팔레트의 기준색
RED = "#D94F4F"      # 강조 — 기회 영역 주석과 동일
INK = "#1F2937"      # 본문 글자
MUTED = "#6B7280"    # 보조 설명
LINE = "#E5E7EB"     # 경계선
SOFT = "#F4F6F9"     # 연한 바탕

CSS = f"""
<style>
/* Pretendard — 없으면 아래 폴백 스택으로 자연히 내려간다(오프라인에서도 안전). */
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.css');

:root {{
  --ss-navy: {NAVY};
  --ss-red: {RED};
  --ss-ink: {INK};
  --ss-muted: {MUTED};
  --ss-line: {LINE};
  --ss-soft: {SOFT};
  --ss-radius: 12px;
  --ss-shadow: 0 1px 2px rgba(16, 24, 40, .04);
  --ss-shadow-hover: 0 6px 18px rgba(16, 24, 40, .08);
}}

html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
  font-family: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont,
               'Malgun Gothic', 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
  -webkit-font-smoothing: antialiased;
}}

/* ── 페이지 여백 ─────────────────────────────────────────────────────
   기본 상단 여백이 6rem 가까이 잡혀 첫 화면에서 표가 접힌다. */
.block-container {{
  padding-top: 2.2rem;
  padding-bottom: 3rem;
  max-width: 1440px;
}}
[data-testid="stHeader"] {{ background: transparent; }}

/* 시연 녹화용 — 하단 "Made with Streamlit" 제거.
   개발 중 메뉴가 필요하면 아래 #MainMenu 만 빼면 된다. */
footer {{ visibility: hidden; height: 0; }}

h1 {{ font-weight: 800; letter-spacing: -.025em; color: var(--ss-ink); }}
h2, h3 {{ font-weight: 700; letter-spacing: -.015em; color: var(--ss-ink); }}
h5 {{ font-weight: 700; color: var(--ss-ink); }}

/* ── 상단 탐색 모드 라디오 → 세그먼트 버튼 ───────────────────────────
   앱에 라디오는 이 하나(main.py 탐색 모드)뿐이라 전역 선택자로 안전하다. */
[data-testid="stRadio"] > div[role="radiogroup"] {{ gap: .5rem; }}
[data-testid="stRadio"] label {{
  border: 1px solid var(--ss-line);
  background: #fff;
  border-radius: 999px;
  padding: .5rem 1.15rem;
  cursor: pointer;
  transition: background .15s ease, border-color .15s ease, box-shadow .15s ease;
}}
[data-testid="stRadio"] label:hover {{
  border-color: var(--ss-navy);
  background: var(--ss-soft);
}}
[data-testid="stRadio"] label > div:first-child {{ display: none; }}  /* 동그라미 숨김 */
[data-testid="stRadio"] label:has(input:checked) {{
  background: var(--ss-navy);
  border-color: var(--ss-navy);
  box-shadow: var(--ss-shadow-hover);
}}
[data-testid="stRadio"] label:has(input:checked) p {{ color: #fff; font-weight: 700; }}

/* ── 요약 지표 카드화 ────────────────────────────────────────────────
   st.metric 4개가 나란히 서는 구간이 첫 화면의 인상을 좌우한다. */
[data-testid="stMetric"] {{
  position: relative;
  background: #fff;
  border: 1px solid var(--ss-line);
  border-radius: var(--ss-radius);
  padding: 1rem 1.1rem 1rem 1.35rem;
  box-shadow: var(--ss-shadow);
  transition: box-shadow .18s ease, transform .18s ease;
}}
[data-testid="stMetric"]:hover {{
  box-shadow: var(--ss-shadow-hover);
  transform: translateY(-1px);
}}
[data-testid="stMetric"]::before {{      /* 좌측 액센트 바 */
  content: "";
  position: absolute;
  left: 0; top: 14px; bottom: 14px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--ss-navy);
}}
[data-testid="stMetricLabel"] p {{
  font-size: .82rem;
  font-weight: 600;
  color: var(--ss-muted);
}}
[data-testid="stMetricValue"] {{
  font-size: 1.65rem;
  font-weight: 800;
  color: var(--ss-navy);
  letter-spacing: -.02em;
}}

/* ── 탭 ──────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
  gap: .35rem;
  border-bottom: 1px solid var(--ss-line);
}}
.stTabs [data-baseweb="tab"] {{
  height: auto;
  padding: .6rem 1.1rem;
  border-radius: 10px 10px 0 0;
  font-weight: 600;
  color: var(--ss-muted);
}}
.stTabs [data-baseweb="tab"]:hover {{ background: var(--ss-soft); color: var(--ss-ink); }}
.stTabs [aria-selected="true"] {{ color: var(--ss-navy); background: var(--ss-soft); }}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--ss-navy); height: 3px; }}

/* ── 사이드바 ────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
  background: var(--ss-soft);
  border-right: 1px solid var(--ss-line);
}}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.6rem; }}
[data-testid="stSidebar"] h2 {{ font-size: 1.05rem; font-weight: 800; }}

/* ── 표·차트·안내 박스 ───────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
  border: 1px solid var(--ss-line);
  border-radius: var(--ss-radius);
  overflow: hidden;
}}
[data-testid="stPlotlyChart"] {{
  border: 1px solid var(--ss-line);
  border-radius: var(--ss-radius);
  padding: .4rem;
  background: #fff;
}}
[data-testid="stExpander"] {{
  border: 1px solid var(--ss-line);
  border-radius: var(--ss-radius);
  background: #fff;
}}
[data-testid="stExpander"] summary {{ font-weight: 600; color: var(--ss-ink); }}
[data-testid="stAlert"] {{ border-radius: 10px; }}
[data-testid="stCaptionContainer"] p {{ color: var(--ss-muted); }}

/* ── 버튼 ───────────────────────────────────────────────────────── */
.stButton > button, [data-testid="stLinkButton"] a {{
  border-radius: 8px;
  font-weight: 600;
  transition: transform .12s ease, box-shadow .12s ease;
}}
.stButton > button:hover, [data-testid="stLinkButton"] a:hover {{
  transform: translateY(-1px);
  box-shadow: var(--ss-shadow-hover);
}}

hr {{ margin: 1.2rem 0; border-color: var(--ss-line); }}

/* ══════════════════════════════════════════════════════════════════
   여기서부터는 app/ui.py 가 그리는 컴포넌트 전용 스타일이다.
   ui.py 를 안 쓰면 아래 규칙은 매칭되는 요소가 없어 아무 일도 하지 않는다.
   ══════════════════════════════════════════════════════════════════ */

/* ── 히어로 헤더 ─────────────────────────────────────────────────── */
.ss-hero {{
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  background: linear-gradient(135deg, #16304D 0%, #2E5C8A 54%, #3E82B0 100%);
  padding: 2.05rem 2.3rem 1.85rem;
  margin: 0 0 1.55rem;
  box-shadow: 0 10px 30px rgba(22, 48, 77, .22);
}}
.ss-hero-glow {{
  position: absolute; right: -90px; top: -130px;
  width: 340px; height: 340px; border-radius: 50%;
  background: radial-gradient(circle, rgba(255,255,255,.22), rgba(255,255,255,0) 62%);
}}
.ss-hero-body {{ position: relative; z-index: 1; }}
.ss-eyebrow {{
  font-size: .7rem; font-weight: 700; letter-spacing: .22em;
  color: rgba(255,255,255,.72); margin-bottom: .5rem;
}}
.ss-hero-title {{
  font-size: 2.05rem; font-weight: 800; letter-spacing: -.03em;
  color: #fff; line-height: 1.16;
}}
.ss-hero-sub {{
  margin-top: .5rem; font-size: .97rem; line-height: 1.62;
  color: rgba(255,255,255,.84); max-width: 66ch;
}}
.ss-chips {{ margin-top: 1.05rem; display: flex; flex-wrap: wrap; gap: .45rem; }}
.ss-chip {{
  font-size: .755rem; font-weight: 600; color: #fff;
  background: rgba(255,255,255,.14);
  border: 1px solid rgba(255,255,255,.24);
  padding: .32rem .72rem; border-radius: 999px;
}}

/* ── 지표 카드 ───────────────────────────────────────────────────── */
.ss-kpi-row {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: .85rem;
  margin: .1rem 0 1.35rem;
}}
.ss-kpi {{
  position: relative; overflow: hidden;
  background: #fff;
  border: 1px solid var(--ss-line);
  border-radius: 14px;
  padding: 1.0rem 1.15rem .95rem;
  box-shadow: var(--ss-shadow);
  transition: box-shadow .18s ease, transform .18s ease, border-color .18s ease;
}}
.ss-kpi::after {{
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
  background: linear-gradient(180deg, var(--ss-navy), #3E82B0);
}}
.ss-kpi:hover {{
  box-shadow: var(--ss-shadow-hover);
  transform: translateY(-2px);
  border-color: #D5DEE8;
}}
.ss-kpi-head {{ display: flex; align-items: center; gap: .4rem; margin-bottom: .45rem; }}
.ss-kpi-icon {{ font-size: .95rem; line-height: 1; }}
.ss-kpi-label {{ font-size: .785rem; font-weight: 600; color: var(--ss-muted); }}
.ss-kpi-value {{
  font-size: 1.7rem; font-weight: 800; line-height: 1.1;
  color: var(--ss-ink); letter-spacing: -.03em;
}}
.ss-kpi-unit {{ font-size: .88rem; font-weight: 700; color: var(--ss-muted); margin-left: .15rem; }}
.ss-kpi-foot {{ margin-top: .4rem; font-size: .725rem; color: #9AA3AF; }}

/* ── 섹션 제목 ───────────────────────────────────────────────────── */
.ss-section {{ margin: 1.45rem 0 .85rem; padding-left: .8rem; border-left: 3px solid var(--ss-navy); }}
.ss-section-title {{ font-size: 1.05rem; font-weight: 800; color: var(--ss-ink); letter-spacing: -.015em; }}
.ss-section-desc {{ margin-top: .18rem; font-size: .84rem; color: var(--ss-muted); line-height: 1.55; }}

/* ── 빈 상태 ─────────────────────────────────────────────────────── */
.ss-empty {{
  text-align: center;
  padding: 3rem 1.5rem;
  border: 1px dashed #D7DEE7;
  border-radius: 16px;
  background: var(--ss-soft);
}}
.ss-empty-icon {{ font-size: 2.1rem; opacity: .6; }}
.ss-empty-title {{ margin-top: .65rem; font-size: 1.02rem; font-weight: 700; color: var(--ss-ink); }}
.ss-empty-body {{ margin-top: .3rem; font-size: .87rem; color: var(--ss-muted); line-height: 1.65; }}

/* ── 스크롤바 ────────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 8px; border: 2px solid #fff; }}
::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}
::-webkit-scrollbar-track {{ background: transparent; }}
</style>
"""


def inject() -> None:
    """CSS를 한 번 주입한다. `st.set_page_config()` 바로 다음에 호출한다."""
    st.markdown(CSS, unsafe_allow_html=True)
