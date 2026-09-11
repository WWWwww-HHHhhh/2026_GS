# -*- coding: utf-8 -*-
"""
P3 当天真实数据事后结算（2026 数模 C 题 问题二）
================================================
实现依据：总纲第 4.2 节第 7 条、4.5 节（结算口径）、4.8 节注意事项。
本模块只在“当天真实负荷/光伏已知后”运行，绝不反向修改 0:00 计划。

【结算模型：方案 A（用户确认）——词典序两阶段结算】
- 实际充/放电不超过计划：0 <= c_actual <= c_plan，0 <= r_actual <= r_plan。
- 实际 SOC 受物理边界约束：1200 <= s_actual[t] <= 10800。
- 电量平衡（总纲 2.3 公共式）：y + e + g + r_actual = L + c_actual。
- 第一阶段只最小化真实紧急购电费：min sum(5*pi*e)。
- 第二阶段在“紧急购电费不超过第一阶段最优值+容差”的前提下，最大化计划充放电
  执行量（等价于最小化偏离计划量）。第二阶段只用于确定实际执行轨迹，不改变
  报告费用，不计入任何罚项。
- 旧版 M_PLAN = 20 加权目标保留为 settle_day_weighted_legacy()，仅用于历史
  敏感性对比；正式滚动与 Q3 接口一律调用词典序 settle_day()。

【费用口径（总纲 4.5）】
- cost_plan = sum(pi * x)：计划购电按计划量全额付费。
- cost_emergency = sum(5*pi*e)：紧急购电严格按交易时刻电价 5 倍计费。
- 报告真实费用 = cost_plan + cost_emergency，不含偏差项、eps 与 kappa2。
"""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

T = 144
ETA_C = 0.9
ETA_R = 0.9
SOC_MIN = 1200.0
SOC_MAX = 10800.0
M_PLAN = 20.0   # 仅用于 settle_day_weighted_legacy（历史对比），正式结算不再使用


def _build_lp(price, x, c, r, L, G, s0, full_extraction):
    """构造结算 LP 的等式、边界与变量索引（词典序与旧加权目标共用）。
    变量布局：y 0..143 ; e 144..287 ; g 288..431 ;
              c_actual 432..575 ; r_actual 576..719 ; s_actual 720..864 (t=0..144)
    """
    n_vars = 6 * T + (T + 1)   # 865
    iy = {t: t for t in range(T)}
    ie = {t: T + t for t in range(T)}
    ig = {t: 2 * T + t for t in range(T)}
    ic = {t: 3 * T + t for t in range(T)}
    ir = {t: 4 * T + t for t in range(T)}
    is_ = {t: 5 * T + t for t in range(T + 1)}

    # 等式 1：电量平衡 y + e + g + r_actual - c_actual = L  (T 行)
    rows, cols, vals = [], [], []
    b_eq = []
    for t in range(T):
        row = t
        rows += [row] * 5
        cols += [iy[t], ie[t], ig[t], ir[t], ic[t]]
        vals += [1.0, 1.0, 1.0, 1.0, -1.0]
        b_eq.append(L[t])

    # 等式 2：实际 SOC 递推 s_t - s_{t-1} - eta_c*c_{t-1} + r_{t-1}/eta_r = 0  (T 行)
    for t in range(1, T + 1):
        row = T + (t - 1)
        rows += [row] * 4
        cols += [is_[t], is_[t - 1], ic[t - 1], ir[t - 1]]
        vals += [1.0, -1.0, -ETA_C, 1.0 / ETA_R]
        b_eq.append(0.0)

    A_eq = coo_matrix((vals, (rows, cols)), shape=(2 * T, n_vars)).tocsr()

    # 边界
    bounds = [(0.0, None)] * n_vars
    for t in range(T):
        if full_extraction:
            bounds[iy[t]] = (x[t], x[t])
        else:
            bounds[iy[t]] = (0.0, x[t])
        bounds[ig[t]] = (0.0, G[t])
        bounds[ic[t]] = (0.0, c[t])    # 0 <= c_actual <= c_plan
        bounds[ir[t]] = (0.0, r[t])    # 0 <= r_actual <= r_plan
    for t in range(T + 1):
        bounds[is_[t]] = (SOC_MIN, SOC_MAX)
    bounds[is_[0]] = (s0, s0)          # 期初实际 SOC 固定
    return A_eq, np.asarray(b_eq, dtype=float), bounds, (iy, ie, ig, ic, ir, is_)


def _extract_solution(sol, idx, price, x, c, r, L, G):
    """从最优解提取轨迹与费用账（报告口径，不含任何罚项）。"""
    iy, ie, ig, ic, ir, is_ = idx
    y = sol[[iy[t] for t in range(T)]]
    e = sol[[ie[t] for t in range(T)]]
    g = sol[[ig[t] for t in range(T)]]
    c_actual = sol[[ic[t] for t in range(T)]]
    r_actual = sol[[ir[t] for t in range(T)]]
    s_actual = sol[[is_[t] for t in range(T + 1)]]
    w = G - g

    cost_plan = float(np.sum(price * x))
    cost_emergency = float(np.sum(5.0 * price * e))
    cost_total = cost_plan + cost_emergency

    load_total = float(np.sum(L))
    x_total = float(np.sum(x))
    g_total = float(np.sum(G))
    emergency_rate = float(np.sum(e) / load_total) if load_total else 0.0
    unextracted_ratio = float(np.sum(x - y) / x_total) if x_total else 0.0
    curtailment_rate = float(np.sum(w) / g_total) if g_total else 0.0
    soc_violate = int(np.sum((s_actual < SOC_MIN - 1e-6) | (s_actual > SOC_MAX + 1e-6)))
    dev_c = float(np.sum(c - c_actual))
    dev_r = float(np.sum(r - r_actual))
    accounts = {
        "cost_plan": cost_plan, "cost_emergency": cost_emergency, "cost_total": cost_total,
        "emergency_rate": emergency_rate, "unextracted_ratio": unextracted_ratio,
        "curtailment_rate": curtailment_rate, "soc_violate_count": soc_violate,
        "dev_c": dev_c, "dev_r": dev_r,
    }
    return y, e, g, w, c_actual, r_actual, s_actual, accounts


def settle_day(price, x, c, r, L_actual, G_actual, s0, full_extraction=False):
    """
    词典序两阶段事后结算（正式方法，Q3 接口唯一结算口径）。

    第一阶段：min sum(5*pi*e)，得到 primary_cost。
    第二阶段：新增一行“紧急购电费 <= primary_cost + cost_tol”上界，
              min -sum(c_actual + r_actual)，即最大化计划充放电执行量。
    若第二阶段求解失败，回退第一阶段最优解并如实记录 secondary_status。
    """
    price = np.asarray(price, dtype=float)
    x = np.asarray(x, dtype=float)
    c = np.asarray(c, dtype=float)
    r = np.asarray(r, dtype=float)
    L = np.asarray(L_actual, dtype=float)
    G = np.asarray(G_actual, dtype=float)
    for name, arr in (("x", x), ("c", c), ("r", r), ("L", L), ("G", G)):
        if arr.shape != (T,):
            raise ValueError(f"{name} 形状应为 ({T},)，实际 {arr.shape}")

    n_vars = 6 * T + (T + 1)
    A_eq, b_eq, bounds, idx = _build_lp(price, x, c, r, L, G, s0, full_extraction)
    iy, ie, ig, ic, ir, is_ = idx

    # ---- 第一阶段：只最小化真实紧急购电费 ----
    primary_obj = np.zeros(n_vars)
    for t in range(T):
        primary_obj[ie[t]] = 5.0 * price[t]
    primary = linprog(c=primary_obj, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if primary.status != 0:
        raise RuntimeError(f"结算主目标求解失败，status={primary.status}, message={primary.message}")
    primary_cost = float(primary.fun)
    cost_tol = max(1.0e-6, 1.0e-9 * max(1.0, abs(primary_cost)))

    # ---- 第二阶段：固定紧急购电费上界，最大化计划充放电执行量 ----
    cost_cols = [ie[t] for t in range(T)]
    cost_vals = [5.0 * price[t] for t in range(T)]
    cost_rows = [0] * T
    A_cost = coo_matrix((cost_vals, (cost_rows, cost_cols)), shape=(1, n_vars)).tocsr()

    secondary_obj = np.zeros(n_vars)
    for t in range(T):
        secondary_obj[ic[t]] = -1.0
        secondary_obj[ir[t]] = -1.0

    secondary = linprog(c=secondary_obj, A_ub=A_cost, b_ub=np.array([primary_cost + cost_tol]),
                        A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    result = secondary if secondary.status == 0 else primary

    sol = result.x
    y, e, g, w, c_actual, r_actual, s_actual, accounts = _extract_solution(
        sol, idx, price, x, c, r, L, G)
    emergency_cost_gap = float(accounts["cost_emergency"] - primary_cost)

    out = dict(accounts)
    out.update({
        "y": y, "e": e, "g": g, "w": w,
        "c_actual": c_actual, "r_actual": r_actual, "s_actual": s_actual,
        "status": int(result.status),
        "settlement_method": "lexicographic",
        "primary_emergency_cost": primary_cost,
        "secondary_status": int(secondary.status),
        "emergency_cost_gap": emergency_cost_gap,
        "cost_tolerance": float(cost_tol),
    })
    return out


def settle_day_weighted_legacy(price, x, c, r, L_actual, G_actual, s0, full_extraction=False):
    """
    旧版 M_PLAN = 20 加权目标结算（仅历史敏感性对比，逻辑与修改前完全一致）。
    正式滚动与 Q3 接口不得调用本函数。
    """
    price = np.asarray(price, dtype=float)
    x = np.asarray(x, dtype=float)
    c = np.asarray(c, dtype=float)
    r = np.asarray(r, dtype=float)
    L = np.asarray(L_actual, dtype=float)
    G = np.asarray(G_actual, dtype=float)
    for name, arr in (("x", x), ("c", c), ("r", r), ("L", L), ("G", G)):
        if arr.shape != (T,):
            raise ValueError(f"{name} 形状应为 ({T},)，实际 {arr.shape}")

    n_vars = 6 * T + (T + 1)
    A_eq, b_eq, bounds, idx = _build_lp(price, x, c, r, L, G, s0, full_extraction)
    iy, ie, ig, ic, ir, is_ = idx

    c_obj = np.zeros(n_vars)
    for t in range(T):
        c_obj[ie[t]] = 5.0 * price[t]
        c_obj[ic[t]] = -M_PLAN
        c_obj[ir[t]] = -M_PLAN

    result = linprog(c=c_obj, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if result.status != 0:
        raise RuntimeError(f"结算 LP 求解失败，status={result.status}, message={result.message}")

    sol = result.x
    y, e, g, w, c_actual, r_actual, s_actual, accounts = _extract_solution(
        sol, idx, price, x, c, r, L, G)
    out = dict(accounts)
    out.update({
        "y": y, "e": e, "g": g, "w": w,
        "c_actual": c_actual, "r_actual": r_actual, "s_actual": s_actual,
        "status": int(result.status),
        "settlement_method": "weighted(M_PLAN=20)",
        "primary_emergency_cost": float(np.nan),
        "secondary_status": int(result.status),
        "emergency_cost_gap": float(np.nan),
        "cost_tolerance": float(np.nan),
    })
    return out
