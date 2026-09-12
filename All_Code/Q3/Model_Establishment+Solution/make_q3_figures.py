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

HERE = Path(__file__).resolve().parent
TABLES = HERE.parent / "Results" / "Tables"
FIGURES = HERE.parent / "Results" / "Pictures"
FIGURES.mkdir(parents=True, exist_ok=True)

ORDER = ("S0", "S6", "S12", "S18", "S6_12", "Sall")
LABELS = {"S0": "仅0:00", "S6": "+6:00", "S12": "+12:00", "S18": "+18:00",
          "S6_12": "+6:00,12:00", "Sall": "+6:00,12:00,18:00"}
SPECIFIED = ("2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21")

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei"],
    "axes.unicode_minus": False,
    "font.size": 10, "axes.linewidth": 0.7, "figure.dpi": 150,
    "savefig.bbox": "tight",
})
C_BASE, C_BLUE, C_ORANGE, C_GREEN, C_RED, C_SOC = "#667085", "#4E79A7", "#F28E2B", "#2E7D32", "#B94040", "#5B7B8C"


def fig1_strategy_cost(report: dict) -> dict:
    """六策略全年实际费用对比"""
    costs = np.array([x["total_cost_yuan"] for x in report["strategies"]]) / 1e6
    baseline = report["Q2_baseline_yuan"] / 1e6
    x = np.arange(len(ORDER))
    fig, ax = plt.subplots(figsize=(7.6, 3.6), layout="constrained")
    colors = [C_BASE, C_BLUE, C_BLUE, C_ORANGE, C_GREEN, C_GREEN]
    bars = ax.bar(x, costs, color=colors, width=0.62)
    ax.axhline(baseline, color=C_RED, ls="--", lw=1.2, label=f"Q2 点预测基线 {baseline:.3f} 百万元")
    ax.set_xticks(x, [LABELS[k] for k in ORDER], fontsize=9)
    ax.set_ylim(min(costs.min(), baseline) - 0.02, max(costs.max(), baseline) + 0.09)
    ax.set_ylabel("全年实际购电费用 / 百万元")
    for bar, v in zip(bars, costs):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.008, f"{v:.3f}", ha="center", fontsize=9)
    ax.grid(axis="y", alpha=0.18); ax.set_axisbelow(True); ax.legend(frameon=False, fontsize=9)
    fig.savefig(FIGURES / "q3_fig1_strategy_cost.pdf"); fig.savefig(FIGURES / "q3_fig1_strategy_cost.png", dpi=220)
    fig.savefig(FIGURES / "q3_fig1_strategy_cost.svg")
    plt.close(fig)
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
    """四个预报时刻的转换误差（MAE 与 WAPE，线性插值 vs 阶梯保持）"""
    a = pd.read_csv(TABLES / "forecast_conversion_audit.csv")
    lin = a[a["conversion"] == "linear_endpoint"].set_index("issue_hour")
    step = a[a["conversion"] == "step"].set_index("issue_hour")
    hours = [0, 6, 12, 18]
    x = np.arange(len(hours)); w = 0.36
    fig, ax1 = plt.subplots(figsize=(7.2, 3.5), layout="constrained")
    b1 = ax1.bar(x - w / 2, [lin.loc[h, "MAE_kwh_per_slot"] for h in hours], w,
                 color=C_BLUE, label="线性插值 MAE")
    b2 = ax1.bar(x + w / 2, [step.loc[h, "MAE_kwh_per_slot"] for h in hours], w,
                 color="#A9C0DC", label="阶梯保持 MAE")
    ax1.set_xticks(x, [f"{h}:00 发布\n线性插值 WAPE {lin.loc[h,'WAPE']*100:.1f}%" for h in hours])
    ax1.set_ylabel("剩余时段平均绝对误差 / (kWh/时段)")
    ax1.bar_label(b1, fmt="%.1f", fontsize=8, padding=1)
    ax1.bar_label(b2, fmt="%.1f", fontsize=8, padding=1)
    ax1.set_ylim(0, max(step["MAE_kwh_per_slot"].max(), lin["MAE_kwh_per_slot"].max()) * 1.28)
    ax1.legend(frameon=False, fontsize=9, ncol=2, loc="upper right")
    ax1.grid(axis="y", alpha=0.18); ax1.set_axisbelow(True)
    fig.savefig(FIGURES / "q3_fig3_forecast_conversion_error.pdf"); fig.savefig(FIGURES / "q3_fig3_forecast_conversion_error.png", dpi=220)
    fig.savefig(FIGURES / "q3_fig3_forecast_conversion_error.svg")
    plt.close(fig)


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
