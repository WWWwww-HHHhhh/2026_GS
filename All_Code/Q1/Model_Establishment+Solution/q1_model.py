# -*- coding: utf-8 -*-
"""
问题1：含弃光和储能边际价值的连续 LP（HiGHS 求解）

输入数据：Data/附件/附件1.xlsx（144 个 10 min 时段的电价、小区负载、光伏预测功率）
         Data/附件/附件5/result1.xlsx（官方结果模板）
运行方法：python q1_model.py（依赖 numpy/pandas/scipy/openpyxl；Python 3.13 验证通过）
输出位置：All_Code/Q1/Tables/（result1.xlsx、q1_timeseries.csv、q1_summary.json）

模型（确定性单日，功率 × 1/6 转为时段电量 kWh）：
    第一阶段：min C1 = sum_t pi_t * x_t
    第二阶段：s.t. C1 <= C1* + tol，min sum_t(c_t+r_t)
    s.t. x_t + (G_t - w_t) + r_t = L_t + c_t        电量平衡（含弃光）
         s_t = s_{t-1} + eta_c*c_t - r_t/eta_r     储能递推
         S_min <= s_t <= S_max, s_0 = s_T = 6000   SOC 边界（问题1硬周期）
         0 <= c_t, r_t <= 833.3333                  5000 kW 折算时段电量
         0 <= w_t <= G_t, x_t >= 0
对偶变量从第一阶段纯购电费用 LP 提取；第二阶段只负责在近似等费用解中减少无意义吞吐。
mu_bal = 时段边际供电成本；储能边际价值 = -mu_soc。符号约定用单个约束 RHS 扰动核验。
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog

# ---------------------------------------------------------------- 路径与常量
Q1_DIR = Path(__file__).resolve().parents[1]           # All_Code/Q1
REPO_ROOT = Path(__file__).resolve().parents[3]        # 仓库根目录
DATA_XLSX = REPO_ROOT / "Data" / "附件" / "附件1.xlsx"
TEMPLATE_XLSX = REPO_ROOT / "Data" / "附件" / "附件5" / "result1.xlsx"
RESULTS = Q1_DIR / "Tables"
RESULTS.mkdir(exist_ok=True)

T = 144                      # 每日 10 min 时段数
DT = 1.0 / 6.0               # 时段长度 h
S_MIN, S_MAX = 1200.0, 10800.0
S0 = 6000.0                  # 0:00 与 24:00 储电量（问题1硬边界）
P_MAX_KWH = 5000.0 * DT      # 单时段最大充/放电量 833.3333 kWh
ETA_C = ETA_R = 0.9
COST_TOL = 1e-4              # 二级 LP 允许的购电费用绝对容差，元


def load_data():
    """读取附件1：144 个时段的电价(元/kWh)、负载(kW)、光伏预测(kW)，功率乘 1/6 转电量。"""
    if not DATA_XLSX.is_file():
        raise FileNotFoundError(f"找不到输入文件: {DATA_XLSX}")
    df = pd.read_excel(DATA_XLSX, header=0)
    if df.shape[1] != 4:
        raise ValueError(f"附件1应有4列，实际 {df.shape[1]} 列")
    df.columns = ["time_label", "price", "load_kw", "pv_kw"]
    if len(df) != T:
        raise ValueError(f"附件1应有 {T} 行，实际 {len(df)} 行")
    if df["time_label"].isna().any() or df["time_label"].astype(str).duplicated().any():
        raise ValueError("附件1时间标签存在缺失或重复")
    for col in ["price", "load_kw", "pv_kw"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[["price", "load_kw", "pv_kw"]].isna().any().any():
        raise ValueError("附件1的电价、负荷或光伏列存在缺失/非数值")
    if (df[["price", "load_kw", "pv_kw"]] < 0).any().any():
        raise ValueError("附件1出现负电价、负负荷或负光伏值，需先核对数据")
    L = df["load_kw"].to_numpy(float) * DT   # kWh/时段
    G = df["pv_kw"].to_numpy(float) * DT
    pi = df["price"].to_numpy(float)
    return df, pi, L, G


def _build_lp(pi, L, G, soc_rhs_injection=None):
    """构造公共 LP 矩阵；soc_rhs_injection 只用于对偶有限差分验证。"""
    if not (len(pi) == len(L) == len(G) == T):
        raise ValueError("pi、L、G 均应包含144个时段")
    soc_rhs_injection = (np.zeros(T) if soc_rhs_injection is None
                         else np.asarray(soc_rhs_injection, dtype=float))
    if soc_rhs_injection.shape != (T,):
        raise ValueError("soc_rhs_injection 应为长度144的向量")
    n = 5 * T
    economic_obj = np.concatenate([pi, np.zeros(4 * T)])

    A_eq, b_eq = [], []

    # 电量平衡：x_t - w_t + r_t - c_t = L_t - G_t
    for t in range(T):
        row = np.zeros(n)
        row[t] = 1.0            # x_t
        row[T + t] = -1.0       # -c_t
        row[2 * T + t] = 1.0    # +r_t
        row[3 * T + t] = -1.0   # -w_t
        A_eq.append(row)
        b_eq.append(L[t] - G[t])

    # SOC 递推：s_t - eta_c*c_t + r_t/eta_r - s_{t-1} = 0（s_0 = S0 为常数移项）
    for t in range(T):
        row = np.zeros(n)
        row[4 * T + t] = 1.0            # s_t
        row[T + t] = -ETA_C             # -eta_c*c_t
        row[2 * T + t] = 1.0 / ETA_R    # +r_t/eta_r
        if t > 0:
            row[4 * T + t - 1] = -1.0   # -s_{t-1}
        A_eq.append(row)
        b_eq.append((S0 if t == 0 else 0.0) + soc_rhs_injection[t])

    # 硬周期边界：s_T = S0
    row = np.zeros(n)
    row[4 * T + T - 1] = 1.0
    A_eq.append(row)
    b_eq.append(S0)

    bounds = (
        [(0.0, None)] * T +                       # x
        [(0.0, P_MAX_KWH)] * T +                  # c
        [(0.0, P_MAX_KWH)] * T +                  # r
        [(0.0, float(G[t])) for t in range(T)] +  # w <= G_t
        [(S_MIN, S_MAX)] * T                      # s
    )

    return economic_obj, np.asarray(A_eq), np.asarray(b_eq), bounds


def _solve_economic(pi, L, G, soc_rhs_injection=None):
    """求解只含真实购电费用的第一阶段 LP。"""
    obj, A_eq, b_eq, bounds = _build_lp(pi, L, G, soc_rhs_injection)
    res = linprog(obj, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(f"经济 LP 求解失败: status={res.status}, message={res.message}")
    return res, obj, A_eq, b_eq, bounds


def build_and_solve(pi, L, G, cost_tol=COST_TOL):
    """先最小化真实购电费，再在近似等费用解中最小化储能吞吐量。

    变量排序：x(0:T), c(T:2T), r(2T:3T), w(3T:4T), s(4T:5T)。
    影子价格来自第一阶段经济 LP，调度结果来自第二阶段稳定化 LP。
    """
    economic, economic_obj, A_eq, b_eq, bounds = _solve_economic(pi, L, G)
    c1_star = float(economic.fun)

    throughput_obj = np.concatenate([
        np.zeros(T), np.ones(T), np.ones(T), np.zeros(2 * T)
    ])
    stable = linprog(
        throughput_obj,
        A_ub=economic_obj.reshape(1, -1),
        b_ub=np.array([c1_star + cost_tol]),
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    if not stable.success:
        raise RuntimeError(f"二级最小吞吐 LP 求解失败: status={stable.status}, message={stable.message}")

    sol = {
        "x": stable.x[0:T], "c": stable.x[T:2 * T], "r": stable.x[2 * T:3 * T],
        "w": stable.x[3 * T:4 * T], "s": stable.x[4 * T:5 * T],
        "C1_star": c1_star,
        "C1": float(pi @ stable.x[0:T]),
        "cost_tol": float(cost_tol),
        "throughput_objective_kwh": float(stable.fun),
        "mu_bal": np.array(economic.eqlin.marginals[0:T]),
        "mu_soc": np.array(economic.eqlin.marginals[T:2 * T]),
    }
    return sol


def perturbation_check(pi, L, G, sol):
    """数值扰动核验对偶符号约定：
    1) 某时段负荷 RHS 增加 delta，有限差分应等于平衡约束对偶；
    2) 单个 SOC 递推 RHS 增加 delta，有限差分应等于该 SOC 约束对偶。
    对偶和有限差分均针对第一阶段纯购电费用 LP。"""
    t_probe = 100  # 代表时段
    delta = 1e-3
    base, *_ = _solve_economic(pi, L, G)

    L2 = L.copy()
    L2[t_probe] += delta
    load_perturbed, *_ = _solve_economic(pi, L2, G)
    fd_bal = float((load_perturbed.fun - base.fun) / delta)

    injection = np.zeros(T)
    injection[t_probe] = delta
    soc_perturbed, *_ = _solve_economic(pi, L, G, soc_rhs_injection=injection)
    fd_soc = float((soc_perturbed.fun - base.fun) / delta)

    dual_bal = float(sol["mu_bal"][t_probe])
    dual_soc = float(sol["mu_soc"][t_probe])
    return {
        "t_probe_zero_based": t_probe,
        "delta_kwh": delta,
        "balance_dual_yuan_per_kwh": dual_bal,
        "balance_finite_difference_yuan_per_kwh": fd_bal,
        "balance_abs_error": abs(fd_bal - dual_bal),
        "soc_dual_yuan_per_kwh": dual_soc,
        "soc_finite_difference_yuan_per_kwh": fd_soc,
        "soc_abs_error": abs(fd_soc - dual_soc),
        "storage_marginal_value_yuan_per_kwh": -dual_soc,
    }


def validate(sol, L, G):
    """校验层一：平衡残差、SOC 递推残差、边界检查。"""
    x, c, r, w, s = sol["x"], sol["c"], sol["r"], sol["w"], sol["s"]
    bal = x + (G - w) + r - L - c
    s_prev = np.concatenate([[S0], s[:-1]])
    soc_res = s - s_prev - ETA_C * c + r / ETA_R
    checks = {
        "max_abs_balance_residual_kwh": float(np.abs(bal).max()),
        "max_abs_soc_recursion_residual_kwh": float(np.abs(soc_res).max()),
        "soc_min": float(s.min()), "soc_max": float(s.max()),
        "soc_within_bounds": bool(s.min() >= S_MIN - 1e-6 and s.max() <= S_MAX + 1e-6),
        "s0_equals_sT": bool(abs(s[-1] - S0) < 1e-6),
        "max_charge_kwh": float(c.max()), "max_discharge_kwh": float(r.max()),
        "charge_discharge_within_power_limit": bool(
            c.max() <= P_MAX_KWH + 1e-6 and r.max() <= P_MAX_KWH + 1e-6),
        "curtailment_nonnegative_and_le_pv": bool(
            w.min() >= -1e-9 and np.all(w <= G + 1e-6)),
        "simultaneous_charge_discharge_max_product": float((c * r).max()),
        "purchase_cost_optimality_gap_yuan": float(sol["C1"] - sol["C1_star"]),
        "purchase_cost_within_secondary_tolerance": bool(
            sol["C1"] <= sol["C1_star"] + sol["cost_tol"] + 1e-7),
    }
    return checks


def _interval_label(t):
    """内部结束时刻口径：t=0 对应 0:00-0:10，t=143 对应 23:50-24:00。"""
    def fmt(minute):
        if minute == 24 * 60:
            return "24:00"
        return f"{minute // 60}:{minute % 60:02d}"
    return f"{fmt(10 * t)}-{fmt(10 * (t + 1))}"


def export_result1(sol, df):
    """按模板逐行映射填充 result1.xlsx（不修改模板表头）。
    映射：内部时段序号 t（1..144，与附件1第 t 行同序）-> 模板“计划购电量”第 t 行。
    专项核对：模板 144 行全部填满；填充总量与逐时段求和一致。"""
    out = RESULTS / "result1.xlsx"
    if not TEMPLATE_XLSX.is_file():
        raise FileNotFoundError(f"找不到结果模板: {TEMPLATE_XLSX}")
    shutil.copy(TEMPLATE_XLSX, out)

    import openpyxl
    wb = openpyxl.load_workbook(out)
    required_sheets = {"计划购电量", "充放电量"}
    if not required_sheets.issubset(wb.sheetnames):
        raise ValueError(f"result1模板缺少工作表: {sorted(required_sheets - set(wb.sheetnames))}")
    ws = wb["计划购电量"]
    if ws.max_row - 1 != T:
        raise ValueError(f"模板应有 {T} 行数据，实际 {ws.max_row - 1}")
    mapping_rows = []
    for t in range(T):
        ws.cell(row=t + 2, column=2, value=float(sol["x"][t]))
        mapping_rows.append({
            "t_one_based": t + 1,
            "source_time_label": str(df.iloc[t]["time_label"]),
            "internal_interval_end_label_convention": _interval_label(t),
            "official_template_label": str(ws.cell(row=t + 2, column=1).value),
            "template_row": t + 2,
        })
    filled = sum(ws.cell(row=t + 2, column=2).value for t in range(T))
    if abs(filled - sol["x"].sum()) >= 1e-6:
        raise RuntimeError("模板填充总量与逐时段求和不一致")

    ws2 = wb["充放电量"]
    for blk in range(6):  # 六个 4 h 区间 = 24 个时段
        lo, hi = blk * 24, (blk + 1) * 24
        ws2.cell(row=blk + 2, column=2, value=float(sol["c"][lo:hi].sum()))
        ws2.cell(row=blk + 2, column=3, value=float(sol["r"][lo:hi].sum()))
    ws2.cell(row=2, column=5, value=S0)                 # 0:00 储电量
    ws2.cell(row=3, column=5, value=float(sol["s"][-1]))  # 24:00 储电量
    wb.save(out)
    mapping = pd.DataFrame(mapping_rows)
    mapping_path = RESULTS / "q1_time_mapping.csv"
    mapping.to_csv(mapping_path, index=False, encoding="utf-8-sig")
    mismatch_count = int((mapping["internal_interval_end_label_convention"]
                          != mapping["official_template_label"]).sum())
    return out, mapping_path, mismatch_count


def main():
    df, pi, L, G = load_data()
    print(f"数据: T={T}, 电价[{pi.min():.4f},{pi.max():.4f}] 元/kWh, "
          f"负荷日均功率 {L.sum()/24:.1f} kW, 光伏峰值 {G.max()/DT:.1f} kW, "
          f"光伏日发电量 {G.sum():.1f} kWh, 负荷日用电量 {L.sum():.1f} kWh")

    sol = build_and_solve(pi, L, G)
    checks = validate(sol, L, G)
    pert = perturbation_check(pi, L, G, sol)
    out, mapping_path, mapping_mismatches = export_result1(sol, df)
    baseline_purchase = np.maximum(L - G, 0.0)
    baseline_cost = float(pi @ baseline_purchase)
    saving = baseline_cost - sol["C1"]
    saving_rate = saving / baseline_cost if baseline_cost > 0 else np.nan

    # 逐时段结果存档（论文数值可溯源）
    detail = pd.DataFrame({
        "time_label": df["time_label"], "price": pi,
        "L_kwh": L, "G_kwh": G,
        "x_plan_kwh": sol["x"], "c_charge_kwh": sol["c"],
        "r_discharge_kwh": sol["r"], "w_curtail_kwh": sol["w"],
        "soc_kwh": sol["s"], "mu_bal": sol["mu_bal"], "mu_soc": sol["mu_soc"],
    })
    detail.to_csv(RESULTS / "q1_timeseries.csv", index=False, encoding="utf-8-sig")

    summary = {
        "C1_true_purchase_cost_yuan": sol["C1"],
        "C1_stage1_optimal_cost_yuan": sol["C1_star"],
        "C1_secondary_solution_cost_yuan": sol["C1"],
        "secondary_cost_tolerance_yuan": sol["cost_tol"],
        "total_purchase_kwh": float(sol["x"].sum()),
        "total_curtailment_kwh": float(sol["w"].sum()),
        "storage_throughput_kwh": float(sol["c"].sum() + sol["r"].sum()),
        "charge_kwh": float(sol["c"].sum()), "discharge_kwh": float(sol["r"].sum()),
        "no_storage_baseline_cost_yuan": baseline_cost,
        "saving_vs_no_storage_yuan": saving,
        "saving_rate_vs_no_storage": saving_rate,
        "no_storage_baseline_definition": "sum_t price_t * max(load_t - pv_t, 0)",
        "time_mapping_mismatch_count_vs_official_template": mapping_mismatches,
        "time_mapping_note": (
            "内部按附件时间标签为时段结束时刻；官方模板标签整体后移10分钟，"
            "结果保持源数据顺序填充，详见q1_time_mapping.csv。"
        ),
        "validation": checks,
        "perturbation_check": pert,
        "mu_soc_stats": {"min": float(sol["mu_soc"].min()),
                          "max": float(sol["mu_soc"].max())},
        "mu_bal_stats": {"min": float(sol["mu_bal"].min()),
                          "max": float(sol["mu_bal"].max())},
    }
    with open(RESULTS / "q1_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\nC1 第一阶段最低购电费用 = {sol['C1_star']:.4f} 元; "
          f"二级稳定解购电费用 = {sol['C1']:.4f} 元")
    print(f"全天购电量 = {sol['x'].sum():.2f} kWh; "
          f"无储能基线 = {baseline_cost:.2f} 元; 节省率 = {saving_rate:.2%}")
    print(f"弃光 = {sol['w'].sum():.2f} kWh;  储能吞吐 = {summary['storage_throughput_kwh']:.2f} kWh")
    print(f"最大平衡残差 = {checks['max_abs_balance_residual_kwh']:.2e} kWh; "
          f"SOC ∈ [{checks['soc_min']:.1f}, {checks['soc_max']:.1f}]")
    print(f"同时充放最大乘积 = {checks['simultaneous_charge_discharge_max_product']:.2e}")
    print(f"扰动核验: t={pert['t_probe_zero_based']}，平衡对偶误差 "
          f"{pert['balance_abs_error']:.2e}，SOC 对偶误差 {pert['soc_abs_error']:.2e}")
    print(f"时间映射: 内部区间与官方模板标签不一致 {mapping_mismatches}/{T} 行，详见 {mapping_path}")
    print(f"已输出: {out}")


if __name__ == "__main__":
    sys.exit(main())
