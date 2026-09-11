# -*- coding: utf-8 -*-
"""
P3 当天真实数据事后结算（2026 数模 C 题 问题二）
================================================
实现依据：总纲第 4.2 节第 7 条、4.5 节（结算口径）、4.8 节注意事项。
本模块只在“当天真实负荷/光伏已知后”运行，绝不反向修改 0:00 计划。

【结算模型：方案 A（用户确认）】
- 实际充/放电不超过计划：0 <= c_actual <= c_plan，0 <= r_actual <= r_plan。
- 实际 SOC 受物理边界约束：1200 <= s_actual[t] <= 10800。
- 电量平衡（总纲 2.3 公共式）：y + e + g + r_actual = L + c_actual。
- 目标：min sum(5*pi*e) + M * sum((c_plan-c_actual) + (r_plan-r_actual))。
  其中 M 为“执行计划优先”的偏差惩罚（仅用于确定实际充放电，不属于报告费用），
  取 M 显著大于 5*max(pi) 以保证物理可行时优先按计划充放电。

【费用口径（总纲 4.5）】
- cost_plan = sum(pi * x)：计划购电按计划量全额付费。
- cost_emergency = sum(5*pi*e)：紧急购电严格按交易时刻电价 5 倍计费。
- 报告真实费用 = cost_plan + cost_emergency，不含 M 偏差项、eps 与 kappa2。
"""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

T = 144
ETA_C = 0.9
ETA_R = 0.9
SOC_MIN = 1200.0
SOC_MAX = 10800.0
M_PLAN = 20.0   # 执行计划优先的偏差惩罚（元/kWh），非报告费用项


def settle_day(price, x, c, r, L_actual, G_actual, s0, full_extraction=False):
    """
    给定 0:00 已锁定的计划 (x,c,r)，用当天真实负荷/光伏结算（方案 A）。

    参数
    ----
    price : (144,) 元/kWh
    x, c, r : (144,) 计划购电/充电/放电 kWh
    L_actual, G_actual : (144,) 当天真实负荷/光伏 kWh
    s0 : 当日实际期初 SOC
    full_extraction : 若 True，强制 y=x（计划量必须全部提取）

    返回
    ----
    settle : dict（y/e/g/w、c_actual/r_actual、s_actual、费用账、评价量）
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

    # 变量布局：
    #   y 0..143 ; e 144..287 ; g 288..431 ;
    #   c_actual 432..575 ; r_actual 576..719 ; s_actual 720..864 (t=0..144)
    n_vars = 6 * T + (T + 1)   # 865
    iy = {t: t for t in range(T)}
    ie = {t: T + t for t in range(T)}
    ig = {t: 2 * T + t for t in range(T)}
    ic = {t: 3 * T + t for t in range(T)}
    ir = {t: 4 * T + t for t in range(T)}
    is_ = {t: 5 * T + t for t in range(T + 1)}

    # 目标：min sum(5*pi*e) - M*sum(c_actual + r_actual)
    # （等价于 min sum(5*pi*e) + M*sum((c_plan-c_actual)+(r_plan-r_actual))，差常数）
    c_obj = np.zeros(n_vars)
    for t in range(T):
        c_obj[ie[t]] = 5.0 * price[t]
        c_obj[ic[t]] = -M_PLAN
        c_obj[ir[t]] = -M_PLAN

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

    result = linprog(c=c_obj, A_eq=A_eq, b_eq=np.array(b_eq), bounds=bounds, method="highs")
    if result.status != 0:
        raise RuntimeError(f"结算 LP 求解失败，status={result.status}, message={result.message}")

    sol = result.x
    y = sol[[iy[t] for t in range(T)]]
    e = sol[[ie[t] for t in range(T)]]
    g = sol[[ig[t] for t in range(T)]]
    c_actual = sol[[ic[t] for t in range(T)]]
    r_actual = sol[[ir[t] for t in range(T)]]
    s_actual = sol[[is_[t] for t in range(T + 1)]]
    w = G - g

    # 费用账（报告口径，不含 M 偏差项、eps/kappa2）
    cost_plan = float(np.sum(price * x))
    cost_emergency = float(np.sum(5.0 * price * e))
    cost_total = cost_plan + cost_emergency

    # 评价量
    load_total = float(np.sum(L))
    x_total = float(np.sum(x))
    g_total = float(np.sum(G))
    emergency_rate = float(np.sum(e) / load_total) if load_total else 0.0
    unextracted_ratio = float(np.sum(x - y) / x_total) if x_total else 0.0
    curtailment_rate = float(np.sum(w) / g_total) if g_total else 0.0
    soc_violate = int(np.sum((s_actual < SOC_MIN - 1e-6) | (s_actual > SOC_MAX + 1e-6)))
    # 计划执行偏差（透明性记录）
    dev_c = float(np.sum(c - c_actual))
    dev_r = float(np.sum(r - r_actual))

    return {
        "y": y, "e": e, "g": g, "w": w,
        "c_actual": c_actual, "r_actual": r_actual,
        "s_actual": s_actual,
        "cost_plan": cost_plan,
        "cost_emergency": cost_emergency,
        "cost_total": cost_total,
        "emergency_rate": emergency_rate,
        "unextracted_ratio": unextracted_ratio,
        "curtailment_rate": curtailment_rate,
        "soc_violate_count": soc_violate,
        "dev_c": dev_c, "dev_r": dev_r,
        "status": int(result.status),
    }
