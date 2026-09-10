# -*- coding: utf-8 -*-
"""问题1效率口径灵敏度：比较单向效率90%与往返效率90%。

该脚本只生成对照结果，不改变 q1_model.py 的主模型参数，也不覆盖 result1.xlsx。
"""

import importlib.util
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MODEL_PATH = HERE / "q1_model.py"
OUTPUT = HERE.parent / "Tables" / "q1_efficiency_sensitivity.json"

spec = importlib.util.spec_from_file_location("q1_model", MODEL_PATH)
q1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q1)


def run_sensitivity():
    _, price, load, pv = q1.load_data()
    baseline_cost = float(price @ np.maximum(load - pv, 0.0))
    cases = [
        ("charge_and_discharge_each_90_percent", 0.9, 0.9),
        ("round_trip_90_percent_symmetric", math.sqrt(0.9), math.sqrt(0.9)),
    ]
    results = []
    original_eta_c, original_eta_r = q1.ETA_C, q1.ETA_R
    try:
        for name, eta_c, eta_r in cases:
            q1.ETA_C, q1.ETA_R = eta_c, eta_r
            solution = q1.build_and_solve(price, load, pv)
            checks = q1.validate(solution, load, pv)
            saving = baseline_cost - solution["C1"]
            results.append({
                "case": name,
                "eta_charge": eta_c,
                "eta_discharge": eta_r,
                "round_trip_efficiency": eta_c * eta_r,
                "purchase_cost_yuan": solution["C1"],
                "total_purchase_kwh": float(solution["x"].sum()),
                "total_charge_kwh": float(solution["c"].sum()),
                "total_discharge_kwh": float(solution["r"].sum()),
                "saving_vs_no_storage_yuan": saving,
                "saving_rate_vs_no_storage": saving / baseline_cost,
                "soc_min_kwh": checks["soc_min"],
                "soc_max_kwh": checks["soc_max"],
                "max_balance_residual_kwh": checks["max_abs_balance_residual_kwh"],
                "max_soc_recursion_residual_kwh": checks["max_abs_soc_recursion_residual_kwh"],
            })
    finally:
        q1.ETA_C, q1.ETA_R = original_eta_c, original_eta_r

    output = {
        "purpose": "Interpretation sensitivity only; the primary Q1 result uses eta_charge=eta_discharge=0.9.",
        "no_storage_baseline_cost_yuan": baseline_cost,
        "cases": results,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    print(json.dumps(run_sensitivity(), ensure_ascii=False, indent=2))
