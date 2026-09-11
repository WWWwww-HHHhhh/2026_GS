# -*- coding: utf-8 -*-
"""
P2 两阶段随机 LP + CVaR 单日优化器（2026 数模 C 题 问题二）
============================================================
实现依据：总纲第 4.1（题意）、4.4（符号）、4.5（目标与 CVaR）、4.6（约束）、2.3（公共物理约束）。
实现方式：环境无 PuLP，按提示词要求用 scipy.optimize.linprog(HiGHS) 自建稀疏矩阵。

【全局铁律摘要】
1. 第一阶段变量 x/c/r/s/xi 跨场景共享（非预期性），严禁写成 c^w,r^w,s^w。
2. 第二阶段变量 y/u/e/g/w/q 每个场景 m 独立。
3. 惩罚项 eps 与软终端罚项 kappa2 只用于求解；报告的真实费用不含它们。
4. 公共电量平衡式 y+e+g+r = L+c；SOC 递推 s_t = s_{t-1} + eta_c*c_t - r_t/eta_r。
5. 紧急购电严格按交易时刻电价的 5 倍计费。
"""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

T = 144
DEFAULT_PARAMS = {
    "alpha": 0.90,
    "beta": 0.5,
    "eps": 1e-4,
    "kappa2": None,          # 必须由调用方传入（P0 校准的 kappa2_base 或其倍数）
    "eta_c": 0.9,
    "eta_r": 0.9,
    "s_min": 1200.0,
    "s_max": 10800.0,
    "cap": 833.3333333333334,  # 5000 kW * 1/6 h
    "s_ref": None,            # 默认取 s0
    "full_extraction": False, # 若 True，强制 y=x（全量提取敏感性）
}


def solve_day2(price, scenarios, s0, params=None):
    """
    求解问题二单日两阶段随机 LP + CVaR。

    参数
    ----
    price : (144,) 元/kWh，当日确定电价。
    scenarios : (M, 2, 144) 或 (M, 144) 负荷 + (M, 144) 光伏；这里约定传入 dict：
        {"L": (M,144), "G": (M,144)}。
    s0 : float，当日 0:00 期初 SOC。
    params : dict，覆盖 DEFAULT_PARAMS。

    返回
    ----
    plan : dict，含 x/c/r/s/xi_p/xi_m/objective/E_C/CVaR/y/e/g/w/u/q/zeta/status 等。
    """
    if params is None:
        params = {}
    p = dict(DEFAULT_PARAMS)
    p.update({k: v for k, v in params.items() if v is not None})
    alpha = float(p["alpha"])
    beta = float(p["beta"])
    eps = float(p["eps"])
    kappa2 = float(p["kappa2"])
    eta_c = float(p["eta_c"])
    eta_r = float(p["eta_r"])
    s_min = float(p["s_min"])
    s_max = float(p["s_max"])
    cap = float(p["cap"])
    s_ref = float(s0) if p["s_ref"] is None else float(p["s_ref"])
    full_extraction = bool(p.get("full_extraction", False))

    price = np.asarray(price, dtype=float)
    if price.shape != (T,):
        raise ValueError(f"price 应为 ({T},)，实际 {price.shape}")
    if (price <= 0).any():
        raise ValueError("电价必须为正（总纲 2.2: pi>0）")
    L = np.asarray(scenarios["L"], dtype=float)
    G = np.asarray(scenarios["G"], dtype=float)
    if L.ndim != 2 or G.ndim != 2 or L.shape[0] != G.shape[0] or L.shape[1] != T:
        raise ValueError(f"场景形状异常: L={L.shape}, G={G.shape}")
    M = int(L.shape[0])
    prob = 1.0 / M

    # ------------------------------------------------------------------
    # 变量布局（全部变量索引）
    # ------------------------------------------------------------------
    # 第一阶段（跨场景共享）：
    #   x: 0..143 ; c: 144..287 ; r: 288..431 ; s: 432..576 (t=0..144) ;
    #   xi_p: 577 ; xi_m: 578
    # 第二阶段：每场景 721 个变量（y/e/g/w/u 各 144 + q 1）
    #   y: 0..143 ; e: 144..287 ; g: 288..431 ; w: 432..575 ; u: 576..719 ; q: 720
    # zeta: 最后 1 个自由变量
    N_FIRST = 3 * T + (T + 1) + 2          # 579
    N_SCEN = 5 * T + 1                     # 721
    BASE2 = N_FIRST
    NZETA = N_FIRST + M * N_SCEN
    N_VARS = NZETA + 1

    ix = {t: t for t in range(T)}
    ic = {t: T + t for t in range(T)}
    ir = {t: 2 * T + t for t in range(T)}
    is_ = {t: 3 * T + t for t in range(T + 1)}   # s[t]
    ixi_p = 3 * T + (T + 1)
    ixi_m = ixi_p + 1

    def scen_var(m, kind, t=None):
        base = BASE2 + m * N_SCEN
        off = {"y": 0, "e": T, "g": 2 * T, "w": 3 * T, "u": 4 * T, "q": 5 * T}[kind]
        if kind == "q":
            return base + off
        return base + off + t

    # ------------------------------------------------------------------
    # 目标系数
    # ------------------------------------------------------------------
    c_obj = np.zeros(N_VARS, dtype=float)
    for t in range(T):
        c_obj[ix[t]] += (1.0 - beta) * price[t]           # (1-beta)*E[C] 中的 x 部分
        c_obj[ic[t]] += eps                                # 充电小量惩罚
        c_obj[ir[t]] += eps                                # 放电小量惩罚
    c_obj[ixi_p] = kappa2
    c_obj[ixi_m] = kappa2
    for m in range(M):
        for t in range(T):
            c_obj[scen_var(m, "e", t)] += (1.0 - beta) * 5.0 * prob * price[t]
        c_obj[scen_var(m, "q")] += beta * (1.0 / (1.0 - alpha)) * prob
    c_obj[NZETA] = beta

    # ------------------------------------------------------------------
    # 约束（COO 稀疏构建）
    # ------------------------------------------------------------------
    rows_eq, cols_eq, vals_eq = [], [], []
    rows_ub, cols_ub, vals_ub = [], [], []
    b_eq, b_ub = [], []

    # 等式 1：场景电量平衡 y+e+g+r = L+c  (M*T 行)
    for m in range(M):
        for t in range(T):
            row = m * T + t
            rows_eq += [row] * 5
            cols_eq += [scen_var(m, "y", t), scen_var(m, "e", t), scen_var(m, "g", t), ir[t], ic[t]]
            vals_eq += [1.0, 1.0, 1.0, 1.0, -1.0]
            b_eq.append(L[m, t])

    # 等式 2：u = x - y  ->  x - y - u = 0  (M*T 行)
    row_base2 = M * T
    for m in range(M):
        for t in range(T):
            row = row_base2 + m * T + t
            rows_eq += [row] * 3
            cols_eq += [ix[t], scen_var(m, "y", t), scen_var(m, "u", t)]
            vals_eq += [1.0, -1.0, -1.0]
            b_eq.append(0.0)

    # 等式 3：w = G - g  ->  g + w = G  (M*T 行)
    row_base3 = 2 * M * T
    for m in range(M):
        for t in range(T):
            row = row_base3 + m * T + t
            rows_eq += [row] * 2
            cols_eq += [scen_var(m, "g", t), scen_var(m, "w", t)]
            vals_eq += [1.0, 1.0]
            b_eq.append(G[m, t])

    # 等式 4：SOC 递推 s_t - s_{t-1} - eta_c*c_t + r_t/eta_r = 0  (T 行)
    row_base4 = 3 * M * T
    for t in range(1, T + 1):
        row = row_base4 + (t - 1)
        rows_eq += [row] * 4
        cols_eq += [is_[t], is_[t - 1], ic[t - 1], ir[t - 1]]
        vals_eq += [1.0, -1.0, -eta_c, 1.0 / eta_r]
        b_eq.append(0.0)

    # 等式 5：软终端 s_T - s_ref = xi_p - xi_m  (1 行)
    row_term = row_base4 + T
    rows_eq += [row_term] * 3
    cols_eq += [is_[T], ixi_p, ixi_m]
    vals_eq += [1.0, -1.0, 1.0]
    b_eq.append(s_ref)

    # 约束：y <= x（默认） 或 全量提取敏感性 y == x（总纲 4.1/4.8）
    for m in range(M):
        for t in range(T):
            if full_extraction:
                # y - x = 0 作为等式
                row = len(b_eq)
                rows_eq += [row] * 2
                cols_eq += [scen_var(m, "y", t), ix[t]]
                vals_eq += [1.0, -1.0]
                b_eq.append(0.0)
            else:
                # y - x <= 0
                row = len(b_ub)
                rows_ub += [row] * 2
                cols_ub += [scen_var(m, "y", t), ix[t]]
                vals_ub += [1.0, -1.0]
                b_ub.append(0.0)

    # 不等式 2：CVaR 线性化 q >= C - zeta  ->  -q + C - zeta <= 0  (M 行)
    # C = sum_t pi_t*x_t + 5*sum_t pi_t*e_mt
    row_ub2 = len(b_ub)
    for m in range(M):
        row = row_ub2 + m
        rows_ub.append(row)
        cols_ub.append(scen_var(m, "q"))
        vals_ub.append(-1.0)
        rows_ub.append(row)
        cols_ub.append(NZETA)
        vals_ub.append(-1.0)
        for t in range(T):
            rows_ub.append(row)
            cols_ub.append(ix[t])
            vals_ub.append(price[t])
            rows_ub.append(row)
            cols_ub.append(scen_var(m, "e", t))
            vals_ub.append(5.0 * price[t])
        b_ub.append(0.0)

    A_eq = coo_matrix((vals_eq, (rows_eq, cols_eq)), shape=(len(b_eq), N_VARS)).tocsr()
    A_ub = coo_matrix((vals_ub, (rows_ub, cols_ub)), shape=(len(b_ub), N_VARS)).tocsr()

    # ------------------------------------------------------------------
    # 变量边界
    # ------------------------------------------------------------------
    bounds = [(0.0, None)] * N_VARS
    for t in range(T):
        bounds[ic[t]] = (0.0, cap)     # 0 <= c_t <= C_bar
        bounds[ir[t]] = (0.0, cap)     # 0 <= r_t <= R_bar
    for t in range(T + 1):
        bounds[is_[t]] = (s_min, s_max)
    bounds[is_[0]] = (s0, s0)          # 期初 SOC 固定
    for m in range(M):
        for t in range(T):
            bounds[scen_var(m, "g", t)] = (0.0, G[m, t])
    bounds[NZETA] = (None, None)       # zeta 自由

    # ------------------------------------------------------------------
    # 求解
    # ------------------------------------------------------------------
    result = linprog(c=c_obj, A_ub=A_ub, b_ub=np.array(b_ub),
                     A_eq=A_eq, b_eq=np.array(b_eq), bounds=bounds,
                     method="highs")
    if result.status != 0:
        raise RuntimeError(f"LP 求解失败，status={result.status}, message={result.message}")

    xopt = result.x

    # 提取第一阶段
    x = xopt[[ix[t] for t in range(T)]]
    c = xopt[[ic[t] for t in range(T)]]
    r = xopt[[ir[t] for t in range(T)]]
    s = xopt[[is_[t] for t in range(T + 1)]]
    xi_p = xopt[ixi_p]
    xi_m = xopt[ixi_m]

    # 提取第二阶段
    y = np.zeros((M, T)); e = np.zeros((M, T)); g = np.zeros((M, T))
    w = np.zeros((M, T)); u = np.zeros((M, T)); q = np.zeros(M)
    for m in range(M):
        y[m] = xopt[[scen_var(m, "y", t) for t in range(T)]]
        e[m] = xopt[[scen_var(m, "e", t) for t in range(T)]]
        g[m] = xopt[[scen_var(m, "g", t) for t in range(T)]]
        w[m] = xopt[[scen_var(m, "w", t) for t in range(T)]]
        u[m] = xopt[[scen_var(m, "u", t) for t in range(T)]]
        q[m] = xopt[scen_var(m, "q")]
    zeta = xopt[NZETA]

    # 场景成本与期望成本 / CVaR（真实经济量，不含 eps/kappa2）
    C = np.array([float(np.sum(price * x) + 5.0 * np.sum(price * e[m])) for m in range(M)])
    E_C = float(np.mean(C))
    cvar = float(zeta + (1.0 / (1.0 - alpha)) * np.mean(q))

    plan = {
        "x": x, "c": c, "r": r, "s": s, "xi_p": float(xi_p), "xi_m": float(xi_m),
        "objective": float(result.fun),   # 含 eps/kappa2 罚项，仅求解用
        "E_C": E_C,
        "CVaR": cvar,
        "C_scen": C,
        "y": y, "e": e, "g": g, "w": w, "u": u, "q": q, "zeta": float(zeta),
        "status": int(result.status),
    }
    return plan


def check_day(price, scenarios, s0, params=None):
    """随机一天跑通后的自检：打印平衡残差最大值、SOC 越界、第一阶段单一版本。"""
    plan = solve_day2(price, scenarios, s0, params)
    M, Tt = scenarios["L"].shape
    max_res = 0.0
    for m in range(M):
        for t in range(Tt):
            res = abs(plan["y"][m, t] + plan["e"][m, t] + plan["g"][m, t] + plan["r"][t]
                      - scenarios["L"][m, t] - plan["c"][t])
            max_res = max(max_res, res)
    soc_violate = (plan["s"] < DEFAULT_PARAMS["s_min"] - 1e-6) | (plan["s"] > DEFAULT_PARAMS["s_max"] + 1e-6)
    print(f"    平衡残差最大值 = {max_res:.3e}")
    print(f"    SOC 越界个数 = {int(np.sum(soc_violate))}")
    print(f"    第一阶段 x/c/r/s 单一版本（非场景相关）= True")
    print(f"    E[C]={plan['E_C']:.4f}, CVaR={plan['CVaR']:.4f}, objective={plan['objective']:.4f}")
    return plan


if __name__ == "__main__":
    import pickle, os
    import numpy as np
    GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
    DATA_PROC = os.path.join(GS, r"All_Code\Q2\Data_processing")
    with open(os.path.join(DATA_PROC, "q2_dataset.pkl"), "rb") as fh:
        ds = pickle.load(fh)
    with open(os.path.join(DATA_PROC, "scenarios_M20.pkl"), "rb") as fh:
        sc = pickle.load(fh)
    # 随机一天（例如报告期第 1 天 2025-02-01 的索引 31）
    i = 31
    price = ds["price"][:, i]
    L = sc["L_all"][i]; G = sc["G_all"][i]
    kappa2_base = ds["kappa2_base"]
    check_day(price, {"L": L, "G": G}, 6000.0, {"kappa2": kappa2_base, "beta": 0.5})
