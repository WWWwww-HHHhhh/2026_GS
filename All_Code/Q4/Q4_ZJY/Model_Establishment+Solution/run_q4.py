from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
Q3_CODE = HERE.parents[2] / "Q3" / "Model_Establishment+Solution"
Q4_2_DATA = HERE.parents[1] / "Q4_wyh" / "Data_processing"
sys.path.insert(0, str(Q3_CODE))

from q3_core import (  # noqa: E402
    ALPHA, BETA, CAP, EPS, KAPPA, M, SEED, SOC_MAX, SOC_MIN, STRATEGIES, T,
    PVForecast, SourceData, execute_slot, market_cost, market_cost_alternative,
)
from run_q3 import sha256, verify_sources  # noqa: E402
from q4_data import ATTACH4, load_q4_price  # noqa: E402
from q4_price_core import joint_scenarios, solve_window  # noqa: E402

OUT = HERE.parent / "Results" / "Tables"
PRICE_FORECAST = Q4_2_DATA / "price_forecast.pkl"


def load_price_forecast() -> np.ndarray:
    """Read the precomputed causal day-ahead price forecast matrix."""
    with PRICE_FORECAST.open("rb") as fh:
        payload = pickle.load(fh)
    price_hat = np.asarray(payload["price_hat"], dtype=float)
    if price_hat.shape != (T, 365) or not np.isfinite(price_hat).all() or np.any(price_hat <= 0):
        raise ValueError("invalid causal price forecast matrix")
    return price_hat


def backtest_strategy(data: SourceData, pv_forecast: PVForecast, price_hat: np.ndarray,
                      name: str, outdir: Path, start_day: int = 31,
                      end_day: int = 365, settlement: str = "net") -> dict:
    """Execute one Q3 update strategy without exposing future actual prices."""
    if name not in STRATEGIES or not 31 <= start_day < end_day <= 365:
        raise ValueError("invalid strategy or report range")
    strategy_dir = outdir / name
    strategy_dir.mkdir(parents=True, exist_ok=True)
    day_rows, interval_rows, update_rows, manifest_rows = [], [], [], []
    # Q2_yy's validated formal-period state begins at the given 6000 kWh.
    soc = 6000.0
    started = time.perf_counter()
    for day in range(start_day, end_day):
        date = data.dates[day]
        day_initial_soc = soc
        actual_price = data.price[:, day]
        actual_l, actual_g = data.load[:, day], data.pv[:, day]
        hard_terminal = day == 364
        terminal_target = 6000.0 if hard_terminal else day_initial_soc

        bundle = joint_scenarios(data, pv_forecast, price_hat, day, 0)
        for scenario_id, source_day in enumerate(bundle.sources, start=1):
            manifest_rows.append({"target_date": date, "issue_hour": 0,
                                  "scenario_id": scenario_id,
                                  "source_day": data.dates[int(source_day)],
                                  "weight": 1.0 / M})
        initial = solve_window(bundle, soc, terminal_target,
                               hard_terminal=hard_terminal, settlement=settlement)
        zero, active_q = initial.q.copy(), initial.q.copy()
        active_c, active_r = initial.c.copy(), initial.r.copy()
        solver_eq, solver_ub, both_count = initial.eq_residual, initial.ub_violation, initial.both_count
        update_rows.append({"date": date, "issue_hour": 0, "strategy": name,
                            "changed_plan_kwh": 0.0,
                            "expected_future_cost_yuan": initial.expected_cost,
                            "cvar_future_cost_yuan": initial.cvar_cost,
                            "objective": initial.objective, "soc_at_issue_kwh": soc,
                            "terminal_target_kwh": terminal_target,
                            "clipped_load_scenario_cells": bundle.clipped_load,
                            "clipped_pv_scenario_cells": bundle.clipped_pv,
                            "clipped_price_scenario_cells": bundle.clipped_price})

        for t in range(T):
            if t in STRATEGIES[name]:
                previous = active_q[t:].copy()
                bundle = joint_scenarios(data, pv_forecast, price_hat, day, t)
                for scenario_id, source_day in enumerate(bundle.sources, start=1):
                    manifest_rows.append({"target_date": date, "issue_hour": t // 6,
                                          "scenario_id": scenario_id,
                                          "source_day": data.dates[int(source_day)],
                                          "weight": 1.0 / M})
                revised = solve_window(bundle, soc, terminal_target, zero_plan=zero[t:],
                                       hard_terminal=hard_terminal, settlement=settlement)
                active_q[t:], active_c[t:], active_r[t:] = revised.q, revised.c, revised.r
                solver_eq, solver_ub = max(solver_eq, revised.eq_residual), max(solver_ub, revised.ub_violation)
                both_count += revised.both_count
                update_rows.append({"date": date, "issue_hour": t // 6, "strategy": name,
                                    "changed_plan_kwh": float(np.sum(np.abs(active_q[t:] - previous))),
                                    "expected_future_cost_yuan": revised.expected_cost,
                                    "cvar_future_cost_yuan": revised.cvar_cost,
                                    "objective": revised.objective, "soc_at_issue_kwh": soc,
                                    "terminal_target_kwh": terminal_target,
                                    "clipped_load_scenario_cells": bundle.clipped_load,
                                    "clipped_pv_scenario_cells": bundle.clipped_pv,
                                    "clipped_price_scenario_cells": bundle.clipped_price})
            before = soc
            actual = execute_slot(active_q[t], active_c[t], active_r[t], soc,
                                  actual_l[t], actual_g[t])
            soc = actual["soc_next"]
            interval_rows.append({
                "date": date, "interval_index": t, "interval_start_min": t * 10,
                "interval_end_min": (t + 1) * 10, "price_yuan_per_kwh": actual_price[t],
                "load_actual_kwh": actual_l[t], "pv_actual_kwh": actual_g[t],
                "zero_plan_kwh": zero[t], "final_plan_kwh": active_q[t],
                "charge_kwh": active_c[t], "discharge_kwh": active_r[t],
                "used_plan_kwh": actual["y"], "emergency_kwh": actual["e"],
                "pv_used_kwh": actual["g"], "curtail_kwh": actual["w"],
                "spill_kwh": actual["v"], "soc_start_kwh": before, "soc_end_kwh": soc,
                "balance_residual_kwh": actual["balance_residual"],
                "market_cost_yuan": float(market_cost(np.array([actual_price[t]]),
                    np.array([zero[t]]), np.array([active_q[t]]))[0]),
                "emergency_cost_yuan": 5.0 * actual_price[t] * actual["e"],
                "alternative_market_cost_yuan": float(market_cost_alternative(
                    np.array([actual_price[t]]), np.array([zero[t]]), np.array([active_q[t]]))[0]),
            })

        today = interval_rows[(day - start_day) * T:(day - start_day + 1) * T]
        market = float(sum(x["market_cost_yuan"] for x in today))
        emergency = float(sum(x["emergency_cost_yuan"] for x in today))
        alt_market = float(sum(x["alternative_market_cost_yuan"] for x in today))
        plan_cost = float(np.dot(actual_price, zero))
        day_rows.append({
            "date": date, "strategy": name, "soc_initial_kwh": day_initial_soc, "soc_final_kwh": soc,
            "zero_plan_kwh": float(np.sum(zero)), "final_plan_kwh": float(sum(x["final_plan_kwh"] for x in today)),
            "used_plan_kwh": float(sum(x["used_plan_kwh"] for x in today)),
            "emergency_kwh": float(sum(x["emergency_kwh"] for x in today)),
            "curtail_kwh": float(sum(x["curtail_kwh"] for x in today)),
            "spill_kwh": float(sum(x["spill_kwh"] for x in today)),
            "charge_kwh": float(sum(x["charge_kwh"] for x in today)),
            "discharge_kwh": float(sum(x["discharge_kwh"] for x in today)),
            "plan_cost_yuan": plan_cost, "adjustment_cost_yuan": market - plan_cost,
            "market_cost_yuan": market, "emergency_cost_yuan": emergency, "total_cost_yuan": market + emergency,
            "alternative_total_cost_yuan": alt_market + emergency, "max_solver_eq_residual": solver_eq,
            "max_solver_ub_violation": solver_ub, "simultaneous_charge_discharge_count": both_count,
            "soft_terminal_deviation_kwh": 0.0 if hard_terminal else abs(soc - terminal_target),
        })
        if (day - start_day + 1) % 10 == 0 or day == end_day - 1:
            print(f"{name} {date} days={day-start_day+1}/{end_day-start_day} "
                  f"cost={sum(x['total_cost_yuan'] for x in day_rows):.2f} "
                  f"elapsed={time.perf_counter()-started:.1f}s", flush=True)

    for rows, filename in ((day_rows, "daily.csv"), (interval_rows, "intervals.csv"),
                           (update_rows, "updates.csv"), (manifest_rows, "scenario_manifest.csv")):
        pd.DataFrame(rows).to_csv(strategy_dir / filename, index=False, encoding="utf-8-sig")
    total = float(sum(x["total_cost_yuan"] for x in day_rows))
    summary = {"strategy": name, "report_days": len(day_rows), "report_start": day_rows[0]["date"],
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
               "elapsed_seconds": time.perf_counter() - started}
    (strategy_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategies", nargs="+", choices=tuple(STRATEGIES), default=list(STRATEGIES))
    parser.add_argument("--start", default="2025-02-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--settlement", choices=["net", "gross"], default="net")
    parser.add_argument("--outdir", type=Path, default=OUT)
    args = parser.parse_args()
    started = time.perf_counter()
    data = SourceData.load_verified()
    data.price = load_q4_price()
    price_hat = load_price_forecast()
    start_day, end_day = data.dates.index(args.start), data.dates.index(args.end) + 1
    if start_day != 31 and end_day == 365:
        raise ValueError("partial runs must set both --start and --end")
    forecast = PVForecast(data, "linear_endpoint")
    args.outdir.mkdir(parents=True, exist_ok=True)
    source_hashes = verify_sources(data)
    source_hashes["attachment4_sha256"] = sha256(ATTACH4)
    source_hashes["causal_price_forecast_sha256"] = sha256(PRICE_FORECAST)
    summaries = [backtest_strategy(data, forecast, price_hat, name, args.outdir, start_day, end_day,
                                   settlement=args.settlement) for name in args.strategies]
    pd.DataFrame(summaries).to_csv(args.outdir / "strategy_summary.csv", index=False, encoding="utf-8-sig")
    meta = {"problem": "Q4-3, volatile real-time-price causal rolling optimization",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "price_information": "At each issue time, price scenarios use only the causal day-ahead forecast and residual blocks from days strictly before the target day. Actual target-day prices are used only for realized settlement.",
            "price_scenario": "Q4-2 causal price forecast plus Q3-sampled historical same-day residual blocks",
            "settlement": args.settlement, "forecast_method": "linear_endpoint",
            "report_start": args.start, "report_end": args.end, "strategies": args.strategies,
            "M": M, "alpha": ALPHA, "beta": BETA, "kappa2": KAPPA, "eps": EPS,
            "seed": SEED, "soc_min": SOC_MIN, "soc_max": SOC_MAX, "cap_kwh": CAP,
            "initial_state": "Q2_yy validated formal-period input, 2025-02-01 00:00 SOC=6000 kWh",
            "year_end_terminal": "2025-12-31 24:00 SOC=6000 kWh hard",
            "source_hashes": source_hashes, "elapsed_seconds": time.perf_counter() - started}
    (args.outdir / "run_metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"elapsed_seconds": meta["elapsed_seconds"], "summaries": summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
