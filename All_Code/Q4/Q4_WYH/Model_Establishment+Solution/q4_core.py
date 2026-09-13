# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

T = 144

DEFAULT_PARAMS = {
    "alpha": 0.90,
    "beta": 0.5,
    "eps": 1e-4,
    "kappa2": None,            # 必须由调用方传入（数据集里的 kappa2_base 或其倍数）
    "eta_c": 0.9,
    "eta_r": 0.9,
    "s_min": 1200.0,
    "s_max": 10800.0,
    "cap": 5000.0 / 6.0,       # 833.3333... kWh/时段
    "s_ref": None,             # 默认取 s0
    "hard_terminal": False,
    "full_extraction": False,  # True 时强制 y == x（敏感性口径）
    "x_cap": None,             # 计划购电量上限（kWh/时段）。None = 不设限（题目未给联络线容量约束）；
                               # 用于 R-1「联络线容量敏感性」：x_cap = 容量kW × (1/6)
}


def solve_day(P, L, G, s0, params=None):
    """求解一个自然日的两阶段随机 LP + CVaR。

    参数
    ----
    P : (M, T) 元/kWh —— **逐场景**电价（Q4-2 的核心输入）
    L : (M, T) kWh    —— 逐场景负荷
    G : (M, T) kWh    —— 逐场景光伏
    s0: float         —— 当日 0:00 期初储电量
    params : dict     —— 覆盖 DEFAULT_PARAMS

    返回 plan 字典（含第一阶段 x/c/r/s、逐场景 y/e/g/w、成本 E[C]/CVaR 与残差验算值）。
    """
    if params is None:
        params = {}
    p = dict(DEFAULT_PARAMS)
    p.update({k: v for k, v in params.items() if v is not None})
    alpha = float(p["alpha"]); beta = float(p["beta"]); eps = float(p["eps"])
    kappa2 = float(p["kappa2"])
    eta_c = float(p["eta_c"]); eta_r = float(p["eta_r"])
    s_min = float(p["s_min"]); s_max = float(p["s_max"]); cap = float(p["cap"])
    s_ref = float(s0) if p["s_ref"] is None else float(p["s_ref"])
    full_extraction = bool(p.get("full_extraction", False))
    hard_terminal = bool(p.get("hard_terminal", False))

    P = np.asarray(P, dtype=float)
    if P.ndim == 1:
        P = P[None, :]
    if P.shape[1] != T:
        raise ValueError(f"电价矩阵应为 (M,{T})，实际 {P.shape}")
    if (P <= 0).any():
        raise ValueError("电价必须严格为正")
    L = np.asarray(L, dtype=float); G = np.asarray(G, dtype=float)
    if L.ndim != 2 or G.ndim != 2 or L.shape != G.shape or L.shape != P.shape:
        raise ValueError(f"场景形状不一致: P={P.shape}, L={L.shape}, G={G.shape}")
    M = int(L.shape[0])
    prob = 1.0 / M

    # ---------------- 变量布局（与 Q2 完全一致）----------------
    N_FIRST = 3 * T + (T + 1) + 2      # x,c,r,s,xi_p,xi_m
    N_SCEN = 6 * T + 1                 # y,e,g,w,u,v,q
    BASE2 = N_FIRST
    NZETA = N_FIRST + M * N_SCEN
    N_VARS = NZETA + 1

    ix = {t: t for t in range(T)}
    ic = {t: T + t for t in range(T)}
    ir = {t: 2 * T + t for t in range(T)}
    is_ = {t: 3 * T + t for t in range(T + 1)}
    ixi_p = 3 * T + (T + 1)
    ixi_m = ixi_p + 1

    def scen_var(m, kind, t=None):
        base = BASE2 + m * N_SCEN
        off = {"y": 0, "e": T, "g": 2 * T, "w": 3 * T, "u": 4 * T, "v": 5 * T, "q": 6 * T}[kind]
        return base + off if kind == "q" else base + off + t

    # ---------------- 目标系数（Q4-2 改动点 1、2）----------------
    c_obj = np.zeros(N_VARS, dtype=float)
    P_bar = P.mean(axis=0)                    # E[λ_t]
    for t in range(T):
        c_obj[ix[t]] += (1.0 - beta) * P_bar[t]     # ← Q2 为 (1-beta)*price[t]
        c_obj[ic[t]] += eps
        c_obj[ir[t]] += eps
    c_obj[ixi_p] = kappa2
    c_obj[ixi_m] = kappa2
    for m in range(M):
        for t in range(T):
            c_obj[scen_var(m, "e", t)] += (1.0 - beta) * 5.0 * prob * P[m, t]   # ← 逐场景
        c_obj[scen_var(m, "q")] += beta * (1.0 / (1.0 - alpha)) * prob
    c_obj[NZETA] = beta

    # ---------------- 约束装配 ----------------
    rows_eq, cols_eq, vals_eq = [], [], []
    rows_ub, cols_ub, vals_ub = [], [], []
    b_eq, b_ub = [], []

    # 等式 1：场景电量平衡 y+e+g+r = L+c+v
    for m in range(M):
        for t in range(T):
            row = m * T + t
            rows_eq += [row] * 6
            cols_eq += [scen_var(m, "y", t), scen_var(m, "e", t), scen_var(m, "g", t),
                        ir[t], ic[t], scen_var(m, "v", t)]
            vals_eq += [1.0, 1.0, 1.0, 1.0, -1.0, -1.0]
            b_eq.append(L[m, t])

    # 等式 2：u = x - y
    row_base2 = M * T
    for m in range(M):
        for t in range(T):
            row = row_base2 + m * T + t
            rows_eq += [row] * 3
            cols_eq += [ix[t], scen_var(m, "y", t), scen_var(m, "u", t)]
            vals_eq += [1.0, -1.0, -1.0]
            b_eq.append(0.0)

    # 等式 3：w = G - g
    row_base3 = 2 * M * T
    for m in range(M):
        for t in range(T):
            row = row_base3 + m * T + t
            rows_eq += [row] * 2
            cols_eq += [scen_var(m, "g", t), scen_var(m, "w", t)]
            vals_eq += [1.0, 1.0]
            b_eq.append(G[m, t])

    # 等式 4：SOC 递推
    row_base4 = 3 * M * T
    for t in range(1, T + 1):
        row = row_base4 + (t - 1)
        rows_eq += [row] * 4
        cols_eq += [is_[t], is_[t - 1], ic[t - 1], ir[t - 1]]
        vals_eq += [1.0, -1.0, -eta_c, 1.0 / eta_r]
        b_eq.append(0.0)

    # 等式 5：软终端 s_T - s_ref = xi_p - xi_m
    row_term = row_base4 + T
    rows_eq += [row_term] * 3
    cols_eq += [is_[T], ixi_p, ixi_m]
    vals_eq += [1.0, -1.0, 1.0]
    b_eq.append(s_ref)

    # y ≤ x（或全量提取敏感性 y = x）
    for m in range(M):
        for t in range(T):
            if full_extraction:
                row = len(b_eq)
                rows_eq += [row] * 2
                cols_eq += [scen_var(m, "y", t), ix[t]]
                vals_eq += [1.0, -1.0]
                b_eq.append(0.0)
            else:
                row = len(b_ub)
                rows_ub += [row] * 2
                cols_ub += [scen_var(m, "y", t), ix[t]]
                vals_ub += [1.0, -1.0]
                b_ub.append(0.0)

    # CVaR 线性化：q_m ≥ C^ω_m − ζ（Q4-2 改动点 3：λ 逐场景）
    row_ub2 = len(b_ub)
    for m in range(M):
        row = row_ub2 + m
        rows_ub.append(row); cols_ub.append(scen_var(m, "q")); vals_ub.append(-1.0)
        rows_ub.append(row); cols_ub.append(NZETA); vals_ub.append(-1.0)
        for t in range(T):
            rows_ub.append(row); cols_ub.append(ix[t]); vals_ub.append(P[m, t])
            rows_ub.append(row); cols_ub.append(scen_var(m, "e", t)); vals_ub.append(5.0 * P[m, t])
        b_ub.append(0.0)

    A_eq = coo_matrix((vals_eq, (rows_eq, cols_eq)), shape=(len(b_eq), N_VARS)).tocsr()
    A_ub = coo_matrix((vals_ub, (rows_ub, cols_ub)), shape=(len(b_ub), N_VARS)).tocsr()

    # ---------------- 变量边界 ----------------
    bounds = [(0.0, None)] * N_VARS
    for t in range(T):
        bounds[ic[t]] = (0.0, cap)
        bounds[ir[t]] = (0.0, cap)
    x_cap = p.get("x_cap")
    if x_cap is not None:
        for t in range(T):
            bounds[ix[t]] = (0.0, float(x_cap))
    for t in range(T + 1):
        bounds[is_[t]] = (s_min, s_max)
    bounds[is_[0]] = (s0, s0)
    if hard_terminal:
        bounds[is_[T]] = (s_ref, s_ref)
        bounds[ixi_p] = (0.0, 0.0)
        bounds[ixi_m] = (0.0, 0.0)
    for m in range(M):
        for t in range(T):
            bounds[scen_var(m, "g", t)] = (0.0, G[m, t])
    bounds[NZETA] = (None, None)

    # ---------------- 求解（与 Q2 相同的稳健策略）----------------
    b_ub_arr = np.asarray(b_ub, dtype=float)
    b_eq_arr = np.asarray(b_eq, dtype=float)
    res = linprog(c=c_obj, A_ub=A_ub, b_ub=b_ub_arr, A_eq=A_eq, b_eq=b_eq_arr,
                  bounds=bounds, method="highs")
    if res.status == 4:
        for method, options in (("highs-ds", {"presolve": False}),
                                ("highs-ipm", {}),
                                ("highs-ipm", {"presolve": False})):
            cand = linprog(c=c_obj, A_ub=A_ub, b_ub=b_ub_arr, A_eq=A_eq, b_eq=b_eq_arr,
                           bounds=bounds, method=method, options=options)
            res = cand
            if res.status == 0:
                break
    if res.status != 0:
        raise RuntimeError(f"LP 求解失败 status={res.status}: {res.message}")

    xopt = res.x
    eq_residual = float(np.max(np.abs(A_eq.dot(xopt) - b_eq_arr)))
    ub_violation = float(np.max(np.maximum(A_ub.dot(xopt) - b_ub_arr, 0.0)))
    if not np.all(np.isfinite(xopt)) or eq_residual > 1e-5 or ub_violation > 1e-5:
        raise RuntimeError(f"LP 解未通过独立残差验算: eq={eq_residual:.3e}, ub={ub_violation:.3e}")

    x = xopt[[ix[t] for t in range(T)]]
    c = xopt[[ic[t] for t in range(T)]]
    r = xopt[[ir[t] for t in range(T)]]
    s = xopt[[is_[t] for t in range(T + 1)]]
    xi_p = float(xopt[ixi_p]); xi_m = float(xopt[ixi_m])

    y = np.zeros((M, T)); e = np.zeros((M, T)); g = np.zeros((M, T))
    w = np.zeros((M, T)); u = np.zeros((M, T)); v = np.zeros((M, T)); q = np.zeros(M)
    for m in range(M):
        y[m] = xopt[[scen_var(m, "y", t) for t in range(T)]]
        e[m] = xopt[[scen_var(m, "e", t) for t in range(T)]]
        g[m] = xopt[[scen_var(m, "g", t) for t in range(T)]]
        w[m] = xopt[[scen_var(m, "w", t) for t in range(T)]]
        u[m] = xopt[[scen_var(m, "u", t) for t in range(T)]]
        v[m] = xopt[[scen_var(m, "v", t) for t in range(T)]]
        q[m] = xopt[scen_var(m, "q")]
    zeta = float(xopt[NZETA])

    # 场景成本（真实经济量，不含 eps/kappa2）—— Q4-2 中 λ 逐场景
    C = np.array([float(np.sum(P[m] * x) + 5.0 * np.sum(P[m] * e[m])) for m in range(M)])
    E_C = float(np.mean(C))
    # Report the empirical CVaR of the actual scenario-cost vector, rather
    # than the auxiliary LP variables.  This remains meaningful when beta=0,
    # where zeta and q are deliberately absent from the optimized objective.
    cvar = float(min(z + np.mean(np.maximum(C - z, 0.0)) / (1.0 - alpha)
                     for z in C))

    return {
        "x": x, "c": c, "r": r, "s": s, "xi_p": xi_p, "xi_m": xi_m,
        "objective": float(res.fun), "E_C": E_C, "CVaR": cvar, "C_scen": C,
        "y": y, "e": e, "g": g, "w": w, "u": u, "v": v, "q": q, "zeta": zeta,
        "status": int(res.status), "eq_residual": eq_residual, "ub_violation": ub_violation,
        "M": M, "P": P,
    }


def check_day(P, L, G, s0, params=None, verbose=True):
    """单日自检：平衡残差、SOC 越界、第一阶段单一版本、提取上限。"""
    plan = solve_day(P, L, G, s0, params)
    M = plan["M"]
    max_res = 0.0
    max_yx = -np.inf
    for m in range(M):
        for t in range(T):
            bal = (plan["y"][m, t] + plan["e"][m, t] + plan["g"][m, t] + plan["r"][t]
                   - L[m, t] - plan["c"][t] - plan["v"][m, t])
            max_res = max(max_res, abs(bal))
            max_yx = max(max_yx, plan["y"][m, t] - plan["x"][t])
    soc_bad = int(np.sum((plan["s"] < 1200.0 - 1e-6) | (plan["s"] > 10800.0 + 1e-6)))
    if verbose:
        print(f"    平衡残差最大值   = {max_res:.3e}")
        print(f"    y-x 最大越界     = {max_yx:.3e}")
        print(f"    SOC 越界个数     = {soc_bad}")
        print(f"    E[C]={plan['E_C']:.4f}  CVaR={plan['CVaR']:.4f}  objective={plan['objective']:.4f}")
    if max_res > 1e-6 or max_yx > 1e-6 or soc_bad > 0:
        raise RuntimeError("单日自检未通过")
    return plan
