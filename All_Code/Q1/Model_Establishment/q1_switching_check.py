# -*- coding: utf-8 -*-
"""问题1可选校验：在近似最低购电费用下，最小化充/放电模式切换。

MILP 不替代连续 LP。连续变量仍满足同一电量平衡、SOC、功率和周期约束；
二进制变量仅描述充电/放电通道是否处于启用状态。一次充电转放电会产生
两个二进制通道变化，因此输出名称使用 channel_state_changes，避免误称设备启停次数。
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix, vstack

HERE = Path(__file__).resolve().parent
MODEL_PATH = HERE / "q1_model.py"
Q1_DIR = HERE.parent
OUTPUT = Q1_DIR / "Tables" / "q1_switching_summary.json"

spec = importlib.util.spec_from_file_location("q1_model", MODEL_PATH)
q1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q1)


def solve_switching_milp():
    _, pi, load, pv = q1.load_data()
    lp = q1.build_and_solve(pi, load, pv)
    _, a_eq_base, b_eq, base_bounds = q1._build_lp(pi, load, pv)

    base_n = 5 * q1.T
    bc0 = base_n
    br0 = bc0 + q1.T
    vc0 = br0 + q1.T
    vr0 = vc0 + q1.T - 1
    n = vr0 + q1.T - 1

    # 首要目标是减少二进制通道状态变化；极小 active 权重只消除空载时任意置 1。
    obj = np.zeros(n)
    obj[bc0:br0] = 1e-6
    obj[br0:vc0] = 1e-6
    obj[vc0:vr0] = 1.0
    obj[vr0:n] = 1.0

    a_eq = lil_matrix((a_eq_base.shape[0], n))
    a_eq[:, :base_n] = a_eq_base
    constraints = [LinearConstraint(a_eq.tocsr(), b_eq, b_eq)]

    rows = []
    upper = []

    # 购电费用不得超过连续 LP 最优费用加容差。
    row = lil_matrix((1, n))
    row[0, :q1.T] = pi
    rows.append(row)
    upper.append(lp["C1_star"] + q1.COST_TOL)

    for t in range(q1.T):
        # c_t <= Cmax * bc_t, r_t <= Rmax * br_t, bc_t + br_t <= 1
        row_c = lil_matrix((1, n)); row_c[0, q1.T + t] = 1; row_c[0, bc0 + t] = -q1.P_MAX_KWH
        row_r = lil_matrix((1, n)); row_r[0, 2 * q1.T + t] = 1; row_r[0, br0 + t] = -q1.P_MAX_KWH
        row_m = lil_matrix((1, n)); row_m[0, bc0 + t] = 1; row_m[0, br0 + t] = 1
        rows.extend([row_c, row_r, row_m]); upper.extend([0.0, 0.0, 1.0])

    for t in range(1, q1.T):
        j = t - 1
        for start, change in [(bc0, vc0), (br0, vr0)]:
            row_up = lil_matrix((1, n))
            row_up[0, start + t] = 1; row_up[0, start + t - 1] = -1; row_up[0, change + j] = -1
            row_dn = lil_matrix((1, n))
            row_dn[0, start + t - 1] = 1; row_dn[0, start + t] = -1; row_dn[0, change + j] = -1
            rows.extend([row_up, row_dn]); upper.extend([0.0, 0.0])

    a_ub = vstack(rows).tocsr()
    constraints.append(LinearConstraint(a_ub, -np.inf, np.asarray(upper)))

    lower = np.zeros(n)
    upper_bounds = np.full(n, np.inf)
    for j, (lo, hi) in enumerate(base_bounds):
        lower[j] = lo if lo is not None else -np.inf
        upper_bounds[j] = hi if hi is not None else np.inf
    upper_bounds[bc0:n] = 1.0

    integrality = np.zeros(n, dtype=int)
    integrality[bc0:n] = 1
    result = milp(
        c=obj,
        integrality=integrality,
        bounds=Bounds(lower, upper_bounds),
        constraints=constraints,
        options={"time_limit": 120.0, "mip_rel_gap": 0.0},
    )
    if not result.success:
        raise RuntimeError(f"切换 MILP 求解失败: status={result.status}, message={result.message}")

    x = result.x[:q1.T]
    charge = result.x[q1.T:2 * q1.T]
    discharge = result.x[2 * q1.T:3 * q1.T]
    bc = np.rint(result.x[bc0:br0]).astype(int)
    br = np.rint(result.x[br0:vc0]).astype(int)
    channel_changes = int(np.abs(np.diff(bc)).sum() + np.abs(np.diff(br)).sum())

    summary = {
        "definition": "sum absolute changes of charge-enabled and discharge-enabled binary channels",
        "C1_stage1_optimal_cost_yuan": lp["C1_star"],
        "milp_purchase_cost_yuan": float(pi @ x),
        "cost_gap_yuan": float(pi @ x - lp["C1_star"]),
        "cost_tolerance_yuan": q1.COST_TOL,
        "channel_state_changes": channel_changes,
        "charge_enabled_intervals": int(bc.sum()),
        "discharge_enabled_intervals": int(br.sum()),
        "actual_charge_intervals": int((charge > 1e-7).sum()),
        "actual_discharge_intervals": int((discharge > 1e-7).sum()),
        "simultaneous_charge_discharge_intervals": int(((charge > 1e-7) & (discharge > 1e-7)).sum()),
        "solver_message": result.message,
    }
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = solve_switching_milp()
    print(json.dumps(result, ensure_ascii=False, indent=2))
