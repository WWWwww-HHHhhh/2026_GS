from __future__ import annotations

import argparse
import pickle
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

WYH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WYH / "Data_processing"))
sys.path.insert(0, str(WYH / "Model_Establishment+Solution"))
from q4_common import D, OUT_DATA, T, TABLES, load_dataset  # noqa: E402
from q4_core import solve_day  # noqa: E402
from q4_settlement import settle_day  # noqa: E402

ALPHA = 0.90
SOC0 = 6000.0
BASELINE = {"M": 20, "beta": 0.25, "kappa_mult": 1.0}
BETA_CAND = [0.0, 0.01, 0.03, 0.05, 0.10, 0.20, 0.25, 0.50]
M_CAND = [10, 20, 30]
KAPPA_MULT_CAND = [0.25, 0.50, 1.0, 2.0]
WARM_DAYS = range(0, 14)
TUNE_DAYS = list(range(14, 31))
REPORT_DAYS = list(range(31, D))


def load_scenarios(M: int) -> dict:
    p = OUT_DATA / f"scenarios_M{M}.pkl"
    if not p.exists():
        raise FileNotFoundError(f"缺少场景缓存 {p}，请先运行 05_q4_scenarios.py --M {M}")
    with open(p, "rb") as fh:
        return pickle.load(fh)


def run_roll(days, s0_start, spec, scen_map, ds, save_detail=False, hard_terminal_day=None, tag=""):
    L_all = scen_map[spec["M"]]["L_all"]
    G_all = scen_map[spec["M"]]["G_all"]
    P_all = scen_map[spec["M"]]["P_all"]
    params = {"alpha": ALPHA, "beta": float(spec["beta"]),
              "kappa2": float(ds["kappa2_base"]) * float(spec["kappa_mult"])}
    s0 = float(s0_start)
    logs = []
    days = list(days)
    for n, i in enumerate(days):
        s0_in = s0
        price_real = ds["price"][:, i]
        day_params = dict(params)
        if hard_terminal_day is not None and i == int(hard_terminal_day):
            day_params.update({"hard_terminal": True, "s_ref": SOC0})
        try:
            plan = solve_day(P_all[i], L_all[i], G_all[i], s0_in, day_params)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"{ds['date_str'][i]} 日前 LP 求解失败") from exc
        st = settle_day(price_real, plan["x"], plan["c"], plan["r"],
                        ds["load"][:, i], ds["pv"][:, i], s0_in)
        s0 = float(st["s_actual"][-1])

        entry = {
            "day_index": int(i), "date": str(ds["date_str"][i]), "s0": s0_in,
            "E_C": float(plan["E_C"]), "CVaR": float(plan["CVaR"]),
            "cost_plan": st["cost_plan"], "cost_emergency": st["cost_emergency"],
            "cost_total": st["cost_total"],
            "emergency_rate": st["emergency_rate"],
            "unextracted_ratio": st["unextracted_ratio"],
            "curtailment_rate": st["curtailment_rate"],
            "soc_violate_count": st["soc_violate_count"],
            "residual_blocks": int(min(30, max(0, i - 1))),
            "emergency_kwh": float(np.sum(st["e"])),
            "load_kwh": float(np.sum(ds["load"][:, i])),
            "pv_kwh": float(np.sum(ds["pv"][:, i])),
            "pv_used_kwh": float(np.sum(st["g"])),
            "curtail_kwh": float(np.sum(st["w"])),
            "unextracted_kwh": float(np.sum(plan["x"] - st["y"])),
            "spill_kwh": float(np.sum(st["spill"])),
            "plan_total_kwh": float(np.sum(plan["x"])),
            "charge_kwh": float(np.sum(plan["c"])), "discharge_kwh": float(np.sum(plan["r"])),
            "final_soc": s0,
            "price_mean": float(np.mean(price_real)),
            "price_hat_mean": float(np.mean(P_all[i].mean(axis=0))),
            "eq_residual": float(plan["eq_residual"]), "ub_violation": float(plan["ub_violation"]),
            "settlement_method": st["settlement_method"],
        }
        if save_detail:
            entry.update({
                "plan_x": plan["x"].copy(), "plan_c": plan["c"].copy(),
                "plan_r": plan["r"].copy(), "plan_s": plan["s"].copy(),
                "settle_y": st["y"].copy(), "settle_e": st["e"].copy(),
                "settle_g": st["g"].copy(), "settle_w": st["w"].copy(),
                "settle_spill": st["spill"].copy(),
                "settle_s_actual": st["s_actual"].copy(),
                "price": price_real.copy(),
                "load_actual": ds["load"][:, i].copy(), "pv_actual": ds["pv"][:, i].copy(),
                "price_scen": P_all[i].copy(),
                "load_scen": L_all[i].copy(), "pv_scen": G_all[i].copy(),
            })
        logs.append(entry)
        if n and n % 25 == 0:
            print(f"    {tag} {ds['date_str'][i]} ({n}/{len(days)}) 累计费用 "
                  f"{sum(x['cost_total'] for x in logs):,.0f} 元", flush=True)
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


def run_smoke(ds, scen_map):
    print("[冒烟] 仅检查链路：报告期前 3 天 + 调参 2 天")
    logs, s_end = run_roll(WARM_DAYS, SOC0, BASELINE, scen_map, ds, tag="smoke-warm")
    print(f"  预热后 SOC = {s_end:.2f} kWh，费用 {sum(x['cost_total'] for x in logs):,.0f} 元")
    tlogs, s_t = run_roll(TUNE_DAYS[:2], s_end, BASELINE, scen_map, ds, tag="smoke-tune")
    print(f"  调参样本 2 天，费用 {sum(x['cost_total'] for x in tlogs):,.0f} 元，SOC={s_t:.2f}")
    rlogs, s_r = run_roll(REPORT_DAYS[:3], s_t, BASELINE, scen_map, ds, save_detail=True, tag="smoke-report")
    print(f"  报告期样本 3 天，费用 {sum(x['cost_total'] for x in rlogs):,.0f} 元，SOC={s_r:.2f}")
    for r in rlogs:
        print(f"    {r['date']}  x={r['plan_total_kwh']:9.2f} kWh  y={r['plan_total_kwh'] - r['unextracted_kwh']:9.2f}  "
              f"紧急={r['emergency_kwh']:8.2f}  SOSC={r['final_soc']:9.2f}  "
              f"计划费={r['cost_plan']:11.2f} 紧急费={r['cost_emergency']:10.2f}")
    print("[冒烟] 通过")
    return 0


def run_full(ds, scen_map):
    started = time.time()
    print("[1/4] 预热 2025-01-01~01-14（基准配置）")
    warm_logs, s0_tune = run_roll(WARM_DAYS, SOC0, BASELINE, scen_map, ds, tag="warm")
    print(f"    预热完成，SOC={s0_tune:.2f}")

    print("[2/4] 仅历史调参 2025-01-15~01-31")
    rows, cand_logs = [], {}
    for M in M_CAND:
        if M not in scen_map:
            print(f"    跳过 M={M}（无场景缓存）")
            continue
        for beta in BETA_CAND:
            for km in KAPPA_MULT_CAND:
                spec = {"M": M, "beta": beta, "kappa_mult": km}
                logs, s_end = run_roll(TUNE_DAYS, s0_tune, spec, scen_map, ds)
                z = summarize(logs)
                adj = float(ds["kappa2_base"]) * max(0.0, s0_tune - s_end)
                cand_logs[(M, beta, km)] = logs
                rows.append([M, beta, km, z["total_cost"], z["emergency_cost"], z["emergency_kwh"],
                             s_end, adj, z["total_cost"] + adj, len(TUNE_DAYS)])
                print(f"    M={M:2d} β={beta:<5} κ×{km:<5} 费用={z['total_cost']:14,.0f} "
                      f"紧急费={z['emergency_cost']:12,.0f} SOC_end={s_end:8.2f}", flush=True)
    tune_df = pd.DataFrame(rows, columns=[
        "M", "beta", "kappa_mult", "validation_total_cost", "validation_emergency_cost",
        "validation_emergency_kwh", "validation_final_soc", "terminal_value_adjustment",
        "selection_score", "n_validation_days"])

    base = tune_df[(tune_df.M == BASELINE["M"]) & (tune_df.beta == BASELINE["beta"]) &
                   (tune_df.kappa_mult == BASELINE["kappa_mult"])]
    if len(base) == 0:
        base = tune_df[tune_df.M == tune_df.M.min()]
    base_row = base.iloc[0]
    eligible = tune_df[tune_df.validation_emergency_cost <= base_row.validation_emergency_cost + 1e-7]
    best = eligible.loc[eligible.selection_score.idxmin()]
    selected = {"M": int(best.M), "beta": float(best.beta), "kappa_mult": float(best.kappa_mult)}
    print(f"    选中参数（仅用历史期）：{selected}")
    tune_df["is_selected"] = ((tune_df.M == selected["M"]) & (tune_df.beta == selected["beta"]) &
                              (tune_df.kappa_mult == selected["kappa_mult"]))
    TABLES.mkdir(parents=True, exist_ok=True)
    tune_df.to_excel(TABLES / "q4_2_tuning_sensitivity.xlsx", index=False)

    print("[3/4] 报告期 2025-02-01~12-31（参数已封存，硬终端仅最后一天）")
    tune_logs = cand_logs[(selected["M"], selected["beta"], selected["kappa_mult"])]
    s0_report = float(tune_logs[-1]["final_soc"])
    report_logs, _ = run_roll(REPORT_DAYS, s0_report, selected, scen_map, ds,
                              save_detail=True, hard_terminal_day=D - 1, tag="report")

    print("[4/4] 落盘")
    scalar_cols = [k for k, v in report_logs[0].items() if not isinstance(v, np.ndarray)]
    pd.DataFrame([{k: r[k] for k in scalar_cols} for r in report_logs]).to_csv(
        TABLES / "q4_2_daily_rolling_log.csv", index=False, encoding="utf-8-sig")
    results = {
        "problem": "Q4-2（波动电价下重新计算问题2）",
        "params": {"alpha": ALPHA, "beta": selected["beta"],
                   "kappa2": selected["kappa_mult"] * float(ds["kappa2_base"]),
                   "M": selected["M"]},
        "kappa2_base": float(ds["kappa2_base"]),
        "selection_period": "2025-01-15..2025-01-31",
        "report_period": "2025-02-01..2025-12-31",
        "state_origin": "2025-01-01 00:00 SOC=6000 kWh",
        "terminal_constraint": "2025-12-31 24:00 SOC=6000 kWh (hard)",
        "baseline_config_for_eligibility": BASELINE,
        "full_logs": warm_logs + tune_logs + report_logs,
        "report_logs": report_logs,
        "tuning": tune_df,
        "elapsed_sec": float(time.time() - started),
    }
    with open(OUT_DATA / "q4_2_rolling_results.pkl", "wb") as fh:
        pickle.dump(results, fh, protocol=pickle.HIGHEST_PROTOCOL)
    z = summarize(report_logs)
    print(f"    报告期汇总：总费用 {z['total_cost']:,.2f} 元（计划 {z['plan_cost']:,.2f} + "
          f"紧急 {z['emergency_cost']:,.2f}）；紧急购电 {z['emergency_kwh']:,.2f} kWh；"
          f"期末 SOC {z['final_soc']:.2f}")
    print(f"    耗时 {results['elapsed_sec']:.1f}s；结果缓存 {OUT_DATA / 'q4_2_rolling_results.pkl'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    ap.add_argument("--M", type=int, default=20, help="smoke 模式使用的场景数")
    args = ap.parse_args()
    try:
        ds = load_dataset()
        scen_map = {args.M: load_scenarios(args.M)} if args.mode == "smoke" else \
            {m: load_scenarios(m) for m in M_CAND if (OUT_DATA / f"scenarios_M{m}.pkl").exists()}
        if args.mode == "smoke":
            return run_smoke(ds, scen_map)
        return run_full(ds, scen_map)
    except Exception as exc:  # noqa: BLE001
        print("=" * 70)
        traceback.print_exc()
        print(f"[rolling] 失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
