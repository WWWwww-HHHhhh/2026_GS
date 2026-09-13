# -*- coding: utf-8 -*-
"""q4_2_variants.py —— 方案 C 的双口径变体驱动（新增文件，不修改既有滚动脚本）。

用途：在**完全相同的物理约束与结算规则**下，只切换两个口径维度，量化"题面歧义"的影响：
  维度 1 价格信息假设  --price-mode unknown | known
      unknown：电价在 0:00 未知，用因果预测 + 逐场景价格（Q4_wyh 主口径）
      known  ：电价在 0:00 已知（Q4_ZJY 口径），把当日实际电价复制到全部 M 个场景
  维度 2 光伏预报来源  --pv-source q2 | official
      q2      ：Q2_yy 自建因果预测（WAPE 0.066596），Q4_wyh 原主口径
      official：附件3 issue=0 + linear_endpoint（WAPE 0.083019），与 Q4_ZJY 同源

选择规则 --select legacy | risk_aware：
  legacy     ：沿用 Q2 协议（先剔除紧急购电费高于基准配置者，再取"验证期总费用+终端调整"最低）
  risk_aware ：目标函数含 CVaR，则选参规则也必须含风险项 ——
               在"验证期总费用 ≤ 最小值×1.01 且紧急购电费不高于基准配置"的候选里，
               取**验证期日费用 CVaR90 最低**者（并列时取总费用更低者）。
               容差 1% 是显式写死的，不随数据调整。

另有 --import-cap-kw：R-1 联络线容量敏感性（默认不设限，因为题目未给该约束）。

运行示例：
  python q4_2_variants.py --pv-source official --price-mode unknown --select risk_aware --tag V_official_unknown
输出：
  Data_processing/variants/<tag>_results.pkl
  Results/Tables/<tag>_tuning.xlsx、<tag>_daily.csv、<tag>_summary.csv
"""
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
WARM_DAYS = list(range(0, 14))
TUNE_DAYS = list(range(14, 31))
REPORT_DAYS = list(range(31, D))
COST_TOL = 0.01          # risk_aware：允许的最大费用让步（相对最优候选）


def scen_path(pv_source: str, M: int) -> Path:
    p = OUT_DATA / f"scenarios_M{M}_{pv_source}.pkl"
    if not p.exists():
        raise FileNotFoundError(f"缺少场景缓存 {p}")
    return p


def load_scen(pv_source: str, M: int) -> dict:
    with open(scen_path(pv_source, M), "rb") as fh:
        return pickle.load(fh)


def price_for_day(scen: dict, ds: dict, i: int, M: int, price_mode: str) -> np.ndarray:
    if price_mode == "unknown":
        return np.asarray(scen["P_all"][i], dtype=float)
    if price_mode == "known":
        return np.tile(np.asarray(ds["price"][:, i], dtype=float)[None, :], (M, 1))
    raise ValueError(price_mode)


def cvar90(daily_costs: np.ndarray) -> float:
    c = np.sort(np.asarray(daily_costs, dtype=float))
    k = max(1, int(np.ceil(0.10 * c.size)))
    return float(c[-k:].mean())


def run_roll(days, s0_start, spec, scen, ds, *, price_mode, x_cap=None,
             save_detail=False, hard_terminal_day=None, tag=""):
    L_all = scen["L_all"]; G_all = scen["G_all"]
    M = int(spec["M"])
    params = {"alpha": ALPHA, "beta": float(spec["beta"]),
              "kappa2": float(ds["kappa2_base"]) * float(spec["kappa_mult"])}
    if x_cap is not None:
        params["x_cap"] = float(x_cap)
    s0 = float(s0_start)
    logs = []
    days = list(days)
    for n, i in enumerate(days):
        s0_in = s0
        price_real = ds["price"][:, i]
        P = price_for_day(scen, ds, i, M, price_mode)
        kw = dict(params)
        if hard_terminal_day is not None and i == int(hard_terminal_day):
            kw.update({"hard_terminal": True, "s_ref": SOC0})
        try:
            plan = solve_day(P, L_all[i], G_all[i], s0_in, kw)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"{ds['date_str'][i]} 求解失败") from exc
        st = settle_day(price_real, plan["x"], plan["c"], plan["r"],
                        ds["load"][:, i], ds["pv"][:, i], s0_in)
        s0 = float(st["s_actual"][-1])
        entry = {
            "day_index": int(i), "date": str(ds["date_str"][i]), "s0": s0_in,
            "E_C": float(plan["E_C"]), "CVaR": float(plan["CVaR"]),
            "cost_plan": st["cost_plan"], "cost_emergency": st["cost_emergency"],
            "cost_total": st["cost_total"],
            "emergency_rate": st["emergency_rate"], "unextracted_ratio": st["unextracted_ratio"],
            "curtailment_rate": st["curtailment_rate"], "soc_violate_count": st["soc_violate_count"],
            "emergency_kwh": float(np.sum(st["e"])), "load_kwh": float(np.sum(ds["load"][:, i])),
            "pv_kwh": float(np.sum(ds["pv"][:, i])), "pv_used_kwh": float(np.sum(st["g"])),
            "curtail_kwh": float(np.sum(st["w"])),
            "unextracted_kwh": float(np.sum(plan["x"] - st["y"])),
            "spill_kwh": float(np.sum(st["spill"])),
            "plan_total_kwh": float(np.sum(plan["x"])),
            "charge_kwh": float(np.sum(plan["c"])), "discharge_kwh": float(np.sum(plan["r"])),
            "final_soc": s0, "price_mean": float(np.mean(price_real)),
            "eq_residual": float(plan["eq_residual"]), "ub_violation": float(plan["ub_violation"]),
        }
        if save_detail:
            entry.update({
                "plan_x": plan["x"].copy(), "plan_c": plan["c"].copy(),
                "plan_r": plan["r"].copy(), "plan_s": plan["s"].copy(),
                "settle_y": st["y"].copy(), "settle_e": st["e"].copy(),
                "settle_g": st["g"].copy(), "settle_w": st["w"].copy(),
                "settle_spill": st["spill"].copy(), "settle_s_actual": st["s_actual"].copy(),
                "price": price_real.copy(), "load_actual": ds["load"][:, i].copy(),
                "pv_actual": ds["pv"][:, i].copy(),
            })
        logs.append(entry)
        if tag and n and n % 60 == 0:
            print(f"      {tag} {ds['date_str'][i]} ({n}/{len(days)})", flush=True)
    return logs, s0


def summarize(logs):
    return {"total_cost": float(sum(x["cost_total"] for x in logs)),
            "plan_cost": float(sum(x["cost_plan"] for x in logs)),
            "emergency_cost": float(sum(x["cost_emergency"] for x in logs)),
            "emergency_kwh": float(sum(x["emergency_kwh"] for x in logs)),
            "load_kwh": float(sum(x["load_kwh"] for x in logs)),
            "final_soc": float(logs[-1]["final_soc"])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pv-source", choices=["q2", "official"], required=True)
    ap.add_argument("--price-mode", choices=["unknown", "known"], required=True)
    ap.add_argument("--select", choices=["legacy", "risk_aware"], default="legacy")
    ap.add_argument("--import-cap-kw", type=float, default=None)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--report-only-beta", type=float, default=None,
                    help="跳过调参，直接用给定 beta（配合 --report-only-kappa）")
    ap.add_argument("--report-only-kappa", type=float, default=1.0)
    ap.add_argument("--report-only-M", type=int, default=None,
                    help="跳过调参时的场景数；缺省取基准配置的 M=20（保持原有行为）。"
                         "受控口径对比时必须显式指定，否则会与主口径的 M=30 混杂")
    args = ap.parse_args()

    started = time.time()
    try:
        ds = load_dataset()
        x_cap = None if args.import_cap_kw is None else args.import_cap_kw / 6.0
        scen_map = {m: load_scen(args.pv_source, m) for m in M_CAND}
        outdir = OUT_DATA / "variants"
        outdir.mkdir(parents=True, exist_ok=True)
        TABLES.mkdir(parents=True, exist_ok=True)
        print(f"[{args.tag}] pv={args.pv_source} price={args.price_mode} "
              f"select={args.select} x_cap={x_cap}")

        print("  [1] 预热 2025-01-01~01-14")
        _, s0_tune = run_roll(WARM_DAYS, SOC0, BASELINE, scen_map[BASELINE["M"]], ds,
                              price_mode=args.price_mode, x_cap=x_cap, tag=args.tag)

        if args.report_only_beta is None:
            print("  [2] 仅历史调参 2025-01-15~01-31")
            rows, cand_logs = [], {}
            for M in M_CAND:
                for beta in BETA_CAND:
                    for km in KAPPA_MULT_CAND:
                        spec = {"M": M, "beta": beta, "kappa_mult": km}
                        logs, s_end = run_roll(TUNE_DAYS, s0_tune, spec, scen_map[M], ds,
                                               price_mode=args.price_mode, x_cap=x_cap)
                        z = summarize(logs)
                        adj = float(ds["kappa2_base"]) * max(0.0, s0_tune - s_end)
                        cand_logs[(M, beta, km)] = logs
                        rows.append([M, beta, km, z["total_cost"], z["emergency_cost"],
                                     s_end, adj, z["total_cost"] + adj,
                                     cvar90([x["cost_total"] for x in logs])])
                        print(f"      M={M:2d} β={beta:<5} κ×{km:<5} 费用={z['total_cost']:14,.0f} "
                              f"紧急={z['emergency_cost']:12,.0f} CVaR90={rows[-1][-1]:12,.0f} "
                              f"SOC_end={s_end:8.2f}", flush=True)
            tune = pd.DataFrame(rows, columns=["M", "beta", "kappa_mult", "val_total_cost",
                                               "val_emergency_cost", "val_final_soc",
                                               "terminal_adjustment", "selection_score",
                                               "val_cvar90"])
            base = tune[(tune.M == BASELINE["M"]) & (tune.beta == BASELINE["beta"]) &
                        (tune.kappa_mult == BASELINE["kappa_mult"])]
            base_row = base.iloc[0] if len(base) else tune.iloc[0]
            if args.select == "legacy":
                elig = tune[tune.val_emergency_cost <= base_row.val_emergency_cost + 1e-7]
                best = elig.loc[elig.selection_score.idxmin()]
            else:
                cut = tune.selection_score.min() * (1.0 + COST_TOL)
                elig = tune[(tune.selection_score <= cut) &
                            (tune.val_emergency_cost <= base_row.val_emergency_cost + 1e-7)]
                if len(elig) == 0:
                    elig = tune[tune.selection_score <= cut]
                best = elig.loc[elig.val_cvar90.idxmin()]
            selected = {"M": int(best.M), "beta": float(best.beta), "kappa_mult": float(best.kappa_mult)}
            print(f"  选中（规则={args.select}，仅用历史期）：{selected}；"
                  f"费用={best.val_total_cost:,.0f} CVaR90={best.val_cvar90:,.0f}")
            tune["is_selected"] = ((tune.M == selected["M"]) & (tune.beta == selected["beta"]) &
                                   (tune.kappa_mult == selected["kappa_mult"]))
            tune.to_excel(TABLES / f"{args.tag}_tuning.xlsx", index=False)
            tune_logs = cand_logs[(selected["M"], selected["beta"], selected["kappa_mult"])]
            s0_report = float(tune_logs[-1]["final_soc"])
        else:
            M_sel = int(args.report_only_M) if args.report_only_M is not None else int(BASELINE["M"])
            selected = {"M": M_sel, "beta": float(args.report_only_beta),
                        "kappa_mult": float(args.report_only_kappa)}
            tune = pd.DataFrame()
            s0_report = float(s0_tune)
            print(f"  跳过调参，直接使用 {selected}"
                  + ("（未指定 --report-only-M，按基准 M=20）" if args.report_only_M is None else ""))

        print("  [3] 报告期 2025-02-01~12-31")
        report_logs, _ = run_roll(REPORT_DAYS, s0_report, selected, scen_map[selected["M"]], ds,
                                  price_mode=args.price_mode, x_cap=x_cap, save_detail=True,
                                  hard_terminal_day=D - 1, tag=args.tag)
        z = summarize(report_logs)
        costs = np.array([x["cost_total"] for x in report_logs])
        summary = {
            "tag": args.tag, "pv_source": args.pv_source, "price_mode": args.price_mode,
            "select_rule": args.select, "import_cap_kw": args.import_cap_kw,
            "selected": selected, "kappa2_base": float(ds["kappa2_base"]),
            "selected_M": selected["M"], "selected_beta": selected["beta"],
            "selected_kappa_mult": selected["kappa_mult"],
            "report_days": len(report_logs),
            "report_total_cost": z["total_cost"], "report_plan_cost": z["plan_cost"],
            "report_emergency_cost": z["emergency_cost"], "report_emergency_kwh": z["emergency_kwh"],
            "report_load_kwh": z["load_kwh"],
            "report_plan_kwh": float(sum(x["plan_total_kwh"] for x in report_logs)),
            "report_unextracted_kwh": float(sum(x["unextracted_kwh"] for x in report_logs)),
            "report_curtail_kwh": float(sum(x["curtail_kwh"] for x in report_logs)),
            "report_pv_kwh": float(sum(x["pv_kwh"] for x in report_logs)),
            "cvar90_daily": cvar90(costs), "max_daily": float(costs.max()),
            "emergency_rate_pct": z["emergency_kwh"] / z["load_kwh"] * 100,
            "final_soc": z["final_soc"],
            "elapsed_sec": time.time() - started,
            "selection_period": "2025-01-15..2025-01-31",
            "state_origin": "2025-01-01 00:00 SOC=6000 kWh",
        }
        with open(outdir / f"{args.tag}_results.pkl", "wb") as fh:
            pickle.dump({"summary": summary, "report_logs": report_logs,
                         "tuning": tune, "params": {"alpha": ALPHA, "beta": selected["beta"],
                                                    "kappa2": selected["kappa_mult"] * float(ds["kappa2_base"]),
                                                    "M": selected["M"]},
                         "kappa2_base": float(ds["kappa2_base"])}, fh,
                        protocol=pickle.HIGHEST_PROTOCOL)
        scalar = [k for k, v in report_logs[0].items() if not isinstance(v, np.ndarray)]
        pd.DataFrame([{k: r[k] for k in scalar} for r in report_logs]).to_csv(
            TABLES / f"{args.tag}_daily.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame([summary]).to_csv(TABLES / f"{args.tag}_summary.csv", index=False,
                                       encoding="utf-8-sig")
        print(f"  完成：总费用 {z['total_cost']:,.2f} 元（计划 {z['plan_cost']:,.2f} + "
              f"紧急 {z['emergency_cost']:,.2f}）；紧急购电量 {z['emergency_kwh']:,.1f} kWh；"
              f"CVaR90 {summary['cvar90_daily']:,.0f} 元；{summary['elapsed_sec']:.0f}s")
        return 0
    except Exception as exc:  # noqa: BLE001
        print("=" * 70)
        traceback.print_exc()
        print(f"[{args.tag}] 失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
