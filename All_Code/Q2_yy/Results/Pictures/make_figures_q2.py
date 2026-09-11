# -*- coding: utf-8 -*-
"""由Q2_yy已校验缓存生成论文图，不再次调参或求解。"""
from pathlib import Path
import pickle
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PICS = Path(__file__).resolve().parent
Q2_ROOT = PICS.parents[1]
DATA = Q2_ROOT / "Data_processing"
TABLES = Q2_ROOT / "Results" / "Tables"
T = 144
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def load(name):
    with open(DATA / name, "rb") as fh:
        return pickle.load(fh)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(PICS / name, dpi=300, bbox_inches="tight")
    plt.close(fig)


def run():
    ds, fc, res = load("q2_dataset.pkl"), load("forecasts.pkl"), load("q2_rolling_results.pkl")
    sc = load(f"scenarios_M{res['m_best']}.pkl")
    logs = res["report_logs"]

    # 预测场景扇形图：固定日期，不挑最好看的日期。
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for row, date in enumerate(("2025-07-15", "2025-11-20")):
        i = ds["date_str"].tolist().index(date)
        for col, (key, pred_key, scen_key, title) in enumerate((
                ("load", "Lhat", "L_all", "负荷"), ("pv", "Ghat", "G_all", "光伏"))):
            ax = axes[row, col]; q = np.percentile(sc[scen_key][i], [5, 95], axis=0)
            ax.fill_between(np.arange(T), q[0], q[1], alpha=.25, label="场景P5–P95")
            ax.plot(fc[pred_key][:, i], label="日前预测", lw=1.2)
            ax.plot(ds[key][:, i], label="实际", lw=1.1)
            ax.set(title=f"{date} {title}", xlabel="10分钟时段", ylabel="电量/kWh")
            ax.legend(fontsize=8)
    save(fig, "fig_q2_load_pv_fan.png")

    fm = pd.read_csv(TABLES / "forecast_monthly_metrics.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, series, title in zip(axes, ("load", "pv"), ("负荷", "光伏")):
        z = fm[fm.series == series]
        ax.plot(z.month, 100*z.WAPE, marker="o")
        ax.set(title=f"{title}月度预测WAPE", xlabel="月份", ylabel="WAPE/%", xticks=range(2, 13))
    save(fig, "fig_q2_error_monthly.png")

    worst = max(logs, key=lambda x: x["cost_emergency"])
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(worst["plan_x"], label="计划购电")
    ax.plot(worst["settle_y"], label="实际提取")
    ax.plot(worst["settle_e"], label="紧急购电")
    ax.set(title=f"最高紧急购电费日：{worst['date']}", xlabel="10分钟时段", ylabel="电量/kWh")
    ax.legend()
    save(fig, "fig_q2_plan_settlement.png")

    soc = np.vstack([x["settle_s_actual"] for x in logs])
    fig, ax = plt.subplots(figsize=(11, 4))
    im = ax.imshow(soc.T, origin="lower", aspect="auto", vmin=1200, vmax=10800)
    fig.colorbar(im, ax=ax, label="SOC/kWh")
    ax.set(title="报告期储能SOC热力图", xlabel="日期序号（2月1日起）", ylabel="10分钟时段")
    save(fig, "fig_q2_soc_heatmap.png")

    monthly = pd.DataFrame({"month": [int(x["date"][5:7]) for x in logs],
                            "emergency": [x["emergency_kwh"] for x in logs],
                            "curtail": [x["curtail_kwh"] for x in logs]}).groupby("month").sum()
    fig, ax = plt.subplots(figsize=(9, 4)); xx = np.arange(len(monthly))
    ax.bar(xx-.2, monthly.emergency, .4, label="紧急购电")
    ax.bar(xx+.2, monthly.curtail, .4, label="弃光")
    ax.set(title="月度紧急购电量与弃光量", xlabel="月份", ylabel="电量/kWh",
           xticks=xx, xticklabels=monthly.index)
    ax.legend(); save(fig, "fig_q2_emergency_curtailment.png")

    tune = res["tuning"]["joint"]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(tune.validation_total_cost, tune.validation_emergency_cost,
               c=tune.beta, s=25, alpha=.65, cmap="viridis")
    chosen = tune[tune.is_selected]
    ax.scatter(chosen.validation_total_cost, chosen.validation_emergency_cost,
               marker="*", s=220, c="red", label="仅历史期选中参数")
    ax.set(title="1月验证期参数候选", xlabel="验证期总费用/元", ylabel="验证期紧急购电费/元")
    ax.legend(); save(fig, "fig_q2_cvar_frontier.png")
    print("six verified figures written")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"figure generation failed: {exc}")
        sys.exit(1)
