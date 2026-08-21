"""app/theme.py — 차트 공통 테마 (plotly 전용 · UI 계층)

`views_*.py` 를 한 줄도 고치지 않고 전 화면의 차트를 같은 스타일로 묶기 위한 파일이다.
로직은 없다.

**동작 원리**: 뷰들이 `px.bar(..., template="plotly_white")` 처럼 템플릿 이름을 직접
넘긴다. 새 이름을 등록해도 뷰가 부르지 않으면 적용되지 않으므로, **`plotly_white`
라는 이름 자체를 우리 테마로 재정의**한다. 템플릿을 명시하지 않은 차트는 `default`
로 같은 테마를 받는다. `apply()` 호출을 지우면 전부 plotly 기본 모양으로 돌아온다.
"""
from __future__ import annotations

import copy

import plotly.io as pio

FONT = ("Pretendard Variable, Pretendard, -apple-system, BlinkMacSystemFont, "
        "Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, sans-serif")

INK = "#0F172A"
MUTED = "#64748B"
LINE = "#E7EBF0"
GRID = "#F1F5F9"

# 색 지정이 없는 차트가 쓰는 계열. common/viz.py 의 유형 색과 톤을 맞춘다.
COLORWAY = ["#2E5C8A", "#3AA6A6", "#E8A33D", "#D94F4F",
            "#7B4FA8", "#4C956C", "#B5651D", "#5D8AA8"]

TEMPLATE_NAME = "scout"


def _build():
    """plotly_white 을 상속해 골격만 교체한다.

    바닥부터 만들면 연속형 색상 스케일 같은 기본값이 비어 일부 차트가 회색으로
    떨어진다. 상속받아 덮어쓰는 편이 안전하다.
    """
    tpl = copy.deepcopy(pio.templates["plotly_white"])
    axis = dict(
        gridcolor=GRID,
        linecolor=LINE,
        zerolinecolor=LINE,
        ticks="outside",
        tickcolor=LINE,
        ticklen=6,
        tickfont=dict(size=11.5, color=MUTED),
        title=dict(font=dict(size=12, color=MUTED)),
        automargin=True,
    )
    tpl.layout.update(
        font=dict(family=FONT, size=12.5, color=INK),
        title=dict(font=dict(family=FONT, size=15.5, color=INK),
                   x=0, xanchor="left", y=0.97, pad=dict(b=14)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        colorway=COLORWAY,
        xaxis=axis,
        yaxis=axis,
        legend=dict(
            font=dict(size=11.5, color=INK),
            bgcolor="rgba(255,255,255,.92)",
            bordercolor=LINE,
            borderwidth=1,
            itemsizing="constant",
        ),
        hoverlabel=dict(
            bgcolor="#0F172A",
            bordercolor="rgba(0,0,0,0)",
            font=dict(family=FONT, size=12, color="#FFFFFF"),
            align="left",
        ),
        margin=dict(l=16, r=16, t=52, b=16),
        separators=".,",
    )
    return tpl


def apply() -> None:
    """전역 plotly 테마를 등록한다. main.py 시작 시 1회 호출."""
    tpl = _build()
    pio.templates[TEMPLATE_NAME] = tpl
    pio.templates.default = TEMPLATE_NAME
    pio.templates["plotly_white"] = tpl      # 뷰가 이름을 명시하므로 함께 덮는다
