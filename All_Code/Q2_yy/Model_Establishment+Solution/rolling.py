import os
import pickle
import time
import traceback
import numpy as np
import pandas as pd

from optimizer import solve_day2
from settlement import settle_day
from paths import Q2_DATA_PROCESSING as DATA_PROC, Q2_TABLES as TABLES

T = 144
D = 365
ALPHA = 0.90
SOC0 = 6000.0
BASELINE = {"M": 20, "beta": 0.25, "kappa_mult": 1.0}
BETA_CAND = [0.0, 0.01, 0.03, 0.05, 0.10, 0.20, 0.25, 0.50]
M_CAND = [10, 20, 30]
KAPPA_MULT_CAND = [0.25, 0.50, 1.0, 2.0]


def load_pickle(name):
    with open(os.path.join(str(DATA_PROC), name), "rb") as fh:
        return pickle.load(fh)


def load_scenarios(M):
    obj = load_pickle(f"scenarios_M{M}.pkl")
    return obj["L_all"], obj["G_all"]


def run_roll(days, s0_start, spec, scen_map, ds, save_detail=False, hard_terminal_day=None):
    L_all, G_all = scen_map[int(spec["M"])]
    params = {"alpha": ALPHA, "beta": float(spec["beta"]),
              "kappa2": float(ds["kappa2_base"]) * float(spec["kappa_mult"])}
    s0 = float(s0_start)
    logs = []
    for i in days:
        s0_in = s0
        price = ds["price"][:, i]
        day_params = dict(params)
        if hard_terminal_day is not None and i == int(hard_terminal_day):
            day_params.update({"hard_terminal": True, "s_ref": SOC0})
        try:
            plan = solve_day2(price, {"L": L_all[i], "G": G_all[i]}, s0_in, day_params)
        except Exception as exc:
            raise RuntimeError(f"{ds['date_str'][i]} 日前LP求解失败") from exc
        st = settle_day(price, plan["x"], plan["c"], plan["r"],
                        ds["load"][:, i], ds["pv"][:, i], s0_in)
        s0 = float(st["s_actual"][-1])
        entry = {
            "day_index": int(i), "date": str(ds["date_str"][i]), "s0": s0_in,
            "E_C": float(plan["E_C"]), "CVaR": float(plan["CVaR"]),
            "cost_plan": st["cost_plan"], "cost_emergency": st["cost_emergency"],
            "cost_total": st["cost_total"], "emergency_rate": st["emergency_rate"],
            "unextracted_ratio": st["unextracted_ratio"], "curtailment_rate": st["curtailment_rate"],
            "soc_violate_count": st["soc_violate_count"],
            "residual_blocks": int(min(30, max(0, i - 1))),
            "emergency_kwh": float(np.sum(st["e"])), "load_kwh": float(np.sum(ds["load"][:, i])),
            "curtail_kwh": float(np.sum(st["w"])), "unextracted_kwh": float(np.sum(plan["x"] - st["y"])),
            "spill_kwh": float(np.sum(st["spill"])),
            "final_soc": s0, "settlement_method": st["settlement_method"],
            "primary_emergency_cost": st["primary_emergency_cost"],
            "secondary_status": st["secondary_status"], "emergency_cost_gap": 0.0,
            "cost_tolerance": 0.0, "dev_c": st["dev_c"], "dev_r": st["dev_r"],
        }
        if save_detail:
            entry.update({
                "plan_x": plan["x"].copy(), "plan_c": plan["c"].copy(),
                "plan_r": plan["r"].copy(), "plan_s": plan["s"].copy(),
                "settle_y": st["y"].copy(), "settle_e": st["e"].copy(),
                "settle_g": st["g"].copy(), "settle_w": st["w"].copy(),
                "settle_spill": st["spill"].copy(),
                "settle_c_actual": st["c_actual"].copy(),
                "settle_r_actual": st["r_actual"].copy(),
                "settle_s_actual": st["s_actual"].copy(), "price": price.copy(),
                "load_actual": ds["load"][:, i].copy(), "pv_actual": ds["pv"][:, i].copy(),
            })
        logs.append(entry)
        if save_detail and (len(logs) % 30 == 0 or i == days.stop - 1 if isinstance(days, range) else False):
            print(f"report progress {ds['date_str'][i]} ({len(logs)} days)", flush=True)
    return logs, s0


def summarize(logs):
    return {
        "total_cost": float(sum(x["cost_total"] for x in logs)),
        "plan_cost": float(sum(x["cost_plan"] for x in logs)),
        "emergency_cost": float(sum(x["cost_emergency"] for x in logs)),
        "emergency_kwh": float(sum(x["emergency_kwh"] for x in logs)),
        "load_kwh": float(sum(x["load_kwh"] for x in logs)),
        "final_soc": float(logs[-1]["final_soc"]),
    }


def run_tuning_and_formal(tables_dir=None, results_path=None):
    started = time.time()
    tables_dir = os.path.abspath(tables_dir or str(TABLES))
    results_path = os.path.abspath(results_path or os.path.join(str(DATA_PROC), "q2_rolling_results.pkl"))
    os.makedirs(tables_dir, exist_ok=True)
    ds = load_pickle("q2_dataset.pkl")
    scen_map = {m: load_scenarios(m) for m in M_CAND}

    # 从题目明确给出的2025-01-01 0:00、SOC=6000开始连续滚动。
    # 预热参数预先约定，不使用验证期和报告期数据。
    warm_logs, s0_tune = run_roll(range(0, 14), SOC0, BASELINE, scen_map, ds)
    tune_days = list(range(14, 31))
    rows = []
    candidate_logs = {}
    for M in M_CAND:
        for beta in BETA_CAND:
            for km in KAPPA_MULT_CAND:
                spec = {"M": M, "beta": beta, "kappa_mult": km}
                logs, s_end = run_roll(tune_days, s0_tune, spec, scen_map, ds)
                z = summarize(logs)
                # 期末少留的电量按Q1边际价值补回，防止靠耗空储能虚假降费。
                terminal_adjustment = float(ds["kappa2_base"]) * max(0.0, s0_tune - s_end)
                score = z["total_cost"] + terminal_adjustment
                key = (M, beta, km)
                candidate_logs[key] = logs
                rows.append([M, beta, km, z["total_cost"], z["emergency_cost"],
                             z["emergency_kwh"], s_end, terminal_adjustment, score, len(tune_days)])
    tune_df = pd.DataFrame(rows, columns=["M", "beta", "kappa_mult", "validation_total_cost",
        "validation_emergency_cost", "validation_emergency_kwh", "validation_final_soc",
        "terminal_value_adjustment", "selection_score", "n_validation_days"])

    base_row = tune_df[(tune_df.M == BASELINE["M"]) &
                       (tune_df.beta == BASELINE["beta"]) &
                       (tune_df.kappa_mult == BASELINE["kappa_mult"])].iloc[0]
    # 双目标、无拍脑袋阈值：紧急费不高于原模型的候选中，选择调整后总成本最低者。
    eligible = tune_df[tune_df.validation_emergency_cost <= base_row.validation_emergency_cost + 1e-7]
    best_row = eligible.loc[eligible.selection_score.idxmin()]
    selected = {"M": int(best_row.M), "beta": float(best_row.beta),
                "kappa_mult": float(best_row.kappa_mult)}
    print("history-only selected", selected, flush=True)
    tune_df["is_selected"] = ((tune_df.M == selected["M"]) &
                              (tune_df.beta == selected["beta"]) &
                              (tune_df.kappa_mult == selected["kappa_mult"]))
    tune_df.to_excel(os.path.join(tables_dir, "tuning_sensitivity.xlsx"), index=False)

    # 参数在1月31日封存；报告期不再参与选择。保持真实的预热/验证状态继续滚动。
    tune_logs = candidate_logs[(selected["M"], selected["beta"], selected["kappa_mult"])]
    s0_report = float(tune_logs[-1]["final_soc"])
    # 仅在最后一个报告日施加年末SOC=6000硬约束，避免靠耗空期初储能压低全年费用。
    report_logs, _ = run_roll(range(31, D), s0_report, selected, scen_map, ds,
                              save_detail=True, hard_terminal_day=D-1)
    full_logs = warm_logs + tune_logs + report_logs

    scalar_cols = [k for k, v in report_logs[0].items() if not isinstance(v, np.ndarray)]
    pd.DataFrame([{k: x[k] for k in scalar_cols} for x in report_logs]).to_csv(
        os.path.join(tables_dir, "daily_rolling_log.csv"), index=False, encoding="utf-8-sig")
    results = {
        "params": {"alpha": ALPHA, "beta": selected["beta"],
                   "kappa2": selected["kappa_mult"] * float(ds["kappa2_base"])},
        "beta_best": selected["beta"], "m_best": selected["M"],
        "kappa2_best": selected["kappa_mult"] * float(ds["kappa2_base"]),
        "kappa2_base": float(ds["kappa2_base"]), "alpha": ALPHA,
        "selection_period": "2025-01-15..2025-01-31",
        "report_period": "2025-02-01..2025-12-31",
        "state_origin": "2025-01-01 00:00 SOC=6000 kWh",
        "terminal_constraint": "2025-12-31 24:00 SOC=6000 kWh (hard)",
        "full_logs": full_logs, "report_logs": report_logs,
        "tuning": {"joint": tune_df},
    }
    with open(results_path, "wb") as fh:
        pickle.dump(results, fh, protocol=pickle.HIGHEST_PROTOCOL)
    z = summarize(report_logs)
    print("selected", selected)
    print("report", z)
    print(f"elapsed={time.time()-started:.1f}s")
    return results


def main():
    try:
        run_tuning_and_formal()
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
