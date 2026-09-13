# -*- coding: utf-8 -*-
"""q4_settlement.py —— 问题 4-2 的因果结算（与 Q2 的 `settlement.py` 逐行同构）。

【口径】逐时段原样执行 0:00 制定的 x/c/r，不读取当天任何未来真实值：
  1. demand = L_actual[t] + c[t] − r[t]；
  2. 若日前固定放电造成供给过剩，记为弃电 spill（题目只要求"不低于负荷"，不允许事后缩减放电来美化 SOC 与费用）；
  3. 先用光伏、再用计划量提取、最后紧急购电：g = min(G, demand)，y = min(x, 剩余)，e = 剩余 − y；
  4. 计划购电费 = Σ λ_t·x_t（λ 为该日**实际**波动电价，即"按计划购电量计价"）；
  5. 紧急购电费 = Σ 5·λ_t·e_t（交易时刻电价的 5 倍）。
"""
from __future__ import annotations

import numpy as np

T = 144
ETA_C = 0.9
ETA_R = 0.9
SOC_MIN = 1200.0
SOC_MAX = 10800.0


def settle_day(price, x, c, r, L_actual, G_actual, s0, full_extraction=False):
    price = np.asarray(price, dtype=float)
    x = np.asarray(x, dtype=float); c = np.asarray(c, dtype=float); r = np.asarray(r, dtype=float)
    L = np.asarray(L_actual, dtype=float); G = np.asarray(G_actual, dtype=float)
    for name, arr in (("price", price), ("x", x), ("c", c), ("r", r), ("L", L), ("G", G)):
        if arr.shape != (T,) or not np.all(np.isfinite(arr)):
            raise ValueError(f"invalid {name}: shape={arr.shape}")
    if np.any(price <= 0) or any(np.any(a < -1e-9) for a in (x, c, r, L, G)):
        raise ValueError("电价必须为正，电量不得为负")

    y = np.zeros(T); e = np.zeros(T); g = np.zeros(T)
    c_actual = c.copy(); r_actual = r.copy()
    s_actual = np.zeros(T + 1); spill = np.zeros(T)
    s_actual[0] = float(s0)

    for t in range(T):
        demand = L[t] + c_actual[t] - r_actual[t]
        spill[t] = max(0.0, -demand)
        served = max(0.0, demand)
        g[t] = min(G[t], served)
        remaining = max(0.0, served - g[t])
        if full_extraction:
            if x[t] > remaining + 1e-7:
                raise RuntimeError("全量提取口径下因果执行不可行")
            y[t] = x[t]
        else:
            y[t] = min(x[t], remaining)
        e[t] = max(0.0, remaining - y[t])
        s_actual[t + 1] = s_actual[t] + ETA_C * c_actual[t] - r_actual[t] / ETA_R

    w = G - g
    balance = y + e + g + r_actual - L - c_actual - spill
    if np.max(np.abs(balance)) > 1e-6:
        raise RuntimeError(f"结算平衡残差过大 {np.max(np.abs(balance)):.3e}")
    if np.any(s_actual < SOC_MIN - 1e-6) or np.any(s_actual > SOC_MAX + 1e-6):
        raise RuntimeError("结算后 SOC 越界")

    cost_plan = float(np.sum(price * x))
    cost_emergency = float(np.sum(5.0 * price * e))
    load_total = float(np.sum(L)); x_total = float(np.sum(x)); pv_total = float(np.sum(G))
    return {
        "y": y, "e": e, "g": g, "w": w, "spill": spill,
        "c_actual": c_actual, "r_actual": r_actual, "s_actual": s_actual,
        "cost_plan": cost_plan, "cost_emergency": cost_emergency,
        "cost_total": cost_plan + cost_emergency,
        "emergency_rate": float(np.sum(e) / load_total) if load_total else 0.0,
        "unextracted_ratio": float(np.sum(x - y) / x_total) if x_total else 0.0,
        "curtailment_rate": float(np.sum(w) / pv_total) if pv_total else 0.0,
        "soc_violate_count": 0,
        "settlement_method": "causal_sequential_exact_plan",
    }
