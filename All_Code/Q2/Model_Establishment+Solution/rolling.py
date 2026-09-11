# -*- coding: utf-8 -*-
"""
P3 跨日滚动推进与调参（2026 数模 C 题 问题二）
================================================
实现依据：总纲第 4.2 节（滚动流程）、4.5 节（结算口径）、4.8 节注意事项。
流程：0:00 因果预测（缓存） -> 生成 M 场景（缓存） -> 单日两阶段 LP -> 当天真实数据结算
      -> 实际期末 SOC 传次日 -> 残差块入库（已预计算于场景模块）。

【关键约定】
- 2025-01-01（i=0）无历史预热日：不优化，SOC 保持 6000，残差不入库。
- 2025-01 整月（i=1..30）为预热期，只积累状态与残差，不进报告。
- 报告期 2025-02-01..12-31（i=31..364，共 334 天）。
- 调参窗口 2025-02-01..02-28（i=31..58，共 28 天）。
- 调参组合共用同一“预热期基准参数”滚动得到的 02-01 期初 SOC，控制变量。
"""
import os
import sys
import pickle
import time
import traceback
from datetime import datetime

import numpy as np
import pandas as pd

from optimizer import solve_day2
from settlement import settle_day
from scenarios import ScenarioEngine

# 路径常量（自包含）
GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q2CODE = os.path.join(GS, r"All_Code\Q2")
DATA_PROC = os.path.join(Q2CODE, "Data_processing")
TABLES = os.path.join(Q2CODE, "Results", "Tables")
MODEL_DIR = os.path.join(Q2CODE, "Model_Establishment+Solution")

T = 144
D = 365
ALPHA = 0.90
SEED = 20260101
SOC0 = 6000.0

BETA_CAND = [0.0, 0.25, 0.5, 0.75, 1.0]
M_CAND = [10, 20, 30]
K2_MULT = [0.25, 0.5, 1.0, 2.0]
RISK_BUDGET = 0.10   # beta 选取规则：调参窗口费用增幅不超过该预算，预算内最小化紧急购电率

# 预热基准参数（仅用于产生调参窗口的 02-01 期初 SOC）
BASE_PARAMS = {"beta": 0.5, "alpha": ALPHA}


def load_dataset():
    path = os.path.join(DATA_PROC, "q2_dataset.pkl")
    with open(path, "rb") as fh:
        return pickle.load(fh)


def load_forecasts():
    path = os.path.join(DATA_PROC, "forecasts.pkl")
    with open(path, "rb") as fh:
        return pickle.load(fh)


def get_scenarios(M, ds, fc):
    """按需加载/生成 M 场景缓存，复用避免重复计算。"""
    path = os.path.join(DATA_PROC, f"scenarios_M{M}.pkl")
    if os.path.exists(path):
        with open(path, "rb") as fh:
            cache = pickle.load(fh)
        return cache["L_all"], cache["G_all"]
    eng = ScenarioEngine(ds, fc, seed=SEED)
    L_all, G_all, _, _ = eng.generate_all(M)
    with open(path, "wb") as fh:
        pickle.dump({"M": M, "L_all": L_all, "G_all": G_all}, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"    已生成并缓存 M={M} 场景")
    return L_all, G_all


def run_roll(days, s0_start, params, L_all, G_all, ds, verbose=False, save_detail=False):
    """
    对给定日期索引列表逐日滚动。
    返回 (logs, final_s0)。logs 每条含经济量与评价量。
    """
    s0 = float(s0_start)
    logs = []
    full_extraction = bool(params.get("full_extraction", False))
    for idx, i in enumerate(days):
        s0_in = float(s0)
        price = ds["price"][:, i]
        plan = solve_day2(price, {"L": L_all[i], "G": G_all[i]}, s0_in, params)
        st = settle_day(price, plan["x"], plan["c"], plan["r"],
                        ds["load"][:, i], ds["pv"][:, i], s0_in,
                        full_extraction=full_extraction)
        s0 = float(st["s_actual"][T])
        entry = {
            "day_index": int(i),
            "date": str(ds["date_str"][i]),
            "s0": s0_in,
            "E_C": float(plan["E_C"]),
            "CVaR": float(plan["CVaR"]),
            "cost_plan": st["cost_plan"],
            "cost_emergency": st["cost_emergency"],
            "cost_total": st["cost_total"],
            "emergency_rate": st["emergency_rate"],
            "unextracted_ratio": st["unextracted_ratio"],
            "curtailment_rate": st["curtailment_rate"],
            "soc_violate_count": st["soc_violate_count"],
            "residual_blocks": int(max(0, i - 1)),
            "emergency_kwh": float(np.sum(st["e"])),
            "load_kwh": float(np.sum(ds["load"][:, i])),
            "curtail_kwh": float(np.sum(st["w"])),
            "unextracted_kwh": float(np.sum(plan["x"] - st["y"])),
            "final_soc": s0,
        }
        if save_detail:
            entry["plan_x"] = plan["x"].copy()
            entry["plan_c"] = plan["c"].copy()
            entry["plan_r"] = plan["r"].copy()
            entry["plan_s"] = plan["s"].copy()
            entry["settle_y"] = st["y"].copy()
            entry["settle_e"] = st["e"].copy()
            entry["settle_g"] = st["g"].copy()
            entry["settle_w"] = st["w"].copy()
            entry["settle_c_actual"] = st["c_actual"].copy()
            entry["settle_r_actual"] = st["r_actual"].copy()
            entry["settle_s_actual"] = st["s_actual"].copy()
            entry["price"] = price.copy()
            entry["load_actual"] = ds["load"][:, i].copy()
            entry["pv_actual"] = ds["pv"][:, i].copy()
        logs.append(entry)
        if verbose and (idx % 30 == 0 or idx == len(days) - 1):
            print(f"    {logs[-1]['date']} cost_total={st['cost_total']:.2f} "
                  f"emergency={st['cost_emergency']:.2f} final_soc={s0:.1f}")
    return logs, s0


def agg_cost(logs):
    return float(np.sum([l["cost_total"] for l in logs]))


def agg_emergency_rate(logs):
    ek = float(np.sum([l["emergency_kwh"] for l in logs]))
    lk = float(np.sum([l["load_kwh"] for l in logs]))
    return ek / lk if lk else 0.0


def run_tuning_and_formal():
    t_start = time.time()
    ds = load_dataset()
    fc = load_forecasts()
    kappa2_base = float(ds["kappa2_base"])

    # 场景缓存
    L20, G20 = get_scenarios(20, ds, fc)
    L10, G10 = get_scenarios(10, ds, fc)
    L30, G30 = get_scenarios(30, ds, fc)

    # 预热期（i=1..30），基准参数，得到调参窗口 02-01 期初 SOC
    warm_days = list(range(1, 31))
    print("[P3] 预热期滚动（2025-01-02..01-31，基准参数）")
    warm_params = dict(BASE_PARAMS)
    warm_params["kappa2"] = kappa2_base
    _, s0_0201 = run_roll(warm_days, SOC0, warm_params, L20, G20, ds)
    print(f"    02-01 期初 SOC（预热基准） = {s0_0201:.4f} kWh")

    tune_days = list(range(31, 59))   # 02-01..02-28 共 28 天

    # ---- 调参 1：beta（费用增幅预算内最小化紧急购电率，权衡费用与尾部风险）----
    print(f"[P3] 调参 beta ∈ {BETA_CAND}（固定 M=20, kappa2_base，费用增幅预算 {RISK_BUDGET*100:.0f}%）")
    beta_rows = []
    for b in BETA_CAND:
        params = {"beta": b, "alpha": ALPHA, "kappa2": kappa2_base}
        logs, _ = run_roll(tune_days, s0_0201, params, L20, G20, ds)
        beta_rows.append([b, agg_cost(logs), agg_emergency_rate(logs), len(tune_days)])
    beta_df = pd.DataFrame(beta_rows, columns=["beta", "tuning_cost_total", "tuning_emergency_rate", "n_days"])
    base_cost = float(beta_df.loc[beta_df["beta"] == 0.0, "tuning_cost_total"].iloc[0])
    beta_df["cost_increase"] = beta_df["tuning_cost_total"] / base_cost - 1.0
    cand = beta_df[beta_df["cost_increase"] <= RISK_BUDGET]
    beta_best = float(cand.loc[cand["tuning_emergency_rate"].idxmin(), "beta"])
    print(f"    选定 beta = {beta_best}（费用增幅 <= {RISK_BUDGET*100:.0f}% 的候选中紧急购电率最低）")

    # ---- 调参 2：M ----
    print("[P3] 调参 M ∈ {10,20,30}（固定 beta_best, kappa2_base）")
    scen_map = {10: (L10, G10), 20: (L20, G20), 30: (L30, G30)}
    m_rows = []
    for m in M_CAND:
        params = {"beta": beta_best, "alpha": ALPHA, "kappa2": kappa2_base}
        Lm, Gm = scen_map[m]
        logs, _ = run_roll(tune_days, s0_0201, params, Lm, Gm, ds)
        m_rows.append([m, agg_cost(logs), agg_emergency_rate(logs), len(tune_days)])
    m_df = pd.DataFrame(m_rows, columns=["M", "tuning_cost_total", "tuning_emergency_rate", "n_days"])
    m_best = int(m_df.loc[m_df["tuning_cost_total"].idxmin(), "M"])
    print(f"    选定 M = {m_best}")

    # ---- 调参 3：kappa2 ----
    print("[P3] 调参 kappa2 ∈ {0.25,0.5,1.0,2.0}*kappa2_base（固定 beta_best, M_best）")
    Lmb, Gmb = scen_map[m_best]
    k2_rows = []
    for mult in K2_MULT:
        params = {"beta": beta_best, "alpha": ALPHA, "kappa2": mult * kappa2_base}
        logs, _ = run_roll(tune_days, s0_0201, params, Lmb, Gmb, ds)
        k2_rows.append([mult, mult * kappa2_base, agg_cost(logs), agg_emergency_rate(logs), len(tune_days)])
    k2_df = pd.DataFrame(k2_rows, columns=["kappa2_mult", "kappa2", "tuning_cost_total", "tuning_emergency_rate", "n_days"])
    k2_best_mult = float(k2_df.loc[k2_df["tuning_cost_total"].idxmin(), "kappa2_mult"])
    kappa2_best = k2_best_mult * kappa2_base
    print(f"    选定 kappa2_mult = {k2_best_mult}，kappa2 = {kappa2_best:.6f}")

    final_params = {"beta": beta_best, "alpha": ALPHA, "kappa2": kappa2_best}

    # ---- 全量提取敏感性（总纲 4.1/4.8）----
    print("[P3] 全量提取敏感性（y=x，正式参数，调参窗口 28 天）")
    fe_params = dict(final_params)
    fe_params["full_extraction"] = True
    try:
        logs_fe, _ = run_roll(tune_days, s0_0201, fe_params, Lmb, Gmb, ds)
        fe_feasible = True
    except RuntimeError as exc:
        logs_fe = None
        fe_feasible = False
        print(f"    全量提取敏感性不可行（如实报告，不隐藏）: {exc}")
    base_tune_logs, _ = run_roll(tune_days, s0_0201, final_params, Lmb, Gmb, ds)  # 同参数基准
    if fe_feasible:
        fe_rows = [
            ["基准(y<=x)", agg_cost(base_tune_logs), agg_emergency_rate(base_tune_logs), len(tune_days), "可行"],
            ["全量提取(y=x)", agg_cost(logs_fe), agg_emergency_rate(logs_fe), len(tune_days), "可行"],
        ]
    else:
        fe_rows = [
            ["基准(y<=x)", agg_cost(base_tune_logs), agg_emergency_rate(base_tune_logs), len(tune_days), "可行"],
            ["全量提取(y=x)", np.nan, np.nan, len(tune_days), "不可行"],
        ]
    fe_df = pd.DataFrame(fe_rows, columns=["方案", "tuning_cost_total", "tuning_emergency_rate", "n_days", "feasible"])

    # ---- 正式运行：完整 334 天报告期（含预热期滚动）----
    print("[P3] 正式运行（2025-02-01..12-31，共 334 天）")
    full_days = list(range(1, D))
    logs_full, _ = run_roll(full_days, SOC0, final_params, Lmb, Gmb, ds, verbose=True, save_detail=True)
    report_logs = [l for l in logs_full if l["day_index"] >= 31]
    if len(report_logs) != 334:
        raise RuntimeError(f"报告期天数应为 334，实际 {len(report_logs)}")

    # ---- 保存调参灵敏度表 ----
    tune_path = os.path.join(TABLES, "tuning_sensitivity.xlsx")
    with pd.ExcelWriter(tune_path, engine="openpyxl") as writer:
        beta_df.assign(is_selected=lambda d: d["beta"] == beta_best).to_excel(writer, sheet_name="beta", index=False)
        m_df.assign(is_selected=lambda d: d["M"] == m_best).to_excel(writer, sheet_name="M", index=False)
        k2_df.assign(is_selected=lambda d: d["kappa2_mult"] == k2_best_mult).to_excel(writer, sheet_name="kappa2", index=False)
        fe_df.to_excel(writer, sheet_name="full_extraction", index=False)
    print(f"    调参灵敏度表已写入: {tune_path}")

    # ---- 保存逐日滚动日志（仅报告期，只含标量列）----
    scalar_cols = ["day_index", "date", "s0", "E_C", "CVaR", "cost_plan", "cost_emergency",
                   "cost_total", "emergency_rate", "unextracted_ratio", "curtailment_rate",
                   "soc_violate_count", "residual_blocks", "emergency_kwh", "load_kwh",
                   "curtail_kwh", "unextracted_kwh", "final_soc"]
    log_df = pd.DataFrame([{k: l[k] for k in scalar_cols} for l in report_logs])
    log_path = os.path.join(TABLES, "daily_rolling_log.csv")
    log_df.to_csv(log_path, index=False, encoding="utf-8-sig")
    print(f"    逐日滚动日志已写入: {log_path}")

    # ---- 缓存正式运行完整结果（供 P4/P5/P6）----
    results = {
        "params": final_params,
        "beta_best": beta_best,
        "m_best": m_best,
        "kappa2_best": kappa2_best,
        "kappa2_base": kappa2_base,
        "alpha": ALPHA,
        "s0_0201_tuning": float(s0_0201),
        "full_logs": logs_full,
        "report_logs": report_logs,
        "full_extraction": {
            "base_tune_logs": base_tune_logs,
            "full_tune_logs": logs_fe,
            "feasible": fe_feasible,
        },
        "tuning": {
            "beta": beta_df, "M": m_df, "kappa2": k2_df, "full_extraction": fe_df,
        },
    }
    res_path = os.path.join(DATA_PROC, "q2_rolling_results.pkl")
    with open(res_path, "wb") as fh:
        pickle.dump(results, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"    正式运行结果缓存已写入: {res_path}")

    elapsed = time.time() - t_start
    print(f"[P3] 完成，总耗时 {elapsed:.1f} 秒")
    print(f"    最终参数: beta={beta_best}, M={m_best}, kappa2={kappa2_best:.6f} (mult={k2_best_mult})")
    return results


def main() -> int:
    try:
        run_tuning_and_formal()
        return 0
    except Exception as exc:
        print("=" * 60)
        print("P3 rolling 执行失败：")
        traceback.print_exc()
        print(f"错误信息: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
