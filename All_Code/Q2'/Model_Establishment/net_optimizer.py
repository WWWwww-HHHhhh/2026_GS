# -*- coding: utf-8 -*-
"""优化版 Q2 两阶段随机 LP：净负荷场景 + CVaR + 弃光变量 + 未提取惩罚 + 日末 SOC 储备。"""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

T = 144
DEFAULT_PARAMS = {
    "alpha": 0.90, "beta": 0.25, "eps": 1e-4, "eps_u": 0.02, "eps_w": 0.001, "em_pen": 0.0,
    "kappa2": 0.531667, "eta_c": 0.9, "eta_r": 0.9,
    "s_min": 1200.0, "s_max": 10800.0, "cap": 833.3333333333334,
    "reserve_kwh": 0.0,
}


def solve_day2_net(price, N_scen, s0, params=None):
    p = dict(DEFAULT_PARAMS)
    if params:
        p.update({k: v for k, v in params.items() if v is not None})
    alpha = float(p["alpha"]); beta = float(p["beta"])
    eps = float(p["eps"]); eps_u = float(p["eps_u"]); eps_w = float(p["eps_w"]); em_pen = float(p["em_pen"])
    kappa2 = float(p["kappa2"]); eta_c = float(p["eta_c"]); eta_r = float(p["eta_r"])
    s_min = float(p["s_min"]); s_max = float(p["s_max"]); cap = float(p["cap"])
    reserve = float(p["reserve_kwh"])
    price = np.asarray(price, dtype=float)
    N_scen = np.asarray(N_scen, dtype=float)
    M = int(N_scen.shape[0])
    prob = 1.0 / M
    s_ref = max(float(s0), s_min + reserve)

    ix = {t: t for t in range(T)}
    ic = {t: T + t for t in range(T)}
    ir = {t: 2 * T + t for t in range(T)}
    is_ = {t: 3 * T + t for t in range(T + 1)}
    NF = 3 * T + (T + 1) + 2
    ixi_p = NF - 2
    ixi_m = NF - 1
    NS = 4 * T + 1
    BASE2 = NF
    NZETA = NF + M * NS
    NV = NZETA + 1

    def sv(m, kind, t=None):
        base = BASE2 + m * NS
        off = {"y": 0, "e": T, "u": 2 * T, "w": 3 * T, "q": 4 * T}[kind]
        if kind == "q":
            return base + off
        return base + off + t

    c_obj = np.zeros(NV)
    for t in range(T):
        c_obj[ix[t]] += (1.0 - beta) * price[t]
        c_obj[ic[t]] += eps
        c_obj[ir[t]] += eps
    c_obj[ixi_p] = kappa2
    c_obj[ixi_m] = kappa2
    for m in range(M):
        for t in range(T):
            c_obj[sv(m, "e", t)] += (1.0 - beta + em_pen) * 5.0 * prob * price[t]
            c_obj[sv(m, "u", t)] += eps_u * prob
            c_obj[sv(m, "w", t)] += eps_w * prob
        c_obj[sv(m, "q")] += beta * (1.0 / (1.0 - alpha)) * prob
    c_obj[NZETA] = beta

    rows_eq, cols_eq, vals_eq, b_eq = [], [], [], []
    # 平衡：y + e + r - c - w = N  (w 为净负荷意义下的弃光量)
    for m in range(M):
        for t in range(T):
            rrow = m * T + t
            rows_eq += [rrow] * 5
            cols_eq += [sv(m, "y", t), sv(m, "e", t), ir[t], ic[t], sv(m, "w", t)]
            vals_eq += [1.0, 1.0, 1.0, -1.0, -1.0]
            b_eq.append(float(N_scen[m, t]))
    # 未提取：x - y - u = 0
    for m in range(M):
        for t in range(T):
            rrow = M * T + m * T + t
            rows_eq += [rrow] * 3
            cols_eq += [ix[t], sv(m, "y", t), sv(m, "u", t)]
            vals_eq += [1.0, -1.0, -1.0]
            b_eq.append(0.0)
    # SOC
    for t in range(1, T + 1):
        rrow = 2 * M * T + (t - 1)
        rows_eq += [rrow] * 4
        cols_eq += [is_[t], is_[t - 1], ic[t - 1], ir[t - 1]]
        vals_eq += [1.0, -1.0, -eta_c, 1.0 / eta_r]
        b_eq.append(0.0)
    # 软终端：s_T - s_ref = xi_p - xi_m
    rrow = 2 * M * T + T
    rows_eq += [rrow] * 3
    cols_eq += [is_[T], ixi_p, ixi_m]
    vals_eq += [1.0, -1.0, 1.0]
    b_eq.append(s_ref)

    rows_ub, cols_ub, vals_ub, b_ub = [], [], [], []
    for m in range(M):
        row = m
        rows_ub.append(row); cols_ub.append(sv(m, "q")); vals_ub.append(-1.0)
        rows_ub.append(row); cols_ub.append(NZETA); vals_ub.append(-1.0)
        for t in range(T):
            rows_ub.append(row); cols_ub.append(ix[t]); vals_ub.append(price[t])
            rows_ub.append(row); cols_ub.append(sv(m, "e", t)); vals_ub.append(5.0 * price[t])
        b_ub.append(0.0)

    A_eq = coo_matrix((vals_eq, (rows_eq, cols_eq)), shape=(2 * M * T + T + 1, NV)).tocsr()
    A_ub = coo_matrix((vals_ub, (rows_ub, cols_ub)), shape=(M, NV)).tocsr()

    bounds = [(0.0, None)] * NV
    for t in range(T):
        bounds[ic[t]] = (0.0, cap)
        bounds[ir[t]] = (0.0, cap)
    for t in range(T + 1):
        bounds[is_[t]] = (s_min, s_max)
    bounds[is_[0]] = (s0, s0)
    bounds[NZETA] = (None, None)

    res = linprog(c=c_obj, A_ub=A_ub, b_ub=np.array(b_ub), A_eq=A_eq, b_eq=np.array(b_eq),
                  bounds=bounds, method="highs")
    if res.status != 0:
        raise RuntimeError(f"net LP failed status={res.status} msg={res.message}")

    sol = res.x
    x = sol[[ix[t] for t in range(T)]]
    c = sol[[ic[t] for t in range(T)]]
    r = sol[[ir[t] for t in range(T)]]
    s = sol[[is_[t] for t in range(T + 1)]]
    e_all = np.array([[sol[sv(m, "e", t)] for t in range(T)] for m in range(M)])
    C = np.array([float(np.sum(price * x) + 5.0 * np.sum(price * e_all[m])) for m in range(M)])
    E_C = float(np.mean(C))
    q_all = np.array([sol[sv(m, "q")] for m in range(M)])
    cvar = float(sol[NZETA] + (1.0 / (1.0 - alpha)) * np.mean(q_all))
    u_all = np.array([[sol[sv(m, "u", t)] for t in range(T)] for m in range(M)])
    w_all = np.array([[sol[sv(m, "w", t)] for t in range(T)] for m in range(M)])
    return {"x": x, "c": c, "r": r, "s": s,
            "xi_p": float(sol[ixi_p]), "xi_m": float(sol[ixi_m]),
            "E_C": E_C, "CVaR": cvar, "objective": float(res.fun),
            "u_mean": float(np.mean(u_all)), "w_mean": float(np.mean(w_all)), "status": int(res.status)}

