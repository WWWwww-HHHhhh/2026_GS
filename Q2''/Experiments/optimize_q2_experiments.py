# -*- coding: utf-8 -*-
"""
问题二 优化实验脚本（不修改原 Q2 代码，仅在本仓库根目录做对照实验）
结算口径: 词典序 settle_day（先最小化紧急购电费，再最大化计划充放电执行量）
"""
import os, sys, time, pickle, json
import numpy as np

GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
BASE = os.path.join(GS, "All_Code", "Q2")
sys.path.insert(0, os.path.join(BASE, "Model_Establishment+Solution"))
from rolling import load_dataset, load_forecasts, get_scenarios
from optimizer import solve_day2
from settlement import settle_day

DS = load_dataset()
FC = load_forecasts()
FULL_DAYS = list(range(1, 365))

def agg(logs, report_only=True):
    if report_only:
        logs = [l for l in logs if l["day_index"] >= 31]
    cost = sum(l["cost_total"] for l in logs)
    plan = sum(l["cost_plan"] for l in logs)
    emg_cost = sum(l["cost_emergency"] for l in logs)
    ek = sum(l["emergency_kwh"] for l in logs)
    lk = sum(l["load_kwh"] for l in logs)
    cur = sum(l["curtail_kwh"] for l in logs)
    une = sum(l["unextracted_kwh"] for l in logs)
    return {"cost": cost, "plan": plan, "emg_cost": emg_cost,
            "emg_rate": ek / lk if lk else 0.0, "emg_kwh": ek,
            "cur_kwh": cur, "une_kwh": une, "n_days": len(logs)}

def run_config(beta, M, kappa2, s0=6000.0, L_all=None, G_all=None, verbose=True):
    L_all, G_all = L_all if L_all is not None else get_scenarios(M, DS, FC)[0], \
                   G_all if G_all is not None else get_scenarios(M, DS, FC)[1]
    t0 = time.time()
    logs = []
    s = float(s0)
    for i in FULL_DAYS:
        price = DS["price"][:, i]
        plan = solve_day2(price, {"L": L_all[i], "G": G_all[i]}, s,
                          {"beta": beta, "alpha": 0.90, "kappa2": kappa2})
        st = settle_day(price, plan["x"], plan["c"], plan["r"],
                        DS["load"][:, i], DS["pv"][:, i], s)
        s = float(st["s_actual"][144])
        logs.append({"day_index": i, "cost_plan": st["cost_plan"],
                     "cost_emergency": st["cost_emergency"], "cost_total": st["cost_total"],
                     "emergency_kwh": float(np.sum(st["e"])),
                     "load_kwh": float(np.sum(DS["load"][:, i])),
                     "curtail_kwh": float(np.sum(st["w"])),
                     "unextracted_kwh": float(np.sum(plan["x"] - st["y"]))})
    a = agg(logs)
    a.update({"beta": beta, "M": M, "kappa2": kappa2, "dt": round(time.time() - t0, 1)})
    if verbose:
        print(json.dumps(a, ensure_ascii=False), flush=True)
    return a, logs

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "beta_fine"
    out_path = os.path.join(GS, f"_opt_{which}.json")

    if which == "beta_fine":
        results = []
        for beta in [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]:
            a, _ = run_config(beta, 20, 0.132917)
            results.append(a)
        json.dump(results, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    elif which == "M_sweep":
        results = []
        for M in [10, 20, 30, 40, 50]:
            a, _ = run_config(0.05, M, 0.132917)
            results.append(a)
        json.dump(results, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    elif which == "kappa_sweep":
        results = []
        for k in [0.0, 0.132917, 0.265833, 0.531667, 1.063333]:
            a, _ = run_config(0.05, 20, k)
            results.append(a)
        json.dump(results, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("DONE", which)
