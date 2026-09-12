"""Run reproducible Q3 strategy backtests from verified Q2_yy and official data."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from q3_core import (
    ALPHA, BETA, CAP, EPS, ISSUES, KAPPA, M, Q2, REPO, SEED,
    SOC_MAX, SOC_MIN, STRATEGIES, T, PVForecast, SourceData,
    execute_slot, market_cost, market_cost_alternative, scenarios, solve_window,
)

HERE = Path(__file__).resolve().parent
SPECIFIED = ("2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sources(data: SourceData) -> dict:
    book = Q2 / "Results" / "Tables" / "result2.xlsx"
    expected = "B2379A84A81863E00AE274A91DCBDA1C1B822369522D768B1348C8037D1B6353"
    actual = sha256(book)
    if actual != expected.lower():
        raise RuntimeError(f"Q2_yy result2 hash mismatch: {actual}")
    if data.dates[31] != "2025-02-01" or data.dates[-1] != "2025-12-31":
        raise RuntimeError("Q2_yy calendar mismatch")
    return {
        "q2_result2_sha256": actual,
        "attachment1_sha256": sha256(REPO / "Data" / "附件" / "附件1.xlsx"),
        "attachment2_sha256": sha256(REPO / "Data" / "附件" / "附件2.xlsx"),
        "attachment3_sha256": sha256(REPO / "Data" / "附件" / "附件3.xlsx"),
    }


def backtest_strategy(data: SourceData, pv_forecast: PVForecast, name: str,
                      outdir: Path, start_day: int = 31, end_day: int = 365,
                      settlement: str = "net") -> dict:
    if name not in STRATEGIES:
        raise ValueError(name)
    if not 31 <= start_day < end_day <= 365:
        raise ValueError("invalid formal-period day range")
    strategy_dir = outdir / name
    strategy_dir.mkdir(parents=True, exist_ok=True)
    day_rows, interval_rows, update_rows, manifest_rows = [], [], [], []
    soc = 6000.0
    started = time.perf_counter()
    for day in range(start_day, end_day):
        date = data.dates[day]
        day_initial_soc = soc
        price = data.price[:, day]
        actual_l = data.load[:, day]
        actual_g = data.pv[:, day]
        hard_terminal = day == 364
        terminal_target = 6000.0 if hard_terminal else day_initial_soc

        bundle = scenarios(data, pv_forecast, day, 0)
        for scenario_id, source_day in enumerate(bundle.sources, start=1):
            manifest_rows.append({"target_date": date, "issue_hour": 0,
                                  "scenario_id": scenario_id, "source_day": data.dates[int(source_day)],
                                  "weight": 1.0/M})
        initial = solve_window(price, bundle, soc, terminal_target, hard_terminal=hard_terminal,
                               settlement=settlement)
        zero = initial.q.copy()
        active_q = zero.copy()
        active_c = initial.c.copy()
        active_r = initial.r.copy()
        initial_obj = initial.objective
        solver_eq = initial.eq_residual
        solver_ub = initial.ub_violation
        both_count = initial.both_count
        update_rows.append({"date": date, "issue_hour": 0, "strategy": name,
                            "changed_plan_kwh": 0.0, "expected_future_cost_yuan": initial.expected_cost,
                            "cvar_future_cost_yuan": initial.cvar_cost,
                            "objective": initial_obj, "soc_at_issue_kwh": soc,
                            "terminal_target_kwh": terminal_target,
                            "clipped_load_scenario_cells": bundle.clipped_load,
                            "clipped_pv_scenario_cells": bundle.clipped_pv})

        for t in range(T):
            if t in STRATEGIES[name]:
                previous = active_q[t:].copy()
                bundle = scenarios(data, pv_forecast, day, t)
                for scenario_id, source_day in enumerate(bundle.sources, start=1):
                    manifest_rows.append({"target_date": date, "issue_hour": t//6,
                                          "scenario_id": scenario_id, "source_day": data.dates[int(source_day)],
                                          "weight": 1.0/M})
                revised = solve_window(price[t:], bundle, soc, terminal_target,
                                       zero_plan=zero[t:], hard_terminal=hard_terminal,
                                       settlement=settlement)
                active_q[t:] = revised.q
                active_c[t:] = revised.c
                active_r[t:] = revised.r
                solver_eq = max(solver_eq, revised.eq_residual)
                solver_ub = max(solver_ub, revised.ub_violation)
                both_count += revised.both_count
                update_rows.append({"date": date, "issue_hour": t//6, "strategy": name,
                                    "changed_plan_kwh": float(np.sum(np.abs(active_q[t:] - previous))),
                                    "expected_future_cost_yuan": revised.expected_cost,
                                    "cvar_future_cost_yuan": revised.cvar_cost,
                                    "objective": revised.objective, "soc_at_issue_kwh": soc,
                                    "terminal_target_kwh": terminal_target,
                                    "clipped_load_scenario_cells": bundle.clipped_load,
                                    "clipped_pv_scenario_cells": bundle.clipped_pv})
            before = soc
            actual = execute_slot(active_q[t], active_c[t], active_r[t], soc,
                                  actual_l[t], actual_g[t])
            soc = actual["soc_next"]
            interval_rows.append({
                "date": date, "interval_index": t, "interval_start_min": t*10,
                "interval_end_min": (t+1)*10, "price_yuan_per_kwh": price[t],
                "load_actual_kwh": actual_l[t], "pv_actual_kwh": actual_g[t],
                "zero_plan_kwh": zero[t], "final_plan_kwh": active_q[t],
                "charge_kwh": active_c[t], "discharge_kwh": active_r[t],
                "used_plan_kwh": actual["y"], "emergency_kwh": actual["e"],
                "pv_used_kwh": actual["g"], "curtail_kwh": actual["w"],
                "spill_kwh": actual["v"], "soc_start_kwh": before,
                "soc_end_kwh": soc, "balance_residual_kwh": actual["balance_residual"],
                "market_cost_yuan": float(market_cost(np.array([price[t]]),
                                         np.array([zero[t]]), np.array([active_q[t]]))[0]),
                "emergency_cost_yuan": 5.0 * price[t] * actual["e"],
                "alternative_market_cost_yuan": float(market_cost_alternative(
                    np.array([price[t]]), np.array([zero[t]]), np.array([active_q[t]]))[0]),
            })

        first = (day - start_day) * T
        today = interval_rows[first:first+T]
        plan_cost = float(np.dot(price, zero))
        market = float(sum(x["market_cost_yuan"] for x in today))
        emergency = float(sum(x["emergency_cost_yuan"] for x in today))
        alt_market = float(sum(x["alternative_market_cost_yuan"] for x in today))
        day_rows.append({
            "date": date, "strategy": name, "soc_initial_kwh": day_initial_soc,
            "soc_final_kwh": soc, "zero_plan_kwh": float(np.sum(zero)),
            "final_plan_kwh": float(sum(x["final_plan_kwh"] for x in today)),
            "used_plan_kwh": float(sum(x["used_plan_kwh"] for x in today)),
            "emergency_kwh": float(sum(x["emergency_kwh"] for x in today)),
            "curtail_kwh": float(sum(x["curtail_kwh"] for x in today)),
            "spill_kwh": float(sum(x["spill_kwh"] for x in today)),
            "charge_kwh": float(sum(x["charge_kwh"] for x in today)),
            "discharge_kwh": float(sum(x["discharge_kwh"] for x in today)),
            "plan_cost_yuan": plan_cost, "adjustment_cost_yuan": market - plan_cost,
            "market_cost_yuan": market, "emergency_cost_yuan": emergency,
            "total_cost_yuan": market + emergency,
            "alternative_total_cost_yuan": alt_market + emergency,
            "max_solver_eq_residual": solver_eq,
            "max_solver_ub_violation": solver_ub,
            "simultaneous_charge_discharge_count": both_count,
            "soft_terminal_deviation_kwh": 0.0 if hard_terminal else abs(soc - terminal_target),
        })
        if (day - start_day + 1) % 10 == 0 or day == end_day - 1:
            print(f"{name} {date} days={day-start_day+1}/{end_day-start_day} "
                  f"cost={sum(x['total_cost_yuan'] for x in day_rows):.2f} "
                  f"elapsed={time.perf_counter()-started:.1f}s", flush=True)

    pd.DataFrame(day_rows).to_csv(strategy_dir / "daily.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(interval_rows).to_csv(strategy_dir / "intervals.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(update_rows).to_csv(strategy_dir / "updates.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(manifest_rows).to_csv(strategy_dir / "scenario_manifest.csv", index=False, encoding="utf-8-sig")
    total = float(sum(x["total_cost_yuan"] for x in day_rows))
    summary = {
        "strategy": name, "report_days": len(day_rows), "report_start": day_rows[0]["date"],
        "report_end": day_rows[-1]["date"], "initial_soc_kwh": day_rows[0]["soc_initial_kwh"],
        "final_soc_kwh": day_rows[-1]["soc_final_kwh"],
        "plan_cost_yuan": float(sum(x["plan_cost_yuan"] for x in day_rows)),
        "adjustment_cost_yuan": float(sum(x["adjustment_cost_yuan"] for x in day_rows)),
        "market_cost_yuan": float(sum(x["market_cost_yuan"] for x in day_rows)),
        "emergency_cost_yuan": float(sum(x["emergency_cost_yuan"] for x in day_rows)),
        "total_cost_yuan": total,
        "alternative_total_cost_yuan_for_same_policy": float(sum(x["alternative_total_cost_yuan"] for x in day_rows)),
        "emergency_kwh": float(sum(x["emergency_kwh"] for x in day_rows)),
        "curtail_kwh": float(sum(x["curtail_kwh"] for x in day_rows)),
        "spill_kwh": float(sum(x["spill_kwh"] for x in day_rows)),
        "max_solver_eq_residual": max(x["max_solver_eq_residual"] for x in day_rows),
        "max_solver_ub_violation": max(x["max_solver_ub_violation"] for x in day_rows),
        "simultaneous_charge_discharge_count": int(sum(x["simultaneous_charge_discharge_count"] for x in day_rows)),
        "elapsed_seconds": time.perf_counter() - started,
    }
    (strategy_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategies", nargs="+", choices=tuple(STRATEGIES), default=["S0", "S6", "S12", "S18", "S6_12", "Sall"])
    parser.add_argument("--start", default="2025-02-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--forecast-method", choices=["linear_endpoint", "step"], default="linear_endpoint")
    parser.add_argument("--settlement", choices=["net", "gross"], default="net")
    parser.add_argument("--outdir", type=Path, default=HERE / "results")
    args = parser.parse_args()
    started = time.perf_counter()
    data = SourceData.load_verified()
    source_hashes = verify_sources(data)
    start_day = data.dates.index(args.start)
    end_day = data.dates.index(args.end) + 1
    if start_day != 31 and end_day == 365:
        raise ValueError("partial runs must set both --start and --end; 334-day results start Feb 1")
    forecast = PVForecast(data, args.forecast_method)
    args.outdir.mkdir(parents=True, exist_ok=True)
    run_meta = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "source_hashes": source_hashes, "forecast_method": args.forecast_method,
                "M": M, "alpha": ALPHA, "beta": BETA, "kappa2": KAPPA, "eps": EPS,
                "seed": SEED, "soc_min": SOC_MIN, "soc_max": SOC_MAX, "cap_kwh": CAP,
                "settlement": f"{args.settlement}, final-vs-zero-plan-once, causal_sequential_exact_plan",
                "year_end_terminal": "6000 kWh hard", "Q2_baseline_total_yuan": 14708963.494455712,
                "report_start": args.start, "report_end": args.end,
                "strategies": args.strategies}
    (args.outdir / "run_metadata.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    summaries = []
    for name in args.strategies:
        summaries.append(backtest_strategy(data, forecast, name, args.outdir, start_day, end_day,
                                           settlement=args.settlement))
    pd.DataFrame(summaries).to_csv(args.outdir / "strategy_summary.csv", index=False, encoding="utf-8-sig")
    print(json.dumps({"elapsed_seconds": time.perf_counter()-started, "summaries": summaries}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
