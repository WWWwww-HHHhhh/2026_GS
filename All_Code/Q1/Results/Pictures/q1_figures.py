# -*- coding: utf-8 -*-
"""
问题1 结果图：4 张 PDF 矢量图（图内不写大标题，论文中引用时加题注）。

输入数据：All_Code/Q1/Tables/q1_timeseries.csv（先运行 q1_model.py 生成）
运行方法：python q1_figures.py（依赖 numpy/pandas/matplotlib）
输出位置：All_Code/Q1/Pictures/（q1_fig1_timeseries.pdf 等 4 张）
论文引用：../All_Code/Q1/Pictures/q1_figX_*.pdf
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

Q1_DIR = Path(__file__).resolve().parents[1]
FIG = Q1_DIR / "Pictures"
FIG.mkdir(exist_ok=True)
d = pd.read_csv(Q1_DIR / "Tables" / "q1_timeseries.csv")

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei"],
    "axes.unicode_minus": False,
    "font.size": 9, "axes.linewidth": 0.6,
    "figure.dpi": 150, "savefig.bbox": "tight",
})

# 暖调低饱和配色
C_PRICE = "#C15F3C"   # 赤陶橙
C_LOAD = "#4A4A48"
C_PV = "#D9A441"
C_NET = "#7A8B6F"
C_GRID = "#8C6D5D"
C_SOC = "#5B7B8C"

hours = (np.arange(144) + 0.5) / 6.0  # 时段中点（h）
DT = 1 / 6

# 图1：电价、负荷、光伏、净负荷时序
fig, ax1 = plt.subplots(figsize=(6.4, 2.8))
ax1.plot(hours, d.L_kwh / DT / 1000, color=C_LOAD, lw=1.0, label="小区负载")
ax1.plot(hours, d.G_kwh / DT / 1000, color=C_PV, lw=1.0, label="光伏预测")
ax1.plot(hours, (d.L_kwh - d.G_kwh) / DT / 1000, color=C_NET, lw=1.0, ls="--", label="净负荷")
ax1.set_xlabel("时刻 / h"); ax1.set_ylabel("功率 / MW")
ax1.set_xlim(0, 24); ax1.set_xticks(range(0, 25, 4))
ax2 = ax1.twinx()
ax2.plot(hours, d.price, color=C_PRICE, lw=1.2, label="电价")
ax2.set_ylabel("电价 / (元/kWh)")
h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, ncol=4, frameon=False, fontsize=8, loc="upper left")
fig.savefig(FIG / "q1_fig1_timeseries.pdf"); plt.close(fig)

# 图2：计划购电、光伏利用、充电、放电、弃光组合（功率口径）
fig, ax = plt.subplots(figsize=(6.4, 2.8))
ax.plot(hours, d.x_plan_kwh / DT / 1000, color=C_GRID, lw=1.1, label="计划购电")
ax.plot(hours, (d.G_kwh - d.w_curtail_kwh) / DT / 1000, color=C_PV, lw=1.0, label="光伏利用")
ax.plot(hours, d.c_charge_kwh / DT / 1000, color=C_SOC, lw=1.0, label="储能充电")
ax.plot(hours, -d.r_discharge_kwh / DT / 1000, color=C_PRICE, lw=1.0, label="储能放电(负值)")
ax.plot(hours, d.w_curtail_kwh / DT / 1000, color="#999999", lw=0.8, ls=":", label="弃光")
ax.axhline(0, color="k", lw=0.5)
ax.set_xlabel("时刻 / h"); ax.set_ylabel("功率 / MW")
ax.set_xlim(0, 24); ax.set_xticks(range(0, 25, 4))
ax.legend(ncol=5, frameon=False, fontsize=8, loc="lower center",
          bbox_to_anchor=(0.5, 1.01), borderaxespad=0)
fig.subplots_adjust(top=0.84)
fig.savefig(FIG / "q1_fig2_dispatch.pdf"); plt.close(fig)

# 图3：SOC 轨迹与上下限
fig, ax = plt.subplots(figsize=(6.4, 2.6))
soc_full = np.concatenate([[6000.0], d.soc_kwh.to_numpy()])
ax.plot(np.arange(145) / 6.0, soc_full / 1000, color=C_SOC, lw=1.2, label="SOC")
ax.axhline(10.8, color=C_PRICE, lw=0.8, ls="--", label="上限 10800 kWh")
ax.axhline(1.2, color=C_PRICE, lw=0.8, ls="-.", label="下限 1200 kWh")
ax.set_xlabel("时刻 / h"); ax.set_ylabel("储电量 / MWh")
ax.set_xlim(0, 24); ax.set_xticks(range(0, 25, 4))
ax.legend(ncol=3, frameon=False, fontsize=8, loc="lower center",
          bbox_to_anchor=(0.5, 1.01), borderaxespad=0)
fig.subplots_adjust(top=0.84)
fig.savefig(FIG / "q1_fig3_soc.pdf"); plt.close(fig)

# 图4：电价与储能边际价值（-mu_soc）双轴
fig, ax1 = plt.subplots(figsize=(6.4, 2.8))
ax1.plot(hours, d.price, color=C_PRICE, lw=1.2, label="电价")
ax1.set_xlabel("时刻 / h"); ax1.set_ylabel("电价 / (元/kWh)")
ax1.set_xlim(0, 24); ax1.set_xticks(range(0, 25, 4))
ax2 = ax1.twinx()
ax2.step(hours, -d.mu_soc, color=C_SOC, lw=1.2, where="mid", label="储能边际价值")
ax2.set_ylabel("储能边际价值 / (元/kWh)")
h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, ncol=2, frameon=False, fontsize=8, loc="upper left")
fig.savefig(FIG / "q1_fig4_marginal_value.pdf"); plt.close(fig)

print("figures saved:", [p.name for p in sorted(FIG.glob('q1_fig*.pdf'))])
