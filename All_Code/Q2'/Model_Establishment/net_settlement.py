# -*- coding: utf-8 -*-
"""优化版 Q2 结算：词典序最小紧急购电，允许放电高于计划，并保留日末 SOC 储备。"""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

T = 144
ETA_C = 0.9
ETA_R = 0.9
SOC_MIN = 1200.0
SOC_MAX = 10800.0
CAP = 833.3333333333334


def settle_day_net(price, x, c_plan, r_plan, L, G, s0, reserve_settle=0.0, kappa2_settle=0.5):
    price = np.asarray(price, float); x = np.asarray(x, float)
    c_plan = np.asarray(c_plan, float); r_plan = np.asarray(r_plan, float)
    L = np.asarray(L, float); G = np.asarray(G, float)
    s_ref = max(float(s0), SOC_MIN + float(reserve_settle))
    # 变量：y,e,g,c,r,s(0..T),xi_p,xi_m
    n = 6 * T + (T + 1) + 2
    iy = {t: t for t in range(T)}
    ie = {t: T + t for t in range(T)}
    ig = {t: 2 * T + t for t in range(T)}
    ic = {t: 3 * T + t for t in range(T)}
    ir = {t: 4 * T + t for t in range(T)}
    is_ = {t: 5 * T + t for t in range(T + 1)}
    ixi_p = 6 * T + (T + 1)
    ixi_m = ixi_p + 1

    rows, cols, vals, b = [], [], [], []
    for t in range(T):
        rows += [t] * 5
        cols += [iy[t], ie[t], ig[t], ir[t], ic[t]]
        vals += [1.0, 1.0, 1.0, 1.0, -1.0]
        b.append(L[t])
    for t in range(1, T + 1):
        row = T + t - 1
        rows += [row] * 4
        cols += [is_[t], is_[t - 1], ic[t - 1], ir[t - 1]]
        vals += [1.0, -1.0, -ETA_C, 1.0 / ETA_R]
        b.append(0.0)
    # 软终端：s_T - s_ref = xi_p - xi_m
    row = 2 * T
    rows += [row] * 3
    cols += [is_[T], ixi_p, ixi_m]
    vals += [1.0, -1.0, 1.0]
    b.append(s_ref)

    A_eq = coo_matrix((vals, (rows, cols)), shape=(2 * T + 1, n)).tocsr()

    bounds = [(0.0, None)] * n
    for t in range(T):
        bounds[iy[t]] = (0.0, x[t])
        bounds[ig[t]] = (0.0, G[t])
        bounds[ic[t]] = (0.0, c_plan[t])
        bounds[ir[t]] = (0.0, CAP)   # 放电允许高于计划
    for t in range(T + 1):
        bounds[is_[t]] = (SOC_MIN, SOC_MAX)
    bounds[is_[0]] = (s0, s0)

    # 第一阶段：只最小化真实紧急购电费
    c1 = np.zeros(n)
    for t in range(T):
        c1[ie[t]] = 5.0 * price[t]
    r1 = linprog(c=c1, A_eq=A_eq, b_eq=np.array(b), bounds=bounds, method="highs")
    if r1.status != 0:
        raise RuntimeError(f"settlement primary failed status={r1.status} msg={r1.message}")
    primary_cost = float(r1.fun)
    tol = max(1e-6, 1e-9 * max(1.0, abs(primary_cost)))

    # 第二阶段：紧急费用不增加的前提下，最大化执行量并保留日末 SOC
    c2 = np.zeros(n)
    for t in range(T):
        c2[ic[t]] = -1.0
        c2[ir[t]] = -1.0
    c2[ixi_p] = kappa2_settle
    c2[ixi_m] = kappa2_settle
    cost_cols = [ie[t] for t in range(T)]
    cost_vals = [5.0 * price[t] for t in range(T)]
    A_cost = coo_matrix((cost_vals, ([0] * T, cost_cols)), shape=(1, n)).tocsr()
    r2 = linprog(c=c2, A_ub=A_cost, b_ub=np.array([primary_cost + tol]), A_eq=A_eq, b_eq=np.array(b), bounds=bounds, method="highs")
    sol = (r2 if r2.status == 0 else r1).x

    y = sol[[iy[t] for t in range(T)]]
    e = sol[[ie[t] for t in range(T)]]
    g = sol[[ig[t] for t in range(T)]]
    c_actual = sol[[ic[t] for t in range(T)]]
    r_actual = sol[[ir[t] for t in range(T)]]
    s_actual = sol[[is_[t] for t in range(T + 1)]]
    w = G - g
    cost_plan = float(np.sum(price * x))
    cost_emergency = float(np.sum(5.0 * price * e))
    return {"y": y, "e": e, "g": g, "w": w, "c_actual": c_actual, "r_actual": r_actual,
            "s_actual": s_actual, "cost_plan": cost_plan, "cost_emergency": cost_emergency,
            "cost_total": cost_plan + cost_emergency,
            "emergency_kwh": float(np.sum(e)), "load_kwh": float(np.sum(L)),
            "curtail_kwh": float(np.sum(w)), "unextracted_kwh": float(np.sum(x - y)),
            "final_soc": float(s_actual[T]), "primary_cost": primary_cost,
            "secondary_status": int(r2.status)}
