"""app/theme.py — 차트 공통 테마 (plotly 전용 · UI 계층)

**views_*.py 를 한 줄도 고치지 않고** 4개 화면의 차트를 같은 스타일로 묶기 위한
파일이다. 로직은 없다.

**동작 원리**: 기존 뷰들이 `px.bar(..., template="plotly_white")` 처럼 템플릿
이름을 직접 넘기고 있다. 그래서 새 이름을 만들어 봐야 뷰가 그걸 부르지 않으면
적용되지 않는다. 대신 **`plotly_white` 라는 이름 자체를 우리 테마로 재정의**한다
— 뷰 코드는 그대로 두고 결과만 바뀐다. 템플릿을 명시하지 않은 차트(역방향
막대)는 `default` 로 같은 테마를 받는다.

`apply()` 를 `app/main.py` 가 시작할 때 한 번 부르면 끝이고, 그 호출을 지우면
전부 원래 plotly 기본 모양으로 돌아온다.

색은 `common/viz.py` 의 TYPE_COLORS 계열을 따른다 (노트북 PNG와 톤을 맞추기 위해).
유형별 색 자체는 뷰가 `color_discrete_map` 으로 직접 지정하므로 여기서 건드리지
않는다 — 이 파일이 맡는 것은 **글꼴·격자·여백·툴팁·범례** 같은 공통 골격이다.
"""
from __future__ import annotations

import copy

import plotly.io as pio

FONT = ("Pretendard Variable, Pretendard, -apple-system, BlinkMacSystemFont, "
        "Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, sans-serif")

NAVY = "#2E5C8A"
INK = "#1F2937"
MUTED = "#6B7280"
LINE = "#E9EDF2"
GRID = "#F1F4F8"

# 유형 색과 부딪히지 않는 보조 계열 (색 지정이 없는 차트가 쓴다)
COLORWAY = ["#2E5C8A", "#3AA6A6", "#E8A33D", "#D94F4F",
            "#7B4FA8", "#4C956C", "#B5651D", "#8C8C8C"]

TEMPLATE_NAME = "seoul_scout"


def _build():
    """plotly_white 을 바탕으로 깔되 골격만 갈아끼운다.

    바닥부터 만들면 연속형 색상 스케일 같은 기본값이 통째로 비어 일부 차트가
    회색으로 떨어진다. 상속받아 덮어쓰는 편이 안전하다.
    """
    tpl = copy.deepcopy(pio.templates["plotly_white"])
    axis = dict(
        gridcolor=GRID,
        linecolor=LINE,
        zerolinecolor=LINE,
        ticks="outside",
        tickcolor=LINE,
        ticklen=5,
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
            bgcolor="rgba(255,255,255,.9)",
            bordercolor=LINE,
            borderwidth=1,
            itemsizing="constant",
        ),
        hoverlabel=dict(
            bgcolor="#111827",
            bordercolor="rgba(0,0,0,0)",
            font=dict(family=FONT, size=12, color="#FFFFFF"),
            align="left",
        ),
        margin=dict(l=16, r=16, t=52, b=16),
        separators=".,",          # 천 단위 구분 — 매출 축이 읽히게
    )
    return tpl


def apply() -> None:
    """전역 plotly 테마를 등록한다. main.py 시작 시 1회 호출."""
    tpl = _build()
    pio.templates[TEMPLATE_NAME] = tpl
    pio.templates.default = TEMPLATE_NAME
    # 뷰들이 이름을 명시하고 있으므로 그 이름도 같은 내용으로 덮는다.
    pio.templates["plotly_white"] = tpl
