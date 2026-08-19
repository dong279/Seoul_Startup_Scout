# common/viz.py — 한글 폰트 + 유형별 색상 팔레트. 노트북·앱 전원이 import한다.
# 환경별 폰트 차이로 그래프 축이 □□□로 깨지는 것을 방지한다. 첫 셀에서 setup() 호출.
import platform
import matplotlib.pyplot as plt
import seaborn as sns

# 유형별 색상 — 노트북 그래프와 앱 지도 마커가 같은 색을 쓰도록 여기서 고정한다.
TYPE_COLORS = {
    "오피스 밀집형":   "#2E5C8A",
    "상업·번화형":     "#D94F4F",
    "청년 밀집형":     "#E8A33D",
    "가족 주거형":     "#4C956C",
    "일반 주거·생활형": "#8C8C8C",
    "발달상권형":      "#7B4FA8",
    "전통시장형":      "#B5651D",
    "관광특구형":      "#3AA6A6",
}


def setup(font_size: int = 11) -> None:
    """한글 폰트 + 마이너스 기호 + seaborn 테마를 한 번에 설정한다."""
    system = platform.system()
    if system == "Darwin":
        family = "AppleGothic"
    elif system == "Windows":
        family = "Malgun Gothic"
    else:                                  # Linux (배포·CI 환경)
        family = "NanumGothic"
    plt.rc("font", family=family, size=font_size)
    plt.rcParams["axes.unicode_minus"] = False   # 음수 부호가 □로 깨지는 것 방지
    sns.set_theme(style="whitegrid", font=family, rc={"axes.unicode_minus": False})


def palette(types) -> list:
    """유형 리스트를 받아 TYPE_COLORS 순서대로 색 리스트를 반환한다.
    seaborn의 palette= 인자에 그대로 넣는다."""
    return [TYPE_COLORS.get(t, "#8C8C8C") for t in types]


def save(fig, name: str, outdir: str = "reports/figures") -> str:
    """PNG로 저장하고 경로를 돌려준다. 발표 자료·README에 재사용한다."""
    import os
    os.makedirs(outdir, exist_ok=True)
    path = f"{outdir}/{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    return path
