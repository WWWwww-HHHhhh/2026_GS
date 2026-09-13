# -*- coding: utf-8 -*-
"""只读：量化 #5 首日冷启动修复对 day0 决策与其后链路的影响。

做法：用同一组参数（预热期基准配置 M=20, β=0.25, κ×1.0）分别以
  P_old = 2025-01-01 当天实际电价（修复前口径，泄露）
  P_new = 附件1 典型日曲线（修复后口径，题目给定先验）
求解 day0，比较计划向量、执行结果与 SOC。
"""
import pickle
import sys
from pathlib import Path

import numpy as np

WYH = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q4\Q4_wyh")
sys.path.insert(0, str(WYH / "Data_processing"))
sys.path.insert(0, str(WYH / "Model_Establishment+Solution"))
from q4_common import load_dataset  # noqa: E402
from q4_core import solve_day  # noqa: E402
from q4_settlement import settle_day  # noqa: E402

ds = load_dataset()
M = 20
prior = np.asarray(ds["price_q2_fixed"], float)
actual0 = np.asarray(ds["price"], float)[:, 0]
L0 = np.asarray(ds["load"], float)[:, 0]
G0 = np.asarray(ds["pv"], float)[:, 0]
kw = {"kappa2": float(ds["kappa2_base"]) * 1.0, "beta": 0.25, "alpha": 0.90, "M": M}

for tag, center in (("修复前（当天实际价，泄露）", actual0), ("修复后（附件1 典型日先验）", prior)):
    P = np.tile(center[None, :], (M, 1))
    plan = solve_day(P, np.tile(L0, (M, 1)), np.tile(G0, (M, 1)), 6000.0, kw)
    st = settle_day(actual0, plan["x"], plan["c"], plan["r"], L0, G0, 6000.0)
    print(f"[{tag}]")
    print(f"    Σ计划购电量 = {plan['x'].sum():,.4f} kWh   计划购电费(按实际价) = {st['cost_plan']:,.4f} 元")
    print(f"    Σ充电 = {plan['c'].sum():,.4f}   Σ放电 = {plan['r'].sum():,.4f}   "
          f"紧急购电 = {st['e'].sum():,.4f} kWh")
    print(f"    day0 末 SOC = {st['s_actual'][-1]:,.6f} kWh")
    globals()[f"x_{'old' if center is actual0 else 'new'}"] = plan["x"]

d = float(np.max(np.abs(x_old - x_new)))
print(f"\n两种先验下 day0 计划向量的最大逐时段差 = {d:,.6e} kWh")

# ---- 与滚动脚本完全同源：用场景文件自带的负荷/光伏中心 + 存档结果里的 day0 标量 ----
print("\n" + "=" * 78)
print("同源对比：场景文件（修复后）vs 存档结果（修复前滚动）的 day0")
print("=" * 78)
sc = pickle.load(open(WYH / "Data_processing" / "scenarios_M20_q2.pkl", "rb"))
plan_new = solve_day(sc["P_all"][0], sc["L_all"][0], sc["G_all"][0], 6000.0, kw)
st_new = settle_day(actual0, plan_new["x"], plan_new["c"], plan_new["r"],
                    np.asarray(ds["load"], float)[:, 0], np.asarray(ds["pv"], float)[:, 0], 6000.0)
res = pickle.load(open(WYH / "Data_processing" / "q4_2_rolling_results.pkl", "rb"))
d0_old = [l for l in res["full_logs"] if l["day_index"] == 0][0]
print(f"  修复前（存档滚动）：Σ计划 = {d0_old['plan_total_kwh']:,.4f} kWh，"
      f"计划购电费 = {d0_old['cost_plan']:,.4f} 元，末 SOC = {d0_old['final_soc']:,.6f} kWh")
print(f"  修复后（重算）    ：Σ计划 = {plan_new['x'].sum():,.4f} kWh，"
      f"计划购电费 = {st_new['cost_plan']:,.4f} 元，末 SOC = {st_new['s_actual'][-1]:,.6f} kWh")
print(f"  差异              ：Σ计划 {plan_new['x'].sum() - d0_old['plan_total_kwh']:+,.4f} kWh，"
      f"费用 {st_new['cost_plan'] - d0_old['cost_plan']:+,.4f} 元，"
      f"末 SOC {st_new['s_actual'][-1] - d0_old['final_soc']:+,.6f} kWh")
print("\n结论：" + ("首日修复对 day0 决策无影响。" if abs(plan_new['x'].sum() - d0_old['plan_total_kwh']) < 1e-6
                 else "首日修复改变了 day0 决策；能否影响下游取决于 day0 末 SOC 是否相同——"
                      f"实测末 SOC 差 = {st_new['s_actual'][-1] - d0_old['final_soc']:+.6f} kWh。"))
