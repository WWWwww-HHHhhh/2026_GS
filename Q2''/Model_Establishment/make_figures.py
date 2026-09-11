# -*- coding: utf-8 -*-
"""Q2'' 图表生成（真实结果，PNG+PDF）。"""
import os, pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q2P = os.path.join(GS, "Q2''")
DATA_PROC = os.path.join(Q2P, "Data_processing")
TABLES = os.path.join(Q2P, "Results", "Tables")
PICS = os.path.join(Q2P, "Results", "Pictures")
os.makedirs(PICS, exist_ok=True)

def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(PICS, name + ".png"), dpi=160)
    fig.savefig(os.path.join(PICS, name + ".pdf"))
    plt.close(fig)
    print("saved", name)

log = pd.read_csv(os.path.join(TABLES, "daily_rolling_log.csv"), encoding="utf-8-sig")
log["date"] = pd.to_datetime(log["date"]); log["month"] = log["date"].dt.month
report = log[log.day_index >= 31]

# 图1 逐日费用与紧急购电率
fig, ax1 = plt.subplots(figsize=(10,4.2))
ax1.plot(report.date, report.cost_total/10000, lw=0.7, color="#1f77b4")
ax1.set_ylabel("日总费用（万元）"); ax1.set_xlabel("日期")
ax2 = ax1.twinx()
ax2.plot(report.date, report.emergency_rate*100, lw=0.6, color="#d62728", alpha=0.8)
ax2.set_ylabel("紧急购电率（%）", color="#d62728"); ax2.tick_params(axis="y", labelcolor="#d62728")
save(fig, "fig1_daily_cost_emergency")

# 图2 日末储能电量
fig, ax = plt.subplots(figsize=(10,3.6))
ax.plot(report.date, report.final_soc, lw=0.8, color="#2ca02c")
ax.axhline(1200, color="red", ls="--", lw=0.8); ax.axhline(10800, color="red", ls="--", lw=0.8)
ax.set_ylabel("日末储电量（kWh）"); ax.set_xlabel("日期")
save(fig, "fig2_soc_trajectory")

# 图3 月度计划/紧急费用
g = report.groupby("month").agg(plan=("cost_plan","sum"), emg=("cost_emergency","sum"))
fig, ax = plt.subplots(figsize=(8,4))
ax.bar(g.index, g.plan/10000, label="计划购电费", color="#1f77b4")
ax.bar(g.index, g.emg/10000, bottom=g.plan/10000, label="紧急购电费", color="#d62728")
ax.set_ylabel("月度费用（万元）"); ax.set_xlabel("月份"); ax.set_xticks(list(range(2,13))); ax.legend()
save(fig, "fig3_monthly_cost")

# 图4 月度紧急率与弃光率
m = report.groupby("month").agg(emg=("emergency_rate","mean"), cur=("curtailment_rate","mean"))
fig, ax = plt.subplots(figsize=(8,4))
ax.plot(m.index, m.emg*100, "o-", label="紧急购电率(%)")
ax.plot(m.index, m.cur*100, "s-", label="弃光率(%)")
ax.set_xlabel("月份"); ax.set_xticks(list(range(2,13))); ax.legend()
save(fig, "fig4_monthly_rates")

# 图5 预测月度WAPE
fdf = pd.read_csv(os.path.join(TABLES, "forecast_monthly_metrics.csv"))
fig, ax = plt.subplots(figsize=(8,4))
for s,color in [("load","#1f77b4"),("pv","#ff7f0e")]:
    sub=fdf[fdf.series==s]
    ax.plot(sub.month, sub.WAPE*100, "o-", label="负荷WAPE(%)" if s=="load" else "光伏WAPE(%)", color=color)
ax.set_xlabel("月份"); ax.set_xticks(list(range(2,13))); ax.legend()
save(fig, "fig5_forecast_wape")

print("FIGURES_DONE")
