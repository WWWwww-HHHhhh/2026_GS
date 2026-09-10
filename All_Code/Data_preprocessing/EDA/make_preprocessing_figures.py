# -*- coding: utf-8 -*-
"""生成论文第 6 章（数据预处理）所需的三张图。

输入：Data_preprocessing/Data_clean 下的 *_clean.csv
输出：Data_preprocessing/Figures/fig6_*.pdf
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.normpath(os.path.join(HERE, ".."))
CLEAN = os.path.join(BASE, "Data_clean")
OUT = os.path.join(BASE, "Figures")
os.makedirs(OUT, exist_ok=True)


def read_wide(name: str):
    df = pd.read_csv(os.path.join(CLEAN, name))
    tcols = [c for c in df.columns if c != df.columns[0]]
    vals = df[tcols].astype(float)
    return df, tcols, vals


def time_axis():
    minutes = np.arange(1, 145) * 10
    ticks = np.arange(0, 1441, 240)
    labels = [f"{int(m // 60)}:00" for m in ticks]
    return minutes, ticks, labels


# ---------------- 图 1：附件 1 单日（典型日）曲线 ----------------
p1 = pd.read_csv(os.path.join(CLEAN, "附件1_clean.csv"))
minutes, ticks, labels = time_axis()

fig, axes = plt.subplots(3, 1, figsize=(7.2, 7.4), sharex=True)
axes[0].plot(minutes, p1["电价"], color="C3", lw=1.4)
axes[0].set_ylabel("电价（元/kWh）")
axes[0].set_title("(a) 电价", loc="left", fontsize=10)
axes[1].plot(minutes, p1["小区负载"], color="C0", lw=1.4)
axes[1].set_ylabel("负载（kW）")
axes[1].set_title("(b) 小区负载", loc="left", fontsize=10)
axes[2].plot(minutes, p1["光伏发电预测功率"], color="C2", lw=1.4)
axes[2].set_ylabel("光伏（kW）")
axes[2].set_xlabel("时刻")
axes[2].set_title("(c) 光伏发电预测功率", loc="left", fontsize=10)
axes[2].set_xticks(ticks)
axes[2].set_xticklabels(labels)
for ax in axes:
    ax.grid(alpha=0.3, lw=0.5)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig6_typical_day.pdf"), bbox_inches="tight")
plt.close(fig)

# ---------------- 图 2：全年逐月均值与季节性 ----------------
load_df, _, load = read_wide("附件2_load_clean.csv")
pv_df, _, pv = read_wide("附件2_pv_clean.csv")
price_df, _, price = read_wide("附件4_clean.csv")

mon = pd.to_datetime(load_df.iloc[:, 0]).dt.month.to_numpy()
load_m = pd.DataFrame(load.to_numpy()).groupby(mon).mean().mean(axis=1)
pv_m = pd.DataFrame(pv.to_numpy()).groupby(mon).mean().mean(axis=1)
price_m = pd.DataFrame(price.to_numpy()).groupby(mon).mean().mean(axis=1)
months = np.arange(1, 13)

fig, axes = plt.subplots(3, 1, figsize=(7.2, 7.4), sharex=True)
axes[0].plot(months, load_m, "o-", color="C0")
axes[0].set_ylabel("负载均值（kW）")
axes[0].set_title("(a) 小区负载月均值", loc="left", fontsize=10)
axes[1].plot(months, pv_m, "s-", color="C2")
axes[1].set_ylabel("光伏均值（kW）")
axes[1].set_title("(b) 光伏功率月均值", loc="left", fontsize=10)
axes[2].plot(months, price_m, "^-", color="C3")
axes[2].set_ylabel("电价均值（元/kWh）")
axes[2].set_xlabel("月份")
axes[2].set_title("(c) 电价月均值", loc="left", fontsize=10)
axes[2].set_xticks(months)
for ax in axes:
    ax.grid(alpha=0.3, lw=0.5)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig6_monthly.pdf"), bbox_inches="tight")
plt.close(fig)

# ---------------- 图 3：全年数值分布 ----------------
fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.0))
axes[0].hist(load.to_numpy().ravel(), bins=60, color="C0", edgecolor="white")
axes[0].set_xlabel("负载（kW）")
axes[0].set_ylabel("频数")
axes[0].set_title("(a) 小区负载分布", fontsize=10)
axes[1].hist(pv.to_numpy().ravel(), bins=60, color="C2", edgecolor="white")
axes[1].set_xlabel("光伏（kW）")
axes[1].set_title("(b) 光伏功率分布", fontsize=10)
axes[2].hist(price.to_numpy().ravel(), bins=60, color="C3", edgecolor="white")
axes[2].set_xlabel("电价（元/kWh）")
axes[2].set_title("(c) 电价分布", fontsize=10)
for ax in axes:
    ax.grid(alpha=0.3, lw=0.5)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig6_distribution.pdf"), bbox_inches="tight")
plt.close(fig)

print("已生成：")
for f in ["fig6_typical_day.pdf", "fig6_monthly.pdf", "fig6_distribution.pdf"]:
    print(" ", os.path.join(OUT, f))
