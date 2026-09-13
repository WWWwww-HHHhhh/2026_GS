"""生成问题三论文插图（仓库版：读 Results/Tables，写 Results/Pictures）。

输入：All_Code/Q3/Results/Tables/ 下的 validation_report.json、strategy_summary.csv、
      forecast_conversion_audit.csv、<策略>/daily.csv、Sall/intervals.csv
输出：All_Code/Q3/Results/Pictures/q3_fig1..fig6（PNG + SVG）
运行：python make_q3_figures.py   （依赖 numpy/pandas/matplotlib）
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.patheffects import Normal, Stroke

HERE = Path(__file__).resolve().parent
TABLES = HERE.parent / "Results" / "Tables"
FIGURES = HERE.parent / "Results" / "Pictures"
FIGURES.mkdir(parents=True, exist_ok=True)

ORDER = ("S0", "S6", "S12", "S18", "S6_12", "Sall")
LABELS = {"S0": "仅0:00", "S6": "+6:00", "S12": "+12:00", "S18": "+18:00",
          "S6_12": "+6:00,12:00", "Sall": "+6:00,12:00,18:00"}
SPECIFIED = ("2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21")

# Q2 点预测基线的费用拆分（冻结的接口常量）。
# 来源：All_Code/Q2_yy/Results/Tables/validated_cost_summary.csv，
# 两者之和 = run_metadata.json 的 Q2_baseline_total_yuan = 14,708,963.49 元。
Q2_BASE_PLAN_YUAN = 13885012.62256014
Q2_BASE_EMERGENCY_YUAN = 823950.8718955689

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei"],
    "axes.unicode_minus": False,
    "font.size": 10, "axes.linewidth": 0.7, "figure.dpi": 150,
    "savefig.bbox": "tight",
})
C_BLUE, C_ORANGE, C_GREEN, C_RED, C_SOC = "#4E79A7", "#F28E2B", "#2E7D32", "#B94040", "#5B7B8C"
C_INK, C_MUTED, C_GRID, C_CARD = "#283C4A", "#6B7B87", "#E7ECF0", "#FAFBFC"


def tint(color, factor: float):
    """把颜色朝白色方向稀释：factor=1 原色，factor=0 纯白。"""
    r, g, b = to_rgb(color)
    return (1 - (1 - r) * factor, 1 - (1 - g) * factor, 1 - (1 - b) * factor)


def gradient_seg(ax, p0, p1, color, lw, bands: int = 34, tint_lo: float = 0.34,
                 zorder: int = 3):
    """两点之间的渐变连线：起点浅、终点饱和，用多段短线叠出来（纯矢量）。

    渐变靠 tint() 逐段稀释，而不是 imshow —— imshow 会在 PDF 里留下光栅块，
    放大后糊掉；叠线段在 PDF 里仍是矢量。
    """
    x0, y0 = p0
    x1, y1 = p1
    for k in range(bands):
        f0, f1 = k / bands, (k + 1) / bands
        factor = tint_lo + (1.0 - tint_lo) * ((k + 0.5) / bands)
        ax.plot([x0 + (x1 - x0) * f0, x0 + (x1 - x0) * f1],
                [y0 + (y1 - y0) * f0, y0 + (y1 - y0) * f1],
                color=tint(color, factor), lw=lw, solid_capstyle="butt",
                zorder=zorder)


def gradient_seg2(ax, p0, p1, c0, c1, lw, bands: int = 44, zorder: int = 3):
    """两点之间的双色渐变连线（起点 c0 → 终点 c1），纯矢量。

    横向哑铃用：连线从「线性插值」的颜色渐变到「阶梯保持」的颜色，
    读者不需要看图例就知道这根线把两种方法连在了一起。
    """
    x0, y0 = p0
    x1, y1 = p1
    a0, a1 = np.array(to_rgb(c0)), np.array(to_rgb(c1))
    for k in range(bands):
        f0, f1 = k / bands, (k + 1) / bands
        t = (k + 0.5) / bands
        base = a0 + (a1 - a0) * t
        # 蓝→橙在 RGB 里直接插值，中段会掉到灰褐色；按 sin 曲线提亮中段即可干净过渡
        lift = np.sin(np.pi * t) * 0.34
        col = tuple(base + (1.0 - base) * lift)
        ax.plot([x0 + (x1 - x0) * f0, x0 + (x1 - x0) * f1],
                [y0 + (y1 - y0) * f0, y0 + (y1 - y0) * f1],
                color=col, lw=lw, solid_capstyle="butt", zorder=zorder)


def tidy_axes(ax, grid_axis: str = "y"):
    """统一坐标区：卡片底 + 浅网格 + 去上/右轴脊。"""
    ax.set_facecolor(C_CARD)
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=C_GRID, linewidth=0.7)
    ax.tick_params(axis="both", length=3, color="#A6B1BA", labelsize=9.5,
                   labelcolor=C_INK)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color("#B5C0C8")


def halo(linewidth: float = 2.6):
    """文字白描边：压在网格线/参考线上也能认出来。"""
    return [Stroke(linewidth=linewidth, foreground="white"), Normal()]


def save_fig(fig, stem: str):
    """同时输出 PDF（投稿）+ PNG（预览）+ SVG。"""
    fig.savefig(FIGURES / f"{stem}.pdf")
    fig.savefig(FIGURES / f"{stem}.png", dpi=220)
    fig.savefig(FIGURES / f"{stem}.svg")
    plt.close(fig)


def fig1_strategy_cost(report: dict) -> dict:
    """六策略全年实际费用 vs Q2 点预测基线：哑铃图（基线点 → 策略点）。

    原图是截断纵轴的柱状图（纵轴从 14.5 起），把 0.358 百万元（约 2.4%）的真实差异
    放大成视觉上的数倍差——好看但不诚实。哑铃图的横轴保留绝对费用，连线长度就是
    与基线的差额：省/超支方向与量级同时可见，且不会误导读者以为差了十几倍。
    """
    costs = np.array([x["total_cost_yuan"] for x in report["strategies"]]) / 1e6
    baseline = report["Q2_baseline_yuan"] / 1e6
    summary = pd.read_csv(TABLES / "strategy_summary.csv").set_index("strategy")
    d_plan = np.array([summary.loc[k, "market_cost_yuan"] for k in ORDER]) - Q2_BASE_PLAN_YUAN
    d_emg = np.array([summary.loc[k, "emergency_cost_yuan"] for k in ORDER]) - Q2_BASE_EMERGENCY_YUAN

    y = np.arange(len(ORDER), dtype=float)
    fig, ax = plt.subplots(figsize=(8.4, 4.6), layout="constrained")
    fig.get_layout_engine().set(rect=(0.0, 0.115, 1.0, 0.885))
    tidy_axes(ax, grid_axis="x")

    best = int(np.argmin(costs))
    ax.axhspan(best - 0.44, best + 0.44, color=tint(C_GREEN, 0.10), zorder=0)
    ax.axvline(baseline, color=C_RED, ls=(0, (4, 3)), lw=1.1, zorder=2)

    for i, cost in enumerate(costs):
        color = C_GREEN if cost < baseline else C_RED
        gradient_seg(ax, (baseline, y[i]), (cost, y[i]), color, 5.0,
                     tint_lo=0.30, zorder=3)
        ax.scatter([baseline], [y[i]], s=58, color="#9AA4B2", edgecolors="white",
                   linewidths=1.3, zorder=5)
        ax.scatter([cost], [y[i]], s=235, color=tint(color, 0.22),
                   edgecolors="none", zorder=5)
        ax.scatter([cost], [y[i]], s=150, color=color, edgecolors="white",
                   linewidths=1.5, zorder=6)
        delta_wan = (cost - baseline) * 100
        ax.annotate(f"{delta_wan:+,.2f} 万元", xy=(cost, y[i]), xytext=(0, 12),
                    textcoords="offset points", ha="center", va="bottom",
                    fontsize=8.8, color=color, zorder=7, path_effects=halo())
        ax.text(0.995, y[i] - 0.17, f"{cost:.3f}",
                transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=9.2, color=C_INK, zorder=7)
        ax.text(0.995, y[i] + 0.18, f"({delta_wan / (baseline * 100) * 100:+.2f}%)",
                transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=8.4, color=color, zorder=7)

    ax.set_yticks(y, [LABELS[k] for k in ORDER])
    ax.set_ylim(len(ORDER) - 0.42, -0.92)
    ax.set_xlim(14.40, 15.05)
    ax.set_xticks(np.arange(14.4, 15.0, 0.1))
    ax.set_xlabel("全年实际购电费用 / 百万元", color=C_INK)
    ax.text(baseline + 0.007, -0.66, f"Q2 点预测基线 {baseline:.3f} 百万元",
            ha="left", va="center", fontsize=8.8, color=C_RED, zorder=7,
            path_effects=halo())
    ax.text(0.995, -0.66, "总费用 / 百万元", transform=ax.get_yaxis_transform(),
            ha="right", va="center", fontsize=8.8, color=C_MUTED, zorder=7)

    span = costs.max() - costs.min()
    fig.text(0.5, 0.005,
             f"注：横轴已放大至差异区间（全距 {span:.3f} 百万元，约 {span / baseline * 100:.1f}%），"
             f"灰点为 Q2 基线、彩色点为策略实际值，连线长度即与基线的差额。\n"
             f"六策略的日前计划购电费均高于基线（{d_plan.min() / 1e4:+.2f} ~ {d_plan.max() / 1e4:+.2f} 万元），"
             f"费用下降全部来自紧急购电费减少（{d_emg.min() / 1e4:+.2f} ~ {d_emg.max() / 1e4:+.2f} 万元）。",
             ha="center", va="bottom", fontsize=8.2, color=C_MUTED)
    save_fig(fig, "q3_fig1_strategy_cost")
    return dict(zip(ORDER, costs.tolist()))


def fig2_specified_day_savings() -> dict:
    """四个指定日：全更新相对仅 0:00 的节省"""
    days = {n: pd.read_csv(TABLES / n / "daily.csv").set_index("date") for n in ORDER}
    savings = np.array([days["S0"].loc[d, "total_cost_yuan"] - days["Sall"].loc[d, "total_cost_yuan"]
                        for d in SPECIFIED])
    x = np.arange(len(SPECIFIED))
    fig, ax = plt.subplots(figsize=(6.6, 3.4), layout="constrained")
    ax.bar(x, savings, color=[C_GREEN if v >= 0 else C_RED for v in savings], width=0.55)
    ax.axhline(0, color="#303030", lw=0.8)
    ax.set_xticks(x, [d[5:] for d in SPECIFIED])
    ax.set_xlabel("指定日期（2025 年）"); ax.set_ylabel("S0 费用 − 全更新费用 / 元")
    for i, v in enumerate(savings):
        ax.annotate(f"{v:+,.0f}", (i, v), xytext=(0, 4 if v >= 0 else -13),
                    textcoords="offset points", ha="center", fontsize=9)
    ax.grid(axis="y", alpha=0.18); ax.set_axisbelow(True)
    fig.savefig(FIGURES / "q3_fig2_specified_day_savings.pdf"); fig.savefig(FIGURES / "q3_fig2_specified_day_savings.png", dpi=220)
    fig.savefig(FIGURES / "q3_fig2_specified_day_savings.svg")
    plt.close(fig)
    return dict(zip(SPECIFIED, savings.tolist()))


def fig3_forecast_error() -> None:
    """四个发布时刻的转换误差：线性插值 vs 阶梯保持（横向哑铃图）。

    两种转换方式只有两个水平，横向哑铃比竖向斜率图更适合宽扁排版：
    斜率图一旦拉宽，折线会被压平，"斜率=倍数"这个读法就废了；
    哑铃图把每一行压成一根水平连线，行高与图宽无关，拉多宽都还能读。
    连线用双色渐变（蓝=线性插值 → 橙=阶梯保持），左右两端直标绝对值，
    上方标 ×N 倍数——四个时刻的 ×N 全部大于 1，即阶梯保持全面更差。
    """
    a = pd.read_csv(TABLES / "forecast_conversion_audit.csv")
    lin = a[a["conversion"] == "linear_endpoint"].set_index("issue_hour")
    step = a[a["conversion"] == "step"].set_index("issue_hour")
    hours = [0, 6, 12, 18]
    v_lin = [float(lin.loc[h, "MAE_kwh_per_slot"]) for h in hours]
    v_step = [float(step.loc[h, "MAE_kwh_per_slot"]) for h in hours]
    y = np.arange(len(hours), dtype=float)

    fig, ax = plt.subplots(figsize=(11.2, 3.4), layout="constrained")
    fig.get_layout_engine().set(rect=(0.0, 0.145, 1.0, 0.855))
    tidy_axes(ax, grid_axis="x")
    ax.set_ylim(len(hours) - 0.44, -0.78)
    ax.set_xlim(-5.0, 80.0)

    for i, (v0, v1) in enumerate(zip(v_lin, v_step)):
        gradient_seg2(ax, (v0, y[i]), (v1, y[i]), C_BLUE, C_ORANGE, 5.4,
                      bands=44, zorder=3)
        ax.scatter([v0], [y[i]], s=165, color=C_BLUE, edgecolors="white",
                   linewidths=1.6, zorder=5)
        ax.scatter([v1], [y[i]], s=165, color=C_ORANGE, edgecolors="white",
                   linewidths=1.6, zorder=5)
        ax.annotate(f"{v0:.1f}", xy=(v0, y[i]), xytext=(-9, 0),
                    textcoords="offset points", ha="right", va="center",
                    fontsize=9.4, color=C_BLUE, zorder=6, path_effects=halo())
        ax.annotate(f"{v1:.1f}", xy=(v1, y[i]), xytext=(9, 0),
                    textcoords="offset points", ha="left", va="center",
                    fontsize=9.4, color=C_ORANGE, zorder=6, path_effects=halo())
        ax.annotate(f"×{v1 / v0:.1f}", xy=((v0 + v1) / 2, y[i]), xytext=(0, 11),
                    textcoords="offset points", ha="center", va="bottom",
                    fontsize=8.8, color=C_INK, zorder=6, path_effects=halo())

    handles = [
        plt.Line2D([], [], color=C_BLUE, lw=0, marker="o", markersize=7.5,
                   markeredgecolor="white", label="线性插值"),
        plt.Line2D([], [], color=C_ORANGE, lw=0, marker="o", markersize=7.5,
                   markeredgecolor="white", label="阶梯保持"),
    ]
    ax.legend(handles=handles, ncol=2, frameon=False, fontsize=9.4,
              loc="lower center", bbox_to_anchor=(0.5, 1.005), borderaxespad=0,
              handlelength=0.9, columnspacing=2.6)

    ax.set_yticks(y, [f"{h}:00 发布" for h in hours])
    ax.set_xticks(np.arange(0, 81, 10))
    ax.set_xlabel("剩余时段平均绝对误差 / (kWh/时段)", color=C_INK)

    fig.text(0.5, 0.005,
             "×N 为阶梯保持相对线性插值的误差倍数，四个发布时刻全部大于 1（阶梯保持全面更差）；"
             "四个时刻的 WAPE（线性插值 → 阶梯保持）："
             + "、".join(f"{lin.loc[h, 'WAPE'] * 100:.1f}% → {step.loc[h, 'WAPE'] * 100:.1f}%"
                         for h in hours),
             ha="center", va="bottom", fontsize=8.2, color=C_MUTED)
    save_fig(fig, "q3_fig3_forecast_conversion_error")


def fig4_typical_day(day: str = "2025-06-21") -> None:
    """典型日：电价 / 光伏 / 计划购电 / SOC 四联图"""
    iv = pd.read_csv(TABLES / "Sall" / "intervals.csv", parse_dates=["date"])
    d = iv[iv["date"].dt.strftime("%Y-%m-%d") == day].sort_values("interval_index")
    h = (np.arange(len(d)) + 0.5) / 6.0
    fig, axes = plt.subplots(5, 1, figsize=(7.4, 8.6), sharex=True, layout="constrained")
    axes[0].plot(h, d["price_yuan_per_kwh"], color=C_ORANGE)
    axes[0].set_ylabel("电价 / (元/kWh)")
    axes[1].plot(h, d["load_actual_kwh"] * 6 / 1000, color="#4A4A48", label="实际负载")
    axes[1].plot(h, d["pv_actual_kwh"] * 6 / 1000, color="#D9A441", label="实际光伏")
    axes[1].set_ylabel("功率 / MW"); axes[1].legend(frameon=False, fontsize=9, ncol=2)
    axes[2].plot(h, d["final_plan_kwh"] * 6 / 1000, color=C_GREEN, lw=1.5, label="最终生效购电")
    axes[2].plot(h, d["emergency_kwh"] * 6 / 1000, color=C_RED, label="紧急购电")
    axes[2].plot(h, (d["charge_kwh"] - d["discharge_kwh"]) * 6 / 1000, color=C_SOC, lw=1.0,
                 alpha=0.85, label="储能净充电（充−放）")
    axes[2].axhline(0, color="k", lw=0.5)
    axes[2].set_ylabel("功率 / MW")
    axes[2].legend(frameon=False, fontsize=8.5, ncol=3, loc="upper center")
    diff = (d["final_plan_kwh"] - d["zero_plan_kwh"]) * 6 / 1000
    axes[3].fill_between(h, 0, diff, color=C_ORANGE, alpha=0.75, label="最终计划 − 0:00 计划")
    axes[3].axhline(0, color="k", lw=0.6)
    axes[3].set_ylabel("计划调整量 / MW")
    axes[3].legend(frameon=False, fontsize=9, loc="upper right")
    axes[3].text(0.02, 0.06, "中午光伏富余时段购电为 0，全天无同时充放",
                 transform=axes[3].transAxes, fontsize=8.5, color="#444444")
    axes[4].plot(h, d["soc_end_kwh"] / 1000, color=C_SOC)
    axes[4].axhline(10.8, color=C_RED, lw=0.8, ls="--")
    axes[4].axhline(1.2, color=C_RED, lw=0.8, ls="-.")
    axes[4].set_ylabel("储电量 / MWh"); axes[4].set_xlabel("时刻 / h")
    axes[4].set_xlim(0, 24); axes[4].set_xticks(range(0, 25, 4))
    fig.savefig(FIGURES / "q3_fig4_typical_day.pdf"); fig.savefig(FIGURES / "q3_fig4_typical_day.png", dpi=220)
    fig.savefig(FIGURES / "q3_fig4_typical_day.svg")
    plt.close(fig)


def fig5_annual_soc_heatmap() -> None:
    """全年 SOC 热力图（日期 × 时刻）"""
    iv = pd.read_csv(TABLES / "Sall" / "intervals.csv", parse_dates=["date"])
    piv = iv.pivot_table(index=iv["date"].dt.date, columns="interval_index", values="soc_end_kwh")
    fig, ax = plt.subplots(figsize=(7.6, 4.4), layout="constrained")
    im = ax.imshow(piv.values / 1000, aspect="auto", origin="lower", cmap="viridis",
                   extent=[0, 24, 0, len(piv)], vmin=1.2, vmax=10.8)
    ax.set_xlabel("时刻 / h"); ax.set_ylabel("日期序号（2025-02-01 → 2025-12-31）")
    ax.set_xticks(range(0, 25, 4))
    cb = fig.colorbar(im, ax=ax, pad=0.02); cb.set_label("储电量 / MWh")
    fig.savefig(FIGURES / "q3_fig5_annual_soc_heatmap.pdf"); fig.savefig(FIGURES / "q3_fig5_annual_soc_heatmap.png", dpi=220)
    fig.savefig(FIGURES / "q3_fig5_annual_soc_heatmap.svg")
    plt.close(fig)


def fig6_flowchart() -> None:
    """模型流程框图（中文）"""
    fig, ax = plt.subplots(figsize=(6.6, 7.6), layout="constrained")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    boxes = [
        ("附件 1/2/3 + Q2_yy 负荷预测（冻结）", 0.92),
        ("0:00 光伏整点预报 + 历史成对残差场景", 0.79),
        ("滚动随机 LP：确定 0:00 计划购电与储能安排", 0.66),
        ("按 10 分钟时段用实际负载/光伏执行，更新 SOC", 0.53),
        ("6:00 / 12:00 / 18:00 仅重优化尚未执行时段", 0.40),
        ("最终购电量相对 0:00 计划一次性结算", 0.27),
        ("六策略对照 + 334 天独立复核 + 导出 result3", 0.14),
    ]
    for label, y in boxes:
        ax.text(0.5, y, label, ha="center", va="center", fontsize=10.5,
                bbox={"boxstyle": "round,pad=0.72", "facecolor": "#EAF2F8",
                      "edgecolor": "#4472A0", "linewidth": 1.2})
    for (_, y1), (_, y2) in zip(boxes, boxes[1:]):
        ax.annotate("", xy=(0.5, y2 + 0.038), xytext=(0.5, y1 - 0.038),
                    arrowprops={"arrowstyle": "->", "color": "#4472A0", "lw": 1.4})
    fig.savefig(FIGURES / "q3_fig6_model_flowchart.pdf"); fig.savefig(FIGURES / "q3_fig6_model_flowchart.png", dpi=220)
    fig.savefig(FIGURES / "q3_fig6_model_flowchart.svg")
    plt.close(fig)


def main() -> None:
    report = json.loads((TABLES / "validation_report.json").read_text(encoding="utf-8"))
    if report["status"] != "PASS" or [x["strategy"] for x in report["strategies"]] != list(ORDER):
        raise RuntimeError("六个正式策略必须全部通过复核后才能出图")
    summary = {
        "annual_cost_million": fig1_strategy_cost(report),
        "specified_day_savings_yuan": fig2_specified_day_savings(),
    }
    fig3_forecast_error()
    fig4_typical_day()
    fig5_annual_soc_heatmap()
    fig6_flowchart()
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("figures ->", FIGURES)


if __name__ == "__main__":
    main()
