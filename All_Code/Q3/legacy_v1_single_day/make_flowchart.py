from __future__ import annotations

import sys
from pathlib import Path


Q3_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DEPS = Q3_ROOT / ".deps"
if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from config import ProjectPaths


def _box(ax, x, y, width, height, text, face, edge="#1F4E79", size=11):
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.025,rounding_size=0.025",
        facecolor=face,
        edgecolor=edge,
        linewidth=1.5,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=size,
        color="#172B3A",
        linespacing=1.35,
    )
    return patch


def _arrow(ax, start, end, color="#46697F", style="-|>", curve=0.0):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=13,
        linewidth=1.35,
        color=color,
        connectionstyle=f"arc3,rad={curve}",
        shrinkA=4,
        shrinkB=4,
    )
    ax.add_patch(arrow)


def create_flowchart() -> tuple[Path, Path]:
    paths = ProjectPaths.discover()
    paths.result_pictures.mkdir(parents=True, exist_ok=True)
    png_path = paths.result_pictures / "Q3_滚动决策流程图.png"
    svg_path = paths.result_pictures / "Q3_滚动决策流程图.svg"

    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(11.0, 9.0))
    fig.patch.set_facecolor("#F7F9FC")
    ax.set_facecolor("#F7F9FC")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.965,
        "问题三，多时点预报下的购电计划与储能滚动决策",
        ha="center",
        va="center",
        fontsize=17,
        fontweight="bold",
        color="#173A52",
    )
    ax.text(
        0.5,
        0.927,
        "计划只在官方时点更新，储能在 10 分钟尺度滚动，实际状态逐段回写",
        ha="center",
        va="center",
        fontsize=10.5,
        color="#527184",
    )

    main_x, main_w, h = 0.12, 0.56, 0.077
    y_positions = [0.82, 0.705, 0.59, 0.475, 0.36, 0.245, 0.13]
    texts = [
        "数据与 Q2 公共口径\n负荷，光伏，电价，SOC 与历史联合残差",
        "0 点生成联合场景并求零点计划\n得到基准购电计划 x0 和储能参考轨迹",
        "到达 6 点，12 点或 18 点\n读取附件 3 最新光伏预报，冻结已执行区间",
        "求解剩余日场景滚动 LP\n允许策略指定时点更新 q，其余时点固定 q",
        "只执行当前 10 分钟储能动作\n计划电提取满足 y ≤ q，不足部分紧急购电",
        "写回实测负荷，光伏与实际 SOC\n检查平衡，容量，功率和安全裁剪量",
        "日末按最终计划相对零点计划一次结算\n汇总费用，紧急购电，弃光和终端偏差",
    ]
    colors = ["#E9F2F9", "#DCECF7", "#FFF3D9", "#E4F1EC", "#EAF0FA", "#F0EAF8", "#DDEDE5"]
    for y, text_value, color in zip(y_positions, texts, colors):
        _box(ax, main_x, y, main_w, h, text_value, color)
    for upper, lower in zip(y_positions[:-1], y_positions[1:]):
        _arrow(ax, (main_x + main_w / 2, upper), (main_x + main_w / 2, lower + h))

    _box(
        ax,
        0.745,
        0.61,
        0.21,
        0.17,
        "购电更新策略\nS0\nS0 加 6 点\nS0 加 12 点\nS0 加 18 点\n全部更新",
        "#FFFFFF",
        edge="#B27A18",
        size=10.5,
    )
    _arrow(ax, (0.745, 0.69), (main_x + main_w, 0.63), color="#B27A18")

    _box(
        ax,
        0.745,
        0.34,
        0.21,
        0.15,
        "窗口目标\n期望真实结算费用\n加 CVaR 风险项\n加软终端偏差代价",
        "#FFFFFF",
        edge="#3E7E67",
        size=10.5,
    )
    _arrow(ax, (0.745, 0.415), (main_x + main_w, 0.50), color="#3E7E67")

    _arrow(
        ax,
        (main_x, 0.282),
        (main_x, 0.743),
        color="#6E5A8B",
        curve=-0.27,
    )
    ax.text(
        0.027,
        0.505,
        "下一官方时点继续滚动",
        rotation=90,
        ha="center",
        va="center",
        fontsize=10,
        color="#6E5A8B",
    )

    ax.text(
        0.5,
        0.045,
        "主结果采用最终一次结算口径，逐次结算仅作为敏感性分析",
        ha="center",
        va="center",
        fontsize=10,
        color="#5D6D78",
    )
    fig.savefig(png_path, dpi=320, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(svg_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return png_path, svg_path


if __name__ == "__main__":
    png, svg = create_flowchart()
    print(png)
    print(svg)
