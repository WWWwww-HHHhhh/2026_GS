from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

HERE = Path(__file__).resolve().parent
TABLES = HERE.parent / "Results" / "Tables"
FIGURES = HERE.parent / "Results" / "Pictures"
FIGURES.mkdir(parents=True, exist_ok=True)
REPO = HERE.parents[3]

C_FIXED = "#8C6D5D"   # 固定电价（褐）
C_FLUC = "#C15F3C"    # 波动电价（赤陶橙）
C_BLUE = "#3A6EA5"


def fig1_price_curves() -> None:
    """附件4 波动电价 vs 附件1 固定电价（典型日 + 多日均价）。"""
    a1 = pd.read_excel(REPO / "Data" / "附件" / "附件1.xlsx", header=0).iloc[:, 1].to_numpy(float)
    a4 = pd.read_excel(REPO / "Data" / "附件" / "附件4.xlsx", header=0)
    vals = a4.iloc[:, 1:145].to_numpy(float).T  # (144,365)
    h = np.arange(144) / 6.0
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    # 左：连续7天的波动电价 vs 固定电价
    for d in range(31, 38):
        axes[0].plot(h, vals[:, d], color=C_FLUC, alpha=0.35, lw=0.8)
    axes[0].plot(h, a1, color="k", lw=1.8, label="附件1 固定电价（每天相同）")
    axes[0].plot(h, vals[:, 31], color=C_FLUC, lw=1.5, alpha=0.9, label="附件4 波动电价（2025-02-01 起一周）")
    axes[0].set_xlabel("时刻 / h"); axes[0].set_ylabel("电价 / (元/kWh)")
    axes[0].set_title("(a) 波动电价 vs 固定电价（单日曲线）")
    axes[0].legend(frameon=False, fontsize=8)
    # 右：全年日均价分布
    day_mean = vals.mean(0)
    axes[1].plot(np.arange(365), day_mean, color=C_FLUC, lw=1.0)
    axes[1].axhline(a1.mean(), color="k", ls="--", lw=1.2, label=f"附件1均价 {a1.mean():.4f}")
    axes[1].set_xlabel("日期（2025 年 day 序）"); axes[1].set_ylabel("日均价 / (元/kWh)")
    axes[1].set_title("(b) 附件4 日均价全年波动")
    axes[1].legend(frameon=False, fontsize=8)
    for ax in axes:
        ax.grid(alpha=0.25, lw=0.5)
    fig.tight_layout()
    for ext in ("pdf", "png", "svg"):
        fig.savefig(FIGURES / f"q4_fig1_price_curves.{ext}", dpi=220)
    plt.close(fig)


def fig2_strategy_cost() -> None:
    """波动 vs 固定电价六策略费用对比（分组柱状）。"""
    q3 = pd.read_csv(HERE.parents[2] / "Q3" / "Results" / "Tables" / "strategy_summary.csv")
    q4 = pd.read_csv(TABLES / "strategy_summary.csv")
    m = q3[["strategy", "total_cost_yuan"]].merge(
        q4[["strategy", "total_cost_yuan"]], on="strategy", suffixes=("_fixed", "_fluc"))
    order = ["S0", "S6", "S12", "S18", "S6_12", "Sall"]
    labels = ["仅0:00", "+6:00", "+12:00", "+18:00", "+6,12", "+6,12,18"]
    m = m.set_index("strategy").loc[order].reset_index()
    x = np.arange(len(order)); w = 0.38
    fig, ax = plt.subplots(figsize=(8, 3.8))
    b1 = ax.bar(x - w/2, m.total_cost_yuan_fixed/1e4, w, color=C_FIXED, label="固定电价(Q3)")
    b2 = ax.bar(x + w/2, m.total_cost_yuan_fluc/1e4, w, color=C_FLUC, label="波动电价(Q4)")
    ax.bar_label(b1, fmt="%.0f", fontsize=7, padding=1)
    ax.bar_label(b2, fmt="%.0f", fontsize=7, padding=1)
    ax.set_xticks(x, labels)
    ax.set_ylabel("全年总费用 / 万元")
    ax.set_title("波动电价 vs 固定电价：六种更新策略全年费用")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.25, axis="y", lw=0.5)
    ax.set_ylim(0, m.total_cost_yuan_fluc.max()/1e4 * 1.12)
    fig.tight_layout()
    for ext in ("pdf", "png", "svg"):
        fig.savefig(FIGURES / f"q4_fig2_strategy_cost.{ext}", dpi=220)
    plt.close(fig)


def fig3_update_value() -> None:
    """更新价值（S0-最优）在固定 vs 波动电价下的对比。"""
    q3 = pd.read_csv(HERE.parents[2] / "Q3" / "Results" / "Tables" / "strategy_summary.csv")
    q4 = pd.read_csv(TABLES / "strategy_summary.csv")
    def value(df):
        s0 = df[df.strategy == "S0"].total_cost_yuan.iloc[0]
        return {s: s0 - df[df.strategy == s].total_cost_yuan.iloc[0]
                for s in ["S6", "S12", "S18", "S6_12", "Sall"]}
    vf, vl = value(q3), value(q4)
    keys = list(vf)
    x = np.arange(len(keys)); w = 0.38
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    b1 = ax.bar(x - w/2, [vf[k]/1e4 for k in keys], w, color=C_FIXED, label="固定电价(Q3)")
    b2 = ax.bar(x + w/2, [vl[k]/1e4 for k in keys], w, color=C_FLUC, label="波动电价(Q4)")
    ax.bar_label(b1, fmt="%.1f", fontsize=7, padding=1)
    ax.bar_label(b2, fmt="%.1f", fontsize=7, padding=1)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(x, ["+6:00", "+12:00", "+18:00", "+6,12", "+6,12,18"])
    ax.set_ylabel("相对仅0:00计划的费用节省 / 万元")
    ax.set_title("引入更新的价值：波动电价下反而更大（18 点仍为负）")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.25, axis="y", lw=0.5)
    fig.tight_layout()
    for ext in ("pdf", "png", "svg"):
        fig.savefig(FIGURES / f"q4_fig3_update_value.{ext}", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    fig1_price_curves()
    fig2_strategy_cost()
    fig3_update_value()
    print("已生成 q4_fig1~3 (pdf/png/svg) 到", FIGURES)
