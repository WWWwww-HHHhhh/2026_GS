# -*- coding: utf-8 -*-
"""优化版 Q2 图表生成（全部来自真实运行结果）。"""
import os, pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from paths import Q2_DATA_PROCESSING, Q2_TABLES, Q2_ROOT

PICS = os.path.join(Q2_ROOT, "Results", "Pictures")
os.makedirs(PICS, exist_ok=True)
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

def load():
    with open(os.path.join(Q2_DATA_PROCESSING, "net_rolling_results.pkl"), "rb") as fh:
        res = pickle.load(fh)
    with open(os.path.join(Q2_DATA_PROCESSING, "q2_dataset.pkl"), "rb") as fh:
        ds = pickle.load(fh)
    with open(os.path.join(Q2_DATA_PROCESSING, "net_forecasts.pkl"), "rb") as fh:
        fc = pickle.load(fh)
    return res, ds, fc

def main():
    res, ds, fc = load()
    logs = res["report_logs"]
    dates = [pd.Timestamp(l["date"]) for l in logs]

    # 1 净负荷预测、实际与场景扇形
    demo_idx = list(fc["dates"]).index(pd.Timestamp("2025-07-15").date()) if pd.Timestamp("2025-07-15").date() in list(fc["dates"]) else 200
    Mfile = os.path.join(Q2_DATA_PROCESSING, f"net_scenarios_M{res['m_best']}.pkl")
    with open(Mfile, "rb") as fh:
        scen = pickle.load(fh)["N_all"][demo_idx]
    fig, ax = plt.subplots(figsize=(10, 5))
    t = np.arange(1, 145)
    lo = np.percentile(scen, 10, axis=0); hi = np.percentile(scen, 90, axis=0)
    ax.fill_between(t, lo, hi, color="skyblue", alpha=0.35, label="场景10%-90%区间")
    ax.plot(t, fc["Nhat"][:, demo_idx], color="tab:blue", label="净负荷预测")
    ax.plot(t, fc["N"][:, demo_idx], color="black", linewidth=1.2, label="真实净负荷")
    ax.set_xlabel("时段序号 t"); ax.set_ylabel("净负荷 kWh"); ax.set_title("净负荷预测、真实值与经验场景扇形")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(PICS, "fig_q2_netload_fan.png"), dpi=150); plt.close(fig)

    # 2 月度预测误差
    met = fc["monthly_metrics"]
    fig, ax1 = plt.subplots(figsize=(9, 4.5))
    ax1.bar(met["month"] - 0.2, met["MAE_kwh"], width=0.4, label="MAE(kWh)", color="tab:orange")
    ax2 = ax1.twinx(); ax2.plot(met["month"], met["WAPE"], marker="o", color="tab:red", label="WAPE")
    ax1.set_xlabel("月份"); ax1.set_ylabel("MAE kWh"); ax2.set_ylabel("WAPE"); ax1.set_title("净负荷预测月度误差")
    ax1.grid(alpha=0.3); ax2.legend(loc="upper right"); ax1.legend(loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(PICS, "fig_q2_netload_error_monthly.png"), dpi=150); plt.close(fig)

    # 3 计划购电与实际提取
    plan_daily = [np.sum(l["plan_x"]) for l in logs]
    y_daily = [np.sum(l["settle_y"]) for l in logs]
    em_daily = [np.sum(l["settle_e"]) for l in logs]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(dates, plan_daily, lw=0.7, label="计划购电量 x")
    ax.plot(dates, y_daily, lw=0.7, label="实际提取量 y")
    ax.fill_between(dates, 0, em_daily, color="red", alpha=0.25, label="紧急购电量 e")
    ax.set_xlabel("日期"); ax.set_ylabel("电量 kWh"); ax.set_title("计划购电、实际提取与紧急购电")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(PICS, "fig_q2_plan_settlement.png"), dpi=150); plt.close(fig)

    # 4 SOC 热力图
    soc = np.vstack([l["plan_s"] for l in logs])  # 334 x 145
    fig, ax = plt.subplots(figsize=(11, 5))
    im = ax.imshow(soc.T, aspect="auto", origin="lower", cmap="viridis", vmin=1200, vmax=10800)
    ax.set_xlabel("报告期日序号"); ax.set_ylabel("时段 t"); ax.set_title("储能 SOC 热力图")
    fig.colorbar(im, ax=ax, label="SOC kWh")
    fig.tight_layout(); fig.savefig(os.path.join(PICS, "fig_q2_soc_heatmap.png"), dpi=150); plt.close(fig)

    # 5 调参成本-紧急购电率权衡
    joint = res["tuning"]["joint"]
    fig, ax = plt.subplots(figsize=(8, 5))
    for beta, grp in joint.groupby("beta"):
        ax.scatter(grp["emergency_rate"], grp["total_cost"], label=f"beta={beta}", s=18)
    ax.set_xlabel("全年紧急购电率"); ax.set_ylabel("报告期总费用 元"); ax.set_title("全年候选的成本-紧急购电率权衡")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(PICS, "fig_q2_cvar_frontier.png"), dpi=150); plt.close(fig)

    # 6 月度紧急购电与弃光
    mdf = pd.read_excel(os.path.join(Q2_TABLES, "monthly_metrics.xlsx"))
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(mdf["month"] - 0.2, mdf["emergency_kwh"], width=0.4, color="red", alpha=0.6, label="紧急购电量")
    ax.bar(mdf["month"] + 0.2, mdf["curtail_kwh"], width=0.4, color="green", alpha=0.6, label="弃光量")
    ax.set_xlabel("月份"); ax.set_ylabel("电量 kWh"); ax.set_title("月度紧急购电量与弃光量")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(PICS, "fig_q2_emergency_curtailment.png"), dpi=150); plt.close(fig)
    print("[opt figures] 6 figures saved to", PICS)

if __name__ == "__main__":
    main()

