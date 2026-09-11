# -*- coding: utf-8 -*-
"""
P5 问题二论文图（2026 数模 C 题）
==================================
依据总纲 4.7 节 6 张图。数据只来自 P0-P4 产出，禁止画未验证数值。
中文字体 SimHei/Microsoft YaHei，DPI>=300，坐标轴含单位。
"""
import os
import pickle
import sys
import traceback

GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q2CODE = os.path.join(GS, r"All_Code\Q2")
MODEL_DIR = os.path.join(Q2CODE, "Model_Establishment+Solution")
sys.path.insert(0, MODEL_DIR)

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import dates as mdates

from rolling import run_roll, load_dataset, get_scenarios

DATA_PROC = os.path.join(Q2CODE, "Data_processing")
TABLES = os.path.join(Q2CODE, "Results", "Tables")
PICS = os.path.join(Q2CODE, "Results", "Pictures")
PAPER_PICS = os.path.join(GS, r"Paper\8.Q2\Pictures")

T = 144
SEED = 20260101

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def load_all():
    with open(os.path.join(DATA_PROC, "q2_dataset.pkl"), "rb") as fh:
        ds = pickle.load(fh)
    with open(os.path.join(DATA_PROC, "forecasts.pkl"), "rb") as fh:
        fc = pickle.load(fh)
    with open(os.path.join(DATA_PROC, "q2_rolling_results.pkl"), "rb") as fh:
        res = pickle.load(fh)
    return ds, fc, res


def date_index(ds, s):
    return ds["date_str"].tolist().index(s)


def fig1_load_pv_fan(ds, fc):
    dates = ["2025-07-15", "2025-11-20"]
    with open(os.path.join(DATA_PROC, "scenarios_M20.pkl"), "rb") as fh:
        sc = pickle.load(fh)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for col, series in enumerate(["load", "pv"]):
        actual = ds[series]          # (144,365)
        pred = fc["Lhat" if series == "load" else "Ghat"]
        scen = sc["L_all" if series == "load" else "G_all"]
        for row, ds_str in enumerate(dates):
            ax = axes[row, col]
            i = date_index(ds, ds_str)
            t = np.arange(1, T + 1)
            lo, md, hi = np.percentile(scen[i], [5, 50, 95], axis=0)
            ax.fill_between(t, lo, hi, color="tab:blue", alpha=0.25, label="场景P5-P95")
            ax.plot(t, pred[:, i], color="tab:orange", lw=1.5, label="0:00预测")
            ax.plot(t, actual[:, i], color="tab:red", lw=1.2, label="当天实际")
            ax.set_title(f"{ds_str} {'负荷' if series == 'load' else '光伏'}")
            ax.set_xlabel("时段 t")
            ax.set_ylabel("电量 kWh")
            ax.legend(fontsize=7)
    fig.suptitle("负荷与光伏预测值、场景扇形带与实际值对比")
    fig.tight_layout()
    path = os.path.join(PICS, "fig_q2_load_pv_fan.png")
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print(f"    已写 {path}")


def fig2_error_monthly():
    df = pd.read_csv(os.path.join(TABLES, "forecast_monthly_metrics.csv"))
    months = sorted(df["month"].unique())
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, series in zip(axes, ["load", "pv"]):
        sub = df[df["series"] == series]
        x = sub["month"].to_numpy()
        mae = sub["MAE_kwh"].to_numpy()
        wape = sub["WAPE"].to_numpy()
        ax.bar(x, mae, color="tab:blue", alpha=0.7, label="MAE (kWh)")
        ax2 = ax.twinx()
        ax2.plot(x, wape, color="tab:red", marker="o", label="WAPE")
        ax2.set_ylim(0, max(0.1, wape.max() * 1.3))
        ax.set_xlabel("月份")
        ax.set_ylabel("MAE (kWh)")
        ax2.set_ylabel("WAPE")
        ax.set_title(f"{'负荷' if series == 'load' else '光伏'} 月度预测误差")
        ax.set_xticks(months)
        ax.set_xticklabels([f"{m}月" for m in months], rotation=45)
    fig.suptitle("滚动预测月度误差（样本量=天数×144）")
    fig.tight_layout()
    path = os.path.join(PICS, "fig_q2_error_monthly.png")
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print(f"    已写 {path}")


def fig3_plan_settlement(ds, res):
    # 选报告期内紧急购电率最高的一天作为典型日
    logs = res["report_logs"]
    i_sel = max(logs, key=lambda l: l["emergency_rate"])
    l = i_sel
    t = np.arange(1, T + 1)
    x = l["plan_x"]; y = l["settle_y"]; u = x - y; e = l["settle_e"]
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(t, x, label="计划购电 x", color="tab:blue")
    ax.plot(t, y, label="实际提取 y", color="tab:green")
    ax.plot(t, u, label="未提取 u=x-y", color="tab:orange")
    ax.plot(t, e, label="紧急购电 e", color="tab:red")
    ax.set_xlabel("时段 t")
    ax.set_ylabel("电量 kWh")
    ax.set_title(f"计划购电与实际结算时序（{l['date']}）")
    ax.legend()
    fig.tight_layout()
    path = os.path.join(PICS, "fig_q2_plan_settlement.png")
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print(f"    已写 {path}")


def fig4_soc_heatmap(res):
    logs = res["report_logs"]
    soc = np.vstack([l["settle_s_actual"] for l in logs])   # (334,145)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5), gridspec_kw={"width_ratios": [3, 1]})
    im = ax1.imshow(soc.T, aspect="auto", origin="lower", cmap="viridis", vmin=1200, vmax=10800)
    ax1.set_xlabel("日期序号（2025-02-01 起）")
    ax1.set_ylabel("时段 t")
    ax1.set_title("全年 SOC 热力图 (kWh)")
    fig.colorbar(im, ax=ax1, label="SOC kWh")
    # 典型日 SOC 曲线（第一天）
    ax2.plot(logs[0]["settle_s_actual"], np.arange(0, 145), color="tab:blue")
    ax2.axhline(0, color="k", lw=0.8)
    ax2.set_xlabel("SOC kWh")
    ax2.set_ylabel("时段 t")
    ax2.set_title(f"典型日 SOC（{logs[0]['date']}）")
    ax2.set_xlim(1200, 10800)
    fig.tight_layout()
    path = os.path.join(PICS, "fig_q2_soc_heatmap.png")
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print(f"    已写 {path}")


def fig5_cvar_frontier(ds, fc, res):
    # beta 调参前沿：复用调参窗口 s0 与 M=20 场景，独立计算 E[C] 与 CVaR
    from optimizer import solve_day2
    s0 = res["s0_0201_tuning"]
    L20, G20 = get_scenarios(20, ds, fc)
    tune_days = list(range(31, 59))
    kappa2_base = ds["kappa2_base"]
    betas = [0.0, 0.25, 0.5, 0.75, 1.0]
    ec, cvar = [], []
    for b in betas:
        params = {"beta": b, "alpha": 0.90, "kappa2": kappa2_base}
        logs, _ = run_roll(tune_days, s0, params, L20, G20, ds)
        ec.append(float(np.mean([l["E_C"] for l in logs])))
        cvar.append(float(np.mean([l["CVaR"] for l in logs])))
    beta_best = res["beta_best"]
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(ec, cvar, marker="o", color="tab:blue")
    for b, x, y in zip(betas, ec, cvar):
        ax.annotate(f"β={b:g}", (x, y), textcoords="offset points", xytext=(6, 4), fontsize=8)
    ib = betas.index(float(beta_best))
    ax.plot(ec[ib], cvar[ib], marker="*", markersize=16, color="tab:red", label=f"最优 β={beta_best:g}")
    ax.set_xlabel("期望成本 E[C] (元)")
    ax.set_ylabel("CVaR (元)")
    ax.set_title("不同 β 的期望成本—CVaR 前沿")
    ax.legend()
    fig.tight_layout()
    path = os.path.join(PICS, "fig_q2_cvar_frontier.png")
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print(f"    已写 {path}")


def fig6_emergency_curtailment(res):
    logs = res["report_logs"]
    df = pd.DataFrame([{"month": int(l["date"][5:7]), "emergency_kwh": l["emergency_kwh"], "curtail_kwh": l["curtail_kwh"]} for l in logs])
    g = df.groupby("month").sum()
    months = list(range(2, 13))
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(months))
    emg = [g.loc[m, "emergency_kwh"] if m in g.index else 0 for m in months]
    cur = [g.loc[m, "curtail_kwh"] if m in g.index else 0 for m in months]
    ax.bar(x - 0.2, emg, width=0.4, label="紧急购电量", color="tab:red")
    ax.bar(x + 0.2, cur, width=0.4, label="弃光量", color="tab:green")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{m}月" for m in months])
    ax.set_xlabel("月份")
    ax.set_ylabel("电量 kWh")
    ax.set_title("月度紧急购电量与弃光量")
    ax.legend()
    fig.tight_layout()
    path = os.path.join(PICS, "fig_q2_emergency_curtailment.png")
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print(f"    已写 {path}")


def run_figures():
    os.makedirs(PICS, exist_ok=True)
    os.makedirs(PAPER_PICS, exist_ok=True)
    ds, fc, res = load_all()
    fig1_load_pv_fan(ds, fc)
    fig2_error_monthly()
    fig3_plan_settlement(ds, res)
    fig4_soc_heatmap(res)
    fig5_cvar_frontier(ds, fc, res)
    fig6_emergency_curtailment(res)
    # 复制到论文图片目录
    for f in os.listdir(PICS):
        if f.endswith(".png"):
            src = os.path.join(PICS, f)
            dst = os.path.join(PAPER_PICS, f)
            with open(src, "rb") as fh_s, open(dst, "wb") as fh_d:
                fh_d.write(fh_s.read())
    print(f"    6 张图已复制到: {PAPER_PICS}")


def main() -> int:
    try:
        run_figures()
        return 0
    except Exception as exc:
        print("=" * 60)
        print("P5 图表执行失败：")
        traceback.print_exc()
        print(f"错误信息: {exc}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
