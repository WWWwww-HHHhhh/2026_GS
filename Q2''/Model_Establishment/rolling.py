# -*- coding: utf-8 -*-
"""Q2'' 滚动回测主流程：0:00 计划 -> 当日真实数据词典序结算 -> 次日 SOC 结转。"""
import os, pickle, time, sys
import numpy as np
import pandas as pd

GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q2P = os.path.join(GS, "Q2''")
DATA_PROC = os.path.join(Q2P, "Data_processing")
TABLES = os.path.join(Q2P, "Results", "Tables")
T, D = 144, 365

from optimizer import solve_day2
from settlement import settle_day
from scenarios import build_scenarios

FINAL = {"beta": 0.01, "alpha": 0.90, "kappa2": 0.531667, "window": 30, "M": 20}

def run_roll(days, s0_start, params, L_all, G_all, ds, save_detail=False, verbose=False):
    s0 = float(s0_start); logs = []
    for idx, i in enumerate(days):
        price = ds["price"][:, i]
        plan = solve_day2(price, {"L": L_all[i], "G": G_all[i]}, s0, params)
        st = settle_day(price, plan["x"], plan["c"], plan["r"], ds["load"][:, i], ds["pv"][:, i], s0)
        s0 = float(st["s_actual"][T])
        entry = {"day_index": int(i), "date": str(ds["date_str"][i]), "s0": float(plan["s"][0]),
                 "cost_plan": st["cost_plan"], "cost_emergency": st["cost_emergency"], "cost_total": st["cost_total"],
                 "emergency_rate": st["emergency_rate"], "unextracted_ratio": st["unextracted_ratio"],
                 "curtailment_rate": st["curtailment_rate"], "soc_violate_count": st["soc_violate_count"],
                 "emergency_kwh": float(np.sum(st["e"])), "load_kwh": float(np.sum(ds["load"][:, i])),
                 "curtail_kwh": float(np.sum(st["w"])), "unextracted_kwh": float(np.sum(plan["x"] - st["y"])),
                 "final_soc": s0, "dev_c": st["dev_c"], "dev_r": st["dev_r"]}
        if save_detail:
            entry["plan_x"] = plan["x"].copy(); entry["plan_c"] = plan["c"].copy(); entry["plan_r"] = plan["r"].copy(); entry["plan_s"] = plan["s"].copy()
            entry["settle_y"] = st["y"].copy(); entry["settle_e"] = st["e"].copy(); entry["settle_g"] = st["g"].copy(); entry["settle_w"] = st["w"].copy()
            entry["settle_c_actual"] = st["c_actual"].copy(); entry["settle_r_actual"] = st["r_actual"].copy(); entry["settle_s_actual"] = st["s_actual"].copy()
        logs.append(entry)
        if verbose and (idx % 30 == 0 or idx == len(days) - 1):
            print(f"  {entry['date']} cost={entry['cost_total']:.2f} emg={entry['cost_emergency']:.2f} soc={s0:.1f}", flush=True)
    return logs, s0

def main():
    os.makedirs(TABLES, exist_ok=True)
    ds = pickle.load(open(os.path.join(DATA_PROC, "q2_dataset.pkl"), "rb"))
    fc = pickle.load(open(os.path.join(DATA_PROC, "forecasts.pkl"), "rb"))
    L_all, G_all = build_scenarios(fc["Lhat"], fc["Ghat"], ds["load"], ds["pv"], window=FINAL["window"], M=FINAL["M"])
    t0 = time.time()
    logs_full, _ = run_roll(list(range(1, D)), 6000.0, FINAL, L_all, G_all, ds, save_detail=True, verbose=True)
    report = [l for l in logs_full if l["day_index"] >= 31]
    scalar_cols = ["day_index","date","s0","cost_plan","cost_emergency","cost_total","emergency_rate","unextracted_ratio","curtailment_rate","soc_violate_count","emergency_kwh","load_kwh","curtail_kwh","unextracted_kwh","final_soc","dev_c","dev_r"]
    pd.DataFrame([{k: l[k] for k in scalar_cols} for l in report]).to_csv(os.path.join(TABLES, "daily_rolling_log.csv"), index=False, encoding="utf-8-sig")
    res = {"params": FINAL, "full_logs": logs_full, "report_logs": report,
           "total_cost": float(sum(l["cost_total"] for l in report)),
           "plan_cost": float(sum(l["cost_plan"] for l in report)),
           "emergency_cost": float(sum(l["cost_emergency"] for l in report)),
           "emergency_rate": float(sum(l["emergency_kwh"] for l in report) / sum(l["load_kwh"] for l in report)),
           "curtailment_kwh": float(sum(l["curtail_kwh"] for l in report)),
           "unextracted_kwh": float(sum(l["unextracted_kwh"] for l in report))}
    pickle.dump(res, open(os.path.join(DATA_PROC, "q2_rolling_results.pkl"), "wb"), protocol=pickle.HIGHEST_PROTOCOL)
    print(f"DONE {time.time()-t0:.1f}s total={res['total_cost']:.2f} plan={res['plan_cost']:.2f} emg={res['emergency_cost']:.2f} emg_rate={res['emergency_rate']:.6f}", flush=True)

if __name__ == "__main__":
    main()
