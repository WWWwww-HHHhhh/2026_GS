# -*- coding: utf-8 -*-
"""q4_core 单日 LP 性能与正确性基准（只读，不写结果）。"""
import pickle
import sys
import time
from pathlib import Path

import numpy as np

WYH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WYH / "Data_processing"))
sys.path.insert(0, str(WYH / "Model_Establishment+Solution"))
from q4_common import load_dataset  # noqa: E402
from q4_core import check_day, solve_day  # noqa: E402

ds = load_dataset()
i = 31  # 2025-02-01
s0 = 6000.0
kappa2 = float(ds["kappa2_base"])
print("kappa2_base =", kappa2)

for M in (10, 20, 30):
    sp = WYH / "Data_processing" / f"scenarios_M{M}.pkl"
    if not sp.exists():
        print(f"M={M}: 缺少 {sp.name}，跳过")
        continue
    with open(sp, "rb") as fh:
        sc = pickle.load(fh)
    L = sc["L_all"][i]; G = sc["G_all"][i]; P = sc["P_all"][i]
    t0 = time.time()
    plan = check_day(P, L, G, s0, {"kappa2": kappa2, "beta": 0.25, "alpha": 0.90}, verbose=False)
    dt = time.time() - t0
    x = plan["x"]
    print(f"M={M:2d}  求解 {dt:6.2f}s  E[C]={plan['E_C']:12.2f}  CVaR={plan['CVaR']:12.2f}  "
          f"Σx={x.sum():10.2f} kWh  Σc={plan['c'].sum():9.2f}  Σr={plan['r'].sum():9.2f}  "
          f"终端SOC={plan['s'][-1]:9.2f}  eq={plan['eq_residual']:.1e} ub={plan['ub_violation']:.1e}")

# 确定性完美预见（M=1，用当天实际值）作为 B0 下界的一次抽样
L1 = ds["load"][:, i][None, :]; G1 = ds["pv"][:, i][None, :]; P1 = ds["price"][:, i][None, :]
t0 = time.time()
plan0 = solve_day(P1, L1, G1, s0, {"kappa2": kappa2, "beta": 0.0, "alpha": 0.90})
print(f"B0 完美预见(M=1) {time.time()-t0:.2f}s  C={plan0['E_C']:12.2f}  Σx={plan0['x'].sum():10.2f}")

# Q2 口径（固定电价=附件1）在同一组负荷/光伏场景下的解（B1 的策略）
with open(WYH / "Data_processing" / "scenarios_M20.pkl", "rb") as fh:
    sc20 = pickle.load(fh)
Pf = np.tile(ds["price_q2_fixed"][None, :], (20, 1))
t0 = time.time()
plan_f = solve_day(Pf, sc20["L_all"][i], sc20["G_all"][i], s0, {"kappa2": kappa2, "beta": 0.25})
print(f"B1 固定价策略(M=20) {time.time()-t0:.2f}s  E[C|固定价]={plan_f['E_C']:12.2f}  Σx={plan_f['x'].sum():10.2f}")
