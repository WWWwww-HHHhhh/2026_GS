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
