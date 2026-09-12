# -*- coding: utf-8 -*-
"""make_figures_q4_2.py —— 问题 4-2 的论文级图表（只读结果，不重算、不调参）。

产出 6 张图，每张同时输出 PDF（投稿用，矢量）与 PNG（预览用）：
  fig_q4_price_forecast      电价：逐日均价曲线 + 日内形状带 + 预测误差分位
  fig_q4_representative_day  代表日：电价/负荷/光伏 + 计划购电与提取 + 充放电 + SOC
  fig_q4_monthly_cost        逐月费用分解（计划购电费 / 紧急购电费）+ 紧急购电率
  fig_q4_plan_vs_extract     计划量 vs 提取量 vs 紧急购电的全年分布（月度）
  fig_q4_scenario_fan        代表日的价格—负荷—光伏场景扇形
  fig_q4_frontier_baseline   风险—成本前沿（β 网格）+ 基线对比

运行：cd Results/Pictures && python make_figures_q4_2.py
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

for _f in ("Microsoft YaHei", "SimHei", "DejaVu Sans"):
    if any(_f.lower() in f.name.lower() for f in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [_f]
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 120

HERE = Path(__file__).resolve().parent
WYH = HERE.parents[1]
DATA = WYH / "Data_processing"
TABLES = WYH / "Results" / "Tables"
T = 144
BANDS = [(0, 24), (24, 48), (48, 72), (72, 96), (96, 120), (120, 144)]
BAND_LABELS = ["0:00-4:00", "4:00-8:00", "8:00-12:00", "12:00-16:00", "16:00-20:00", "20:00-24:00"]
POINT_LABELS = ["10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]
POINT_IDX = [60, 72, 84, 96, 108, 120]


def save(fig, name: str) -> None:
    for ext in ("pdf", "png"):
        fig.savefig(HERE / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}.pdf/.png")


def load():
    ds = pickle.load(open(DATA / "q4_dataset.pkl", "rb"))
    res = pickle.load(open(DATA / "q4_2_rolling_results.pkl", "rb"))
    pf = pickle.load(open(DATA / "price_forecast.pkl", "rb"))
    M = int(res["params"]["M"])
    sc = pickle.load(open(DATA / f"scenarios_M{M}.pkl", "rb"))
    return ds, res, pf, sc, M


def fig_price(ds, pf):
    price = ds["price"]; Phat = pf["price_hat"]
    dates = pd.to_datetime([str(x) for x in ds["date_str"]])
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.4))
    ax = axes[0]
    ax.plot(dates, price.mean(axis=0), lw=0.9, color="#3F72AF", label="实际日均价")
    ax.plot(dates, Phat.mean(axis=0), lw=0.8, color="#D05A4E", alpha=0.85, label="因果预测日均价")
    ax.fill_between(dates, price.min(axis=0), price.max(axis=0), color="#3F72AF", alpha=0.12,
                    label="实际日内极差")
    ax.set_ylabel("电价（元/kWh）"); ax.set_xlabel("日期（2025 年）")
    ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25, lw=0.5)

    ax = axes[1]
    hh = np.arange(1, T + 1) / 6.0
    ax.fill_between(hh, np.percentile(price, 10, axis=1), np.percentile(price, 90, axis=1),
                    color="#3F72AF", alpha=0.18, label="实际 P10–P90")
    ax.plot(hh, price.mean(axis=1), color="#3F72AF", lw=1.2, label="实际均值日内形状")
    ax.plot(hh, Phat.mean(axis=1), color="#D05A4E", lw=1.0, ls="--", label="预测均值日内形状")
    ax.set_ylabel("电价（元/kWh）"); ax.set_xlabel("时刻（小时）")
    ax.set_xlim(0, 24); ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25, lw=0.5)
    fig.tight_layout(); save(fig, "fig_q4_price_forecast")


def fig_representative(ds, res, sc, M):
    logs = res["report_logs"]
    by = {l["date"]: l for l in logs}
    mdf = pd.DataFrame([{k: v for k, v in l.items() if not isinstance(v, np.ndarray)} for l in logs])
    pick = mdf.sort_values("emergency_kwh", ascending=False).iloc[0]["date"]
    l = by[pick]
    i = l["day_index"]
    t = np.arange(1, T + 1) / 6.0
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.2))

    ax = axes[0, 0]
    ax.plot(t, ds["price"][:, i], color="#D05A4E", lw=1.2, label="实际波动电价")
    ax.plot(t, np.asarray(l["price_scen"]).mean(axis=0), color="#3F72AF", lw=1.0, ls="--", label="日前预测（场景均值）")
    ax.set_ylabel("电价（元/kWh）"); ax.set_xlabel("时刻（小时）")
    ax.set_title(f"{pick} 电价：实际 vs 日前预测", fontsize=9)
    ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25, lw=0.5)

    ax = axes[0, 1]
    ax.plot(t, ds["load"][:, i], color="#2F8F67", lw=1.2, label="实际负荷")
    ax.plot(t, ds["pv"][:, i], color="#E8A33D", lw=1.2, label="实际光伏")
    ax.plot(t, np.asarray(l["plan_x"]), color="#3F72AF", lw=1.0, label="计划购电量")
    ax.plot(t, np.asarray(l["settle_e"]), color="#B03A2E", lw=1.0, label="紧急购电量")
    ax.set_ylabel("电量（kWh/10min）"); ax.set_xlabel("时刻（小时）")
    ax.set_title("计划购电 vs 实际负荷/光伏/紧急购电", fontsize=9)
    ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25, lw=0.5)

    ax = axes[1, 0]
    c = np.asarray(l["plan_c"]); r = np.asarray(l["plan_r"])
    ax.bar(t, c, width=0.15, color="#3F72AF", label="充电")
    ax.bar(t, -r, width=0.15, color="#D05A4E", label="放电")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_ylabel("充/放电量（kWh/10min）"); ax.set_xlabel("时刻（小时）")
    ax.set_title("储能充放电（负值为放电）", fontsize=9)
    ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25, lw=0.5)

    ax = axes[1, 1]
    s = np.asarray(l["settle_s_actual"])
    ax.plot(np.arange(T + 1) / 6.0, s, color="#6C4AB6", lw=1.3)
    ax.axhline(1200, color="#B03A2E", lw=0.8, ls=":"); ax.axhline(10800, color="#B03A2E", lw=0.8, ls=":")
    ax.set_ylabel("储电量（kWh）"); ax.set_xlabel("时刻（小时）")
    ax.set_title("储能 SOC 轨迹（虚线为上下限）", fontsize=9)
    ax.grid(alpha=0.25, lw=0.5)
    fig.tight_layout(); save(fig, "fig_q4_representative_day")


def fig_monthly(res):
    logs = res["report_logs"]
    m = pd.DataFrame([{k: v for k, v in l.items() if not isinstance(v, np.ndarray)} for l in logs])
    m["month"] = pd.to_datetime(m["date"]).dt.month
    g = m.groupby("month").agg(cost_plan=("cost_plan", "sum"), cost_emg=("cost_emergency", "sum"),
                               load=("load_kwh", "sum"), emg=("emergency_kwh", "sum"))
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.4))
    ax = axes[0]
    ax.bar(g.index, g["cost_plan"] / 1e4, color="#3F72AF", label="计划购电费")
    ax.bar(g.index, g["cost_emg"] / 1e4, bottom=g["cost_plan"] / 1e4, color="#B03A2E", label="紧急购电费")
    ax.set_ylabel("费用（万元）"); ax.set_xlabel("月份（2025 年）")
    ax.set_xticks(range(2, 13)); ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25, lw=0.5, axis="y")
    ax = axes[1]
    ax.bar(g.index, g["emg"] / g["load"] * 100, color="#E8A33D")
    ax.set_ylabel("紧急购电率（占负荷 %）"); ax.set_xlabel("月份（2025 年）")
    ax.set_xticks(range(2, 13)); ax.grid(alpha=0.25, lw=0.5, axis="y")
    fig.tight_layout(); save(fig, "fig_q4_monthly_cost")


def fig_plan_vs_extract(res):
    logs = res["report_logs"]
    m = pd.DataFrame([{k: v for k, v in l.items() if not isinstance(l[k], np.ndarray)} for l in logs])
    m["month"] = pd.to_datetime(m["date"]).dt.month
    m["extract"] = m["plan_total_kwh"] - m["unextracted_kwh"]
    g = m.groupby("month").agg(plan=("plan_total_kwh", "sum"), ex=("extract", "sum"),
                               emg=("emergency_kwh", "sum"), spill=("spill_kwh", "sum"))
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    x = np.arange(len(g.index)); w = 0.27
    ax.bar(x - w, g["plan"] / 1e4, w, color="#3F72AF", label="计划购电量")
    ax.bar(x, g["ex"] / 1e4, w, color="#2F8F67", label="实际提取的计划电量")
    ax.bar(x + w, g["emg"] / 1e4, w, color="#B03A2E", label="紧急购电量")
    ax.set_xticks(x); ax.set_xticklabels([f"{i}月" for i in g.index])
    ax.set_ylabel("电量（万 kWh）"); ax.set_xlabel("月份（2025 年）")
    ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25, lw=0.5, axis="y")
    fig.tight_layout(); save(fig, "fig_q4_plan_vs_extract")


def fig_scenario_fan(ds, sc, res):
    logs = res["report_logs"]
    dates = [l["date"] for l in logs]
    mdf = pd.DataFrame([{k: v for k, v in l.items() if not isinstance(v, np.ndarray)} for l in logs])
    pick = mdf.sort_values("emergency_kwh", ascending=False).iloc[0]["date"]
    i = dates.index(pick)
    t = np.arange(1, T + 1) / 6.0
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.2))
    for ax, arr, cen, act, lab, col in (
            (axes[0], sc["P_all"][i], sc["centers"]["Phat"][:, i], ds["price"][:, i], "电价（元/kWh）", "#D05A4E"),
            (axes[1], sc["L_all"][i], sc["centers"]["Lhat"][:, i], ds["load"][:, i], "负荷（kWh/10min）", "#2F8F67"),
            (axes[2], sc["G_all"][i], sc["centers"]["Ghat"][:, i], ds["pv"][:, i], "光伏（kWh/10min）", "#E8A33D")):
        ax.fill_between(t, np.percentile(arr, 5, axis=0), np.percentile(arr, 95, axis=0),
                        color=col, alpha=0.18, label=f"{arr.shape[0]} 场景 P5–P95")
        ax.plot(t, cen, color="#3F72AF", lw=1.0, ls="--", label="场景中心（预测）")
        ax.plot(t, act, color="k", lw=0.9, label="当日实际")
        ax.set_xlabel("时刻（小时）"); ax.set_ylabel(lab)
        ax.legend(fontsize=6.5, frameon=False); ax.grid(alpha=0.25, lw=0.5)
    fig.suptitle(f"代表日 {pick} 的三维联合场景（同历史日残差块抽样）", fontsize=9)
    fig.tight_layout(); save(fig, "fig_q4_scenario_fan")


def fig_frontier_baseline(res):
    tune = res["tuning"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    ax = axes[0]
    for M, gg in tune.groupby("M"):
        sel = gg[(gg.kappa_mult == 1.0)]
        ax.plot(sel["validation_emergency_cost"] / 1e4, sel["validation_total_cost"] / 1e4,
                marker="o", ms=3.5, lw=1.0, label=f"M={int(M)}（κ×1.0）")
    ax.set_xlabel("验证期紧急购电费（万元）"); ax.set_ylabel("验证期总费用（万元）")
    ax.set_title("风险—成本前沿（2025-01-15~01-31，仅历史调参）", fontsize=9)
    ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25, lw=0.5)

    ax = axes[1]
    bp = TABLES / "q4_2_baselines.csv"
    if bp.exists():
        b = pd.read_csv(bp, encoding="utf-8-sig")
        names = b["方案"].tolist(); vals = b["报告期总费用(元)"].to_numpy(float) / 1e4
        cols = ["#3F72AF"] + ["#9AA5B1"] * (len(vals) - 1)
        order = np.argsort(vals)
        ax.barh([names[i] for i in order], vals[order], color=[cols[i] for i in order])
        for y, v in enumerate(vals[order]):
            ax.text(v, y, f"{v:,.0f}", va="center", fontsize=6.5)
        ax.set_xlabel("报告期总费用（万元）")
        ax.set_title("基线与主模型对比（334 天）", fontsize=9)
        ax.grid(alpha=0.25, lw=0.5, axis="x")
    fig.tight_layout(); save(fig, "fig_q4_frontier_baseline")


def fig_main_vs_b1():
    """专属对比图：Q4-2 主模型 vs B1（Q2 固定价策略）的费用结构与机制。

    数据全部来自已落盘结果表，不重算模型：
      Results/Tables/q4_2_experiments.csv        总费用
      Results/Tables/q4_2_timing_main_vs_b1.csv  计划购电费 / 计划购电量 / 均价 / 择时集中度
    """
    exp = pd.read_csv(TABLES / "q4_2_experiments.csv", encoding="utf-8-sig")
    tim = pd.read_csv(TABLES / "q4_2_timing_main_vs_b1.csv", encoding="utf-8-sig")

    def exp_row(prefix):
        return exp[exp["实验"].str.startswith(prefix)].iloc[0]

    m_row, b1_row = exp_row("主模型"), exp_row("B1")
    m_tim = tim[tim["方案"].str.startswith("Q4-2")].iloc[0]
    b1_tim = tim[tim["方案"].str.startswith("B1")].iloc[0]

    names = ["Q4-2 主模型\n（波动电价优化）", "B1\n（Q2 固定价策略）"]
    plan_cost = np.array([m_tim["计划购电费(实际波动价,元)"], b1_tim["计划购电费(实际波动价,元)"]], float)
    total = np.array([m_row["总费用(元)"], b1_row["总费用(元)"]], float)
    emg_cost = total - plan_cost
    plan_kwh = np.array([m_tim["计划购电量(kWh)"], b1_tim["计划购电量(kWh)"]], float)
    plan_px = np.array([m_tim["平均购电单价(元/kWh)"], b1_tim["平均购电单价(元/kWh)"]], float)
    emg_kwh = np.array([m_row["紧急购电量(kWh)"], b1_row["紧急购电量(kWh)"]], float)
    emg_px = emg_cost / emg_kwh

    fig, axes = plt.subplots(1, 3, figsize=(12.4, 3.8))

    # (a) 费用结构
    ax = axes[0]
    x = np.arange(2); w = 0.5
    ax.bar(x, plan_cost / 1e4, w, color="#3F72AF", label="计划购电费")
    ax.bar(x, emg_cost / 1e4, w, bottom=plan_cost / 1e4, color="#B03A2E", label="紧急购电费")
    for i in range(2):
        ax.text(i, (plan_cost[i] + emg_cost[i]) / 1e4 * 1.01, f"总额 {total[i]/1e4:,.1f} 万元",
                ha="center", fontsize=7.5)
        ax.text(i, plan_cost[i] / 1e4 / 2, f"{plan_cost[i]/1e4:,.1f}", ha="center", va="center",
                fontsize=7.5, color="w")
        ax.text(i, (plan_cost[i] + emg_cost[i] / 2) / 1e4, f"{emg_cost[i]/1e4:,.1f}", ha="center",
                va="center", fontsize=7.5, color="w")
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("费用（万元）"); ax.set_ylim(0, 1850)
    ax.set_title("(a) 全年费用构成（334 天）", fontsize=9)
    ax.legend(fontsize=7, frameon=False, loc="lower right")

    # (b) 单位电价（对数轴）
    ax = axes[1]
    x = np.arange(2); w = 0.34
    ax.bar(x - w / 2, plan_px, w, color="#3F72AF", label="计划购电均价")
    ax.bar(x + w / 2, emg_px, w, color="#B03A2E", label="紧急购电均价（=5×交易时刻价）")
    for i in range(2):
        ax.text(i - w / 2, plan_px[i] * 1.06, f"{plan_px[i]:.4f}", ha="center", fontsize=7.5)
        ax.text(i + w / 2, emg_px[i] * 1.06, f"{emg_px[i]:.4f}", ha="center", fontsize=7.5)
    ax.set_yscale("log"); ax.set_ylim(0.4, 14)
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("电量单价（元/kWh，对数轴）")
    ax.set_title(f"(b) 单价：B1 计划更便宜，紧急贵 {emg_px[1]/emg_px[0]:.2f} 倍", fontsize=9)
    ax.legend(fontsize=6.6, frameon=False, loc="upper left")

    # (c) 择时质量
    ax = axes[2]
    metrics = [("计划量落在当日\n最便宜 25% 时段", "最便宜25%时段占比(%)"),
               ("充电落在\n最便宜 25% 时段", "充电落在最便宜25%(%)"),
               ("放电落在\n最贵 25% 时段", "放电落在最贵25%(%)")]
    x = np.arange(len(metrics)); w = 0.34
    mv = [float(m_tim[k]) for _, k in metrics]
    bv = [float(b1_tim[k]) for _, k in metrics]
    ax.bar(x - w / 2, mv, w, color="#3F72AF", label="Q4-2 主模型")
    ax.bar(x + w / 2, bv, w, color="#9AA5B1", label="B1（Q2 固定价策略）")
    ax.axhline(25, color="#B03A2E", lw=0.9, ls=":", label="均匀投放基准 25%")
    for i in range(len(metrics)):
        ax.text(i - w / 2, mv[i] + 1.2, f"{mv[i]:.1f}", ha="center", fontsize=7)
        ax.text(i + w / 2, bv[i] + 1.2, f"{bv[i]:.1f}", ha="center", fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels([m for m, _ in metrics], fontsize=7.5)
    ax.set_ylabel("占比（%）"); ax.set_ylim(0, 88)
    ax.set_title("(c) 择时质量：两者相当，差别不在“挑便宜”", fontsize=9)
    ax.legend(fontsize=6.6, frameon=False, loc="upper left")

    fig.suptitle("图 fig_q4_main_vs_b1_cost_structure　Q4-2 主模型 与 B1（Q2 固定价策略）的费用结构对比"
                 "（2025-02-01~12-31，334 天，同场景·同结算规则，仅日前优化所用电价不同）",
                 fontsize=9.5)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "fig_q4_main_vs_b1_cost_structure")

    # 把该图的关键数字落盘，供论文与复核
    pd.DataFrame([
        {"方案": "Q4-2 主模型（波动电价优化）", "计划购电费(元)": plan_cost[0], "紧急购电费(元)": emg_cost[0],
         "总费用(元)": total[0], "计划购电量(kWh)": plan_kwh[0], "计划均价(元/kWh)": plan_px[0],
         "紧急购电量(kWh)": emg_kwh[0], "紧急均价(元/kWh)": emg_px[0]},
        {"方案": "B1（Q2 固定价策略）", "计划购电费(元)": plan_cost[1], "紧急购电费(元)": emg_cost[1],
         "总费用(元)": total[1], "计划购电量(kWh)": plan_kwh[1], "计划均价(元/kWh)": plan_px[1],
         "紧急购电量(kWh)": emg_kwh[1], "紧急均价(元/kWh)": emg_px[1]},
    ]).to_csv(TABLES / "q4_2_fig_main_vs_b1_data.csv", index=False, encoding="utf-8-sig")
    print(f"    紧急购电费倍数 = {emg_cost[1]/emg_cost[0]:.2f}×；紧急均价倍数 = {emg_px[1]/emg_px[0]:.2f}×")


CAPTIONS = [
    ("fig_q4_price_forecast", "电价与预测：左为逐日实际/预测均价与日内极差，右为日内形状的 P10–P90 与实际/预测均值曲线。单位 元/kWh，样本 365 天 × 144 时段。"),
    ("fig_q4_representative_day", "代表日（紧急购电最多日）：左上电价实际 vs 日前预测；右上计划购电量、实际负荷/光伏与紧急购电量；左下储能充放电（负值为放电）；右下 SOC 轨迹与上下限。单位 kWh/10min、kWh。"),
    ("fig_q4_monthly_cost", "逐月费用构成（计划购电费 + 紧急购电费）与逐月紧急购电率（占负荷百分比），2025 年 2–12 月。"),
    ("fig_q4_plan_vs_extract", "逐月计划购电量、实际提取的计划电量与紧急购电量的量级对比。单位 万 kWh。"),
    ("fig_q4_scenario_fan", "代表日的价格—负荷—光伏三维联合场景（同一历史日残差块抽样，P5–P95）与当日实际曲线、场景中心。"),
    ("fig_q4_frontier_baseline", "左：仅用历史期调参得到的风险—成本前沿（验证期紧急购电费 vs 总费用，M=10/20/30）；右：Q4-2 主模型与 B0/B1/B2/B3 基线的报告期总费用对比。单位 万元。"),
    ("fig_q4_main_vs_b1_cost_structure", "Q4-2 主模型 vs B1（Q2 固定价策略）的费用结构对比（334 天，同场景、同结算规则）。(a) 费用构成：B1 计划费更低但紧急费高 1.96 倍；(b) 单价（对数轴）：B1 计划均价低 5.9%，紧急均价高 96%；(c) 择时质量：两者的低价时段集中度相当，说明差异不在“挑便宜”，而在高价时段的缺口覆盖。数据见 Results/Tables/q4_2_fig_main_vs_b1_data.csv。"),
]


def write_captions():
    lines = ["# Q4-2 图目录与图注", "",
             "> 由 `Results/Pictures/make_figures_q4_2.py` 自动生成；每张图同时输出 PDF（投稿）与 PNG（预览）。",
             "> 文件名即图名，可直接用于 `\\includegraphics{figures/<name>}`。", ""]
    for name, cap in CAPTIONS:
        lines += [f"## `{name}`", "", cap, ""]
    (HERE / "figure_captions.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  figure_captions.md（{len(CAPTIONS)} 张图的名称与图注）")


if __name__ == "__main__":
    ds, res, pf, sc, M = load()
    print(f"[figures] M={M}，报告期 {len(res['report_logs'])} 天")
    fig_price(ds, pf)
    fig_representative(ds, res, sc, M)
    fig_monthly(res)
    fig_plan_vs_extract(res)
    fig_scenario_fan(ds, sc, res)
    fig_frontier_baseline(res)
    fig_main_vs_b1()
    write_captions()
    print("[figures] 完成")
