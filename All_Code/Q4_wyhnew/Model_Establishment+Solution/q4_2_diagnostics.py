# -*- coding: utf-8 -*-
"""q4_2_diagnostics.py —— 计划购电的"择时质量"诊断（只读滚动日志，不重算 LP）。

回答一个问题：Q4-2 的日前计划到底有没有把钱花在便宜的时候？
  D1 平均购电单价 = Σλ_t x_t / Σx_t，与全年均价、当日均价对比；
  D2 低价时段集中度：把当日 144 个时段按价格分成 4 档，统计计划量落在最便宜一档的占比
     （均匀投放应为 25%；>25% 说明有择时能力）；
  D3 反事实：把同一计划按附件1 的固定电价计价，看费用变化（分离"时间对齐"与"价格水平"的贡献）；
  D4 未提取、弃光、紧急购电的时段分布；
  D5 储能充放电的价位分布（充电落在低价档的比例 / 放电落在高价档的比例）。

运行：python q4_2_diagnostics.py
"""
from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

WYH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WYH / "Data_processing"))
sys.path.insert(0, str(WYH / "Model_Establishment+Solution"))
from q4_common import D, OUT_DATA, TABLES, T, load_dataset  # noqa: E402

SOC0 = 6000.0


def timing_metrics(plans: list, price: np.ndarray, charges: list | None = None,
                   discharges: list | None = None) -> dict:
    """给出一组逐日计划向量的择时指标。plans[i] / charges[i] / discharges[i] 为 (144,) 或 None。"""
    tot_x = tot_cost = 0.0
    cheap_share, chg_cheap, dis_exp = [], [], []
    for i, x in enumerate(plans):
        lam = price[:, i]
        order = np.argsort(lam)
        q = np.empty(T, dtype=int)
        q[order] = np.minimum(3, (np.arange(T) * 4) // T)
        tot_x += float(x.sum()); tot_cost += float(np.sum(lam * x))
        cheap_share.append(float(x[q == 0].sum() / max(x.sum(), 1e-9)))
        if charges is not None and charges[i] is not None and charges[i].sum() > 0:
            chg_cheap.append(float(charges[i][q == 0].sum() / charges[i].sum()))
        if discharges is not None and discharges[i] is not None and discharges[i].sum() > 0:
            dis_exp.append(float(discharges[i][q == 3].sum() / discharges[i].sum()))
    return {
        "plan_kwh": tot_x, "plan_cost": tot_cost, "avg_price": tot_cost / max(tot_x, 1e-9),
        "cheap_share": float(np.mean(cheap_share)),
        "charge_cheap": float(np.nanmean(chg_cheap)) if chg_cheap else float("nan"),
        "discharge_expensive": float(np.nanmean(dis_exp)) if dis_exp else float("nan"),
    }


def run_b1_plans(ds, res, scen) -> tuple[list, list, list]:
    """用 Q2 固定电价做日前优化，返回逐日 (x, c, r)（结算口径不变，仅用于择时对比）。"""
    from q4_core import solve_day
    logs = res["report_logs"]
    s0 = float(logs[0]["s0"])
    M = int(scen["M"])
    P = np.tile(ds["price_q2_fixed"][None, :], (M, 1))
    xs, cs, rs = [], [], []
    t0 = time.time()
    for n, l in enumerate(logs):
        i = l["day_index"]
        kw = {"kappa2": float(res["params"]["kappa2"]), "beta": float(res["params"]["beta"]),
              "alpha": float(res["params"]["alpha"])}
        if i == D - 1:
            kw.update({"hard_terminal": True, "s_ref": SOC0})
        plan = solve_day(P, scen["L_all"][i], scen["G_all"][i], s0, kw)
        xs.append(plan["x"]); cs.append(plan["c"]); rs.append(plan["r"])
        s0 = float(plan["s"][-1])
        if n and n % 80 == 0:
            print(f"    B1 计划重算 {l['date']} ({n}/334, {time.time()-t0:.0f}s)", flush=True)
    return xs, cs, rs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--b1", action="store_true", help="额外重算 B1（固定价优化）的择时指标作对比")
    args = ap.parse_args()
    ds = load_dataset()
    res = pickle.load(open(OUT_DATA / "q4_2_rolling_results.pkl", "rb"))
    logs = res["report_logs"]
    price = ds["price"]
    fixed = ds["price_q2_fixed"]

    plot_rows, rows = [], []
    tot_x = tot_plan_cost = tot_fixed_cost = 0.0
    cheap_share_all, cheap_charge, expensive_discharge = [], [], []
    unext_band = np.zeros(4)   # 未提取量按当日价格档
    emg_band = np.zeros(4)
    curt_band = np.zeros(4)

    for l in logs:
        i = l["day_index"]
        lam = price[:, i]; x = np.asarray(l["plan_x"]); c = np.asarray(l["plan_c"])
        r = np.asarray(l["plan_r"]); un = x - np.asarray(l["settle_y"])
        e = np.asarray(l["settle_e"]); w = np.asarray(l["settle_w"])
        order = np.argsort(lam)                       # 价格升序
        q = np.empty(T, dtype=int)
        q[order] = np.minimum(3, (np.arange(T) * 4) // T)   # 0=最便宜 25%，3=最贵 25%
        tot_x += float(x.sum())
        tot_plan_cost += float(np.sum(lam * x))
        tot_fixed_cost += float(np.sum(fixed * x))
        cheap_share_all.append(float(x[q == 0].sum() / max(x.sum(), 1e-9)))
        cheap_charge.append(float(c[q == 0].sum() / max(c.sum(), 1e-9)) if c.sum() > 0 else np.nan)
        expensive_discharge.append(float(r[q == 3].sum() / max(r.sum(), 1e-9)) if r.sum() > 0 else np.nan)
        for k in range(4):
            unext_band[k] += float(un[q == k].sum())
            emg_band[k] += float(e[q == k].sum())
            curt_band[k] += float(w[q == k].sum())

    mean_price = float(price[:, [l["day_index"] for l in logs]].mean())
    rows = [
        ["计划购电量合计（kWh）", f"{tot_x:,.2f}"],
        ["计划购电费合计（实际波动价，元）", f"{tot_plan_cost:,.2f}"],
        ["平均购电单价（元/kWh）", f"{tot_plan_cost / tot_x:.4f}"],
        ["报告期全年均价（元/kWh）", f"{mean_price:.4f}"],
        ["相对均价节省", f"{(1 - (tot_plan_cost / tot_x) / mean_price) * 100:.2f}%"],
        ["同一计划按附件1固定价计价（元）", f"{tot_fixed_cost:,.2f}"],
        ["固定价与波动价之差（元）", f"{tot_fixed_cost - tot_plan_cost:+,.2f}"],
        ["计划量落在当日最便宜 25% 时段的占比（均匀=25%）",
         f"{np.mean(cheap_share_all) * 100:.2f}%"],
        ["充电量落在最便宜 25% 时段的占比", f"{np.nanmean(cheap_charge) * 100:.2f}%"],
        ["放电量落在最贵 25% 时段的占比", f"{np.nanmean(expensive_discharge) * 100:.2f}%"],
    ]
    band_df = pd.DataFrame({
        "价格档（当日）": ["最便宜25%", "次便宜25%", "次贵25%", "最贵25%"],
        "未提取计划量(kWh)": unext_band,
        "紧急购电量(kWh)": emg_band,
        "弃光量(kWh)": curt_band,
    })
    band_df["未提取占比(%)"] = band_df["未提取计划量(kWh)"] / band_df["未提取计划量(kWh)"].sum() * 100
    band_df["紧急购电占比(%)"] = band_df["紧急购电量(kWh)"] / band_df["紧急购电量(kWh)"].sum() * 100

    cmp_df = None
    if args.b1:
        scen = pickle.load(open(OUT_DATA / f"scenarios_M{int(res['params']['M'])}.pkl", "rb"))
        print("  重算 B1（固定价优化）的逐日计划，用于择时对比…")
        bx, bc, br = run_b1_plans(ds, res, scen)
        m1 = timing_metrics(bx, price, bc, br)
        cmp_df = pd.DataFrame([
            {"方案": "Q4-2 主模型（波动价优化）", "计划购电量(kWh)": tot_x,
             "计划购电费(实际波动价,元)": tot_plan_cost, "平均购电单价(元/kWh)": tot_plan_cost / tot_x,
             "最便宜25%时段占比(%)": float(np.mean(cheap_share_all)) * 100,
             "充电落在最便宜25%(%)": float(np.nanmean(cheap_charge)) * 100,
             "放电落在最贵25%(%)": float(np.nanmean(expensive_discharge)) * 100},
            {"方案": "B1 Q2固定价优化（同一结算口径）", "计划购电量(kWh)": m1["plan_kwh"],
             "计划购电费(实际波动价,元)": m1["plan_cost"], "平均购电单价(元/kWh)": m1["avg_price"],
             "最便宜25%时段占比(%)": m1["cheap_share"] * 100,
             "充电落在最便宜25%(%)": m1["charge_cheap"] * 100,
             "放电落在最贵25%(%)": m1["discharge_expensive"] * 100},
        ])
        cmp_df.to_csv(TABLES / "q4_2_timing_main_vs_b1.csv", index=False, encoding="utf-8-sig")
        print(cmp_df.to_string(index=False))

    TABLES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["指标", "数值"]).to_csv(
        TABLES / "q4_2_plan_timing.csv", index=False, encoding="utf-8-sig")
    band_df.to_csv(TABLES / "q4_2_band_allocation.csv", index=False, encoding="utf-8-sig")

    lines = ["# 问题 4-2 计划购电的择时质量诊断", "",
             "- 数据来源：`Data_processing/q4_2_rolling_results.pkl` 的 report_logs 与附件4 实际电价",
             "- 脚本：`Model_Establishment+Solution/q4_2_diagnostics.py`（只读，不重算 LP）", "",
             "## 汇总", "", "| 指标 | 数值 |", "| --- | --- |"]
    for k, v in rows:
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 分档分布（按当日价格四分位）", "",
              "| 价格档 | 未提取计划量(kWh) | 紧急购电量(kWh) | 弃光量(kWh) | 未提取占比(%) | 紧急购电占比(%) |",
              "| --- | --- | --- | --- | --- | --- |"]
    for _, r in band_df.iterrows():
        lines.append(f"| {r['价格档（当日）']} | {r['未提取计划量(kWh)']:,.1f} | {r['紧急购电量(kWh)']:,.1f} | "
                     f"{r['弃光量(kWh)']:,.1f} | {r['未提取占比(%)']:.2f} | {r['紧急购电占比(%)']:.2f} |")
    lines += ["", "## 读法", "",
              "1. 「平均购电单价 < 全年均价」的差额，就是日前计划**择时能力**的直接证据：",
              "   计划把电量集中投放到当日价格较低的时段。",
              "2. 「计划量落在最便宜 25% 时段的占比」与均匀投放的 25% 比较，量化集中度。",
              "3. 「同一计划按附件1固定价计价」与按波动价计价之差，分离出两件事：",
              "   时间对齐（在哪里买）与价格水平（单价高低）。前者由波动电价优化贡献，后者是市场给定的。",
              "4. 紧急购电若集中在最贵档，说明价格高企时预测误差的代价被 5 倍罚价放大，"
              "这正是风险厌恶系数 β 起作用的场景。", ""]
    if cmp_df is not None:
        lines += ["", "## 主模型 vs B1（固定价优化）的择时对比", "",
                  "| 方案 | 计划购电量(kWh) | 计划购电费(元) | 平均购电单价(元/kWh) | 最便宜25%时段占比(%) | 充电落在最便宜25%(%) | 放电落在最贵25%(%) |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for _, r in cmp_df.iterrows():
            lines.append(f"| {r['方案']} | {r['计划购电量(kWh)']:,.1f} | {r['计划购电费(实际波动价,元)']:,.1f} | "
                         f"{r['平均购电单价(元/kWh)']:.4f} | {r['最便宜25%时段占比(%)']:.2f} | "
                         f"{r['充电落在最便宜25%(%)']:.2f} | {r['放电落在最贵25%(%)']:.2f} |")
        lines += ["",
                  "说明：两者使用同一组负荷/光伏场景、同一结算规则，差别**只在日前优化时用哪套电价**。",
                  "若平均购电单价接近，说明该题结构下日内价格形状的可预测性很高，"
                  "真正无法通过对冲消除的是日级价格水平（R1 口径下按计划量成比例计费）。"]
    (TABLES / "q4_2_plan_timing_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for k, v in rows:
        print(f"  {k}: {v}")
    print()
    print(band_df.to_string(index=False))
    print(f"\n  报告: {TABLES / 'q4_2_plan_timing_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
