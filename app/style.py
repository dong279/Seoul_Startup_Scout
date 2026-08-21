"""app/style.py — 전역 CSS (UI 계층 · 표시 전용)

로직이 없다. `app/main.py`가 `st.set_page_config()` 직후 `inject()`를 한 번
호출하면 끝이고, 그 호출을 지우면 Streamlit 기본 화면으로 완전히 돌아온다.

**선택자 원칙**: `st-emotion-cache-*` 는 버전마다 바뀌는 해시라 쓰지 않는다.
Streamlit이 테스트 훅으로 유지하는 `data-testid` / `data-baseweb` 속성만 쓴다
(streamlit 1.39 기준). 컴포넌트용 `.sc-*` 클래스는 `app/ui.py` 가 만든다.
"""
from __future__ import annotations

import streamlit as st

CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.css');

:root{
  --sc-brand:#2E5C8A;  --sc-brand-2:#1E3A5F;  --sc-brand-3:#3E82B0;
  --sc-accent:#D94F4F;
  --sc-ink:#0F172A;    --sc-ink-2:#334155;    --sc-muted:#64748B;  --sc-faint:#94A3B8;
  --sc-line:#E7EBF0;   --sc-line-2:#F1F5F9;
  --sc-bg:#FFFFFF;     --sc-soft:#F7F9FC;
  --sc-r:14px;         --sc-r-sm:10px;
  --sc-sh:0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.03);
  --sc-sh-2:0 8px 24px rgba(15,23,42,.08);
  --sc-font:'Pretendard Variable',Pretendard,-apple-system,BlinkMacSystemFont,'Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR',sans-serif;
}

html,body,[data-testid="stAppViewContainer"],[data-testid="stSidebar"]{
  font-family:var(--sc-font);
  -webkit-font-smoothing:antialiased;
  color:var(--sc-ink);
}
[data-testid="stAppViewContainer"]{ background:var(--sc-soft); }
[data-testid="stHeader"]{ background:transparent; }
footer{ visibility:hidden; height:0; }

.block-container{ padding-top:1.6rem; padding-bottom:3.5rem; max-width:1480px; }

h1,h2,h3,h4,h5{ letter-spacing:-.02em; color:var(--sc-ink); }
[data-testid="stCaptionContainer"] p{ color:var(--sc-muted); font-size:.84rem; }

/* 앱바 */
.sc-appbar{
  display:flex; align-items:center; gap:1rem; flex-wrap:wrap;
  background:linear-gradient(120deg,var(--sc-brand-2) 0%,var(--sc-brand) 58%,var(--sc-brand-3) 100%);
  border-radius:18px; padding:1.15rem 1.5rem; margin-bottom:1rem;
  box-shadow:0 10px 28px rgba(30,58,95,.20); position:relative; overflow:hidden;
}
.sc-appbar::after{
  content:""; position:absolute; right:-80px; top:-120px; width:300px; height:300px;
  border-radius:50%; background:radial-gradient(circle,rgba(255,255,255,.18),rgba(255,255,255,0) 62%);
}
.sc-mark{
  width:42px; height:42px; flex:0 0 42px; border-radius:12px;
  background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.26);
  display:flex; align-items:center; justify-content:center; font-size:1.25rem; z-index:1;
}
.sc-appbar-txt{ z-index:1; min-width:220px; flex:1 1 320px; }
.sc-appbar-title{ font-size:1.32rem; font-weight:800; color:#fff; letter-spacing:-.03em; line-height:1.25; }
.sc-appbar-sub{ font-size:.86rem; color:rgba(255,255,255,.82); margin-top:.18rem; line-height:1.5; }
.sc-chips{ display:flex; flex-wrap:wrap; gap:.4rem; z-index:1; }
.sc-chip{
  font-size:.735rem; font-weight:600; color:#fff; white-space:nowrap;
  background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.24);
  padding:.3rem .68rem; border-radius:999px;
}

/* 모드 네비 (st.radio) */
[data-testid="stRadio"]>div[role="radiogroup"]{ gap:.4rem; }
[data-testid="stRadio"] label{
  border:1px solid var(--sc-line); background:var(--sc-bg); border-radius:999px;
  padding:.5rem 1.15rem; cursor:pointer; box-shadow:var(--sc-sh);
  transition:background .15s ease,border-color .15s ease,box-shadow .15s ease,transform .15s ease;
}
[data-testid="stRadio"] label>div:first-child{ display:none; }
[data-testid="stRadio"] label p{ font-weight:600; color:var(--sc-ink-2); font-size:.9rem; }
[data-testid="stRadio"] label:hover{ border-color:var(--sc-brand-3); transform:translateY(-1px); }
[data-testid="stRadio"] label:has(input:checked){
  background:var(--sc-brand); border-color:var(--sc-brand); box-shadow:var(--sc-sh-2);
}
[data-testid="stRadio"] label:has(input:checked) p{ color:#fff; font-weight:700; }

/* KPI */
.sc-kpis{ display:grid; grid-template-columns:repeat(auto-fit,minmax(196px,1fr)); gap:.8rem; margin:.2rem 0 1.1rem; }
.sc-kpi{
  position:relative; overflow:hidden; background:var(--sc-bg);
  border:1px solid var(--sc-line); border-radius:var(--sc-r);
  padding:.95rem 1.1rem .9rem; box-shadow:var(--sc-sh);
  transition:box-shadow .18s ease,transform .18s ease,border-color .18s ease;
}
.sc-kpi::before{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px;
  background:linear-gradient(180deg,var(--sc-brand),var(--sc-brand-3)); }
.sc-kpi:hover{ box-shadow:var(--sc-sh-2); transform:translateY(-2px); border-color:#D8E1EB; }
.sc-kpi-h{ display:flex; align-items:center; gap:.4rem; margin-bottom:.4rem; }
.sc-kpi-ico{ font-size:.9rem; line-height:1; }
.sc-kpi-lab{ font-size:.775rem; font-weight:600; color:var(--sc-muted); }
.sc-kpi-val{ font-size:1.62rem; font-weight:800; line-height:1.12; letter-spacing:-.035em; color:var(--sc-ink); }
.sc-kpi-unit{ font-size:.85rem; font-weight:700; color:var(--sc-muted); margin-left:.14rem; }
.sc-kpi-foot{ margin-top:.34rem; font-size:.715rem; color:var(--sc-faint); line-height:1.45; }

/* 섹션 */
.sc-sec{ margin:1.35rem 0 .8rem; padding-left:.78rem; border-left:3px solid var(--sc-brand); }
.sc-sec-t{ font-size:1.04rem; font-weight:800; color:var(--sc-ink); letter-spacing:-.02em; }
.sc-sec-d{ margin-top:.2rem; font-size:.835rem; color:var(--sc-muted); line-height:1.6; }

/* 뉴스 카드 */
.sc-news{ display:grid; grid-template-columns:repeat(auto-fill,minmax(340px,1fr)); gap:.8rem; }
.sc-card{
  display:flex; flex-direction:column; background:var(--sc-bg);
  border:1px solid var(--sc-line); border-radius:var(--sc-r);
  padding:1rem 1.1rem; box-shadow:var(--sc-sh);
  transition:box-shadow .18s ease,transform .18s ease,border-color .18s ease;
}
.sc-card:hover{ box-shadow:var(--sc-sh-2); transform:translateY(-2px); border-color:#D8E1EB; }
.sc-card-h{ display:flex; align-items:center; gap:.45rem; margin-bottom:.55rem; }
.sc-badge{ font-size:.7rem; font-weight:700; padding:.2rem .55rem; border-radius:6px; white-space:nowrap; }
.sc-date{ font-size:.72rem; color:var(--sc-faint); margin-left:auto; }
.sc-card-t{ font-size:.955rem; font-weight:700; line-height:1.45; color:var(--sc-ink); letter-spacing:-.015em; }
.sc-card-t a{ color:inherit; text-decoration:none; }
.sc-card-t a:hover{ color:var(--sc-brand); text-decoration:underline; text-underline-offset:3px; }
.sc-card-s{
  margin-top:.45rem; font-size:.815rem; line-height:1.62; color:var(--sc-muted);
  display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;
}
.sc-card-f{ margin-top:.75rem; padding-top:.6rem; border-top:1px solid var(--sc-line-2); }
.sc-card-f a{ font-size:.775rem; font-weight:600; color:var(--sc-brand); text-decoration:none; }
.sc-card-f a:hover{ text-decoration:underline; text-underline-offset:3px; }

/* 빈 상태 */
.sc-empty{
  text-align:center; padding:3.2rem 1.5rem; background:var(--sc-bg);
  border:1px dashed #D4DDE7; border-radius:16px;
}
.sc-empty-i{ font-size:2rem; opacity:.55; }
.sc-empty-t{ margin-top:.65rem; font-size:1.01rem; font-weight:700; color:var(--sc-ink); }
.sc-empty-b{ margin-top:.32rem; font-size:.865rem; color:var(--sc-muted); line-height:1.68; }

/* 푸터 */
.sc-foot{
  margin-top:2.2rem; padding-top:1.1rem; border-top:1px solid var(--sc-line);
  font-size:.755rem; color:var(--sc-faint); line-height:1.7;
}

/* Streamlit 기본 요소 다듬기 */
[data-testid="stSidebar"]{ background:var(--sc-bg); border-right:1px solid var(--sc-line); }
[data-testid="stSidebar"] .block-container{ padding-top:1.4rem; }
[data-testid="stSidebar"] h2{ font-size:1rem; font-weight:800; }

[data-testid="stMetric"]{
  background:var(--sc-bg); border:1px solid var(--sc-line);
  border-radius:var(--sc-r-sm); padding:.85rem 1rem; box-shadow:var(--sc-sh);
}
[data-testid="stMetricLabel"] p{ font-size:.78rem; font-weight:600; color:var(--sc-muted); }
[data-testid="stMetricValue"]{ font-size:1.35rem; font-weight:800; color:var(--sc-brand); letter-spacing:-.03em; }

.stTabs [data-baseweb="tab-list"]{ gap:.3rem; border-bottom:1px solid var(--sc-line); }
.stTabs [data-baseweb="tab"]{
  height:auto; padding:.58rem 1.05rem; border-radius:10px 10px 0 0;
  font-weight:600; color:var(--sc-muted);
}
.stTabs [data-baseweb="tab"]:hover{ background:var(--sc-soft); color:var(--sc-ink); }
.stTabs [aria-selected="true"]{ color:var(--sc-brand); background:var(--sc-soft); }
.stTabs [data-baseweb="tab-highlight"]{ background:var(--sc-brand); height:3px; }

[data-testid="stDataFrame"]{
  border:1px solid var(--sc-line); border-radius:var(--sc-r); overflow:hidden; background:var(--sc-bg);
}
[data-testid="stPlotlyChart"]{
  border:1px solid var(--sc-line); border-radius:var(--sc-r);
  padding:.45rem; background:var(--sc-bg); box-shadow:var(--sc-sh);
}
[data-testid="stExpander"]{
  border:1px solid var(--sc-line); border-radius:var(--sc-r); background:var(--sc-bg);
}
[data-testid="stExpander"] summary{ font-weight:600; color:var(--sc-ink-2); }
[data-testid="stAlert"]{ border-radius:var(--sc-r-sm); border:1px solid var(--sc-line); }
[data-testid="stVerticalBlockBorderWrapper"]{ border-radius:var(--sc-r); }

.stButton>button,[data-testid="stLinkButton"] a{
  border-radius:9px; font-weight:600; border-color:var(--sc-line);
  transition:transform .12s ease,box-shadow .12s ease,border-color .12s ease;
}
.stButton>button:hover,[data-testid="stLinkButton"] a:hover{
  transform:translateY(-1px); box-shadow:var(--sc-sh-2); border-color:var(--sc-brand-3);
}

[data-baseweb="select"]>div,[data-testid="stTextInput"] input{
  border-radius:9px; border-color:var(--sc-line);
}
[data-baseweb="tag"]{ background:var(--sc-brand)!important; border-radius:7px!important; }

hr{ margin:1.1rem 0; border-color:var(--sc-line); }

::-webkit-scrollbar{ width:10px; height:10px; }
::-webkit-scrollbar-thumb{ background:#CBD5E1; border-radius:8px; border:2px solid var(--sc-soft); }
::-webkit-scrollbar-thumb:hover{ background:#94A3B8; }
::-webkit-scrollbar-track{ background:transparent; }
</style>
"""


def inject() -> None:
    """CSS를 한 번 주입한다. `st.set_page_config()` 바로 다음에 호출한다."""
    st.markdown(CSS, unsafe_allow_html=True)
