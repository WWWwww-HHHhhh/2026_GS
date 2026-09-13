# -*- coding: utf-8 -*-
"""
问题二论文用表生成（2026 数模 C 题）。

数据全部取自前置步骤已落盘的产物，不重新求解；每个统计量均带样本量列。
输出 4 张表：kappa2_calibration（复核）、tuning_sensitivity（复核）、
monthly_metrics、annual_cost_summary。
"""
import os
import pickle
import traceback
from datetime import datetime

import numpy as np
import pandas as pd

Q2CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_PROC = os.path.join(Q2CODE, "Data_processing")
TABLES = os.path.join(Q2CODE, "Results", "Tables")

T = 144


def run_tables():
    with open(os.path.join(DATA_PROC, "q2_rolling_results.pkl"), "rb") as fh:
        res = pickle.load(fh)
    with open(os.path.join(DATA_PROC, "q2_dataset.pkl"), "rb") as fh:
        ds = pickle.load(fh)
    logs = res["report_logs"]

    # ---- 1. kappa2_calibration 复核（沿用已有标定产物，不重算） ----
    k2 = pd.read_excel(os.path.join(TABLES, "kappa2_calibration.xlsx"))
    print(f"    复核 kappa2_calibration.xlsx: {len(k2)} 行，kappa2_base 来自问题一 SOC 对偶口径")

    # ---- 2. tuning_sensitivity 复核 ----
    tune = pd.read_excel(os.path.join(TABLES, "tuning_sensitivity.xlsx"), sheet_name=None)
    print(f"    复核 tuning_sensitivity.xlsx: sheets={list(tune.keys())}")

    # ---- 3. monthly_metrics ----
    fc_month = pd.read_csv(os.path.join(TABLES, "forecast_monthly_metrics.csv"))
    rows = []
    for m in range(2, 13):
        sub = [l for l in logs if int(l["date"][5:7]) == m]
        n_days = len(sub)
        load_kwh = float(sum(l["load_kwh"] for l in sub))
        pv_kwh = float(sum(l["pv_actual"].sum() for l in sub))
        x_kwh = float(sum(l["plan_x"].sum() for l in sub))
        emergency_kwh = float(sum(l["emergency_kwh"] for l in sub))
        unext_kwh = float(sum(l["unextracted_kwh"] for l in sub))
        curtail_kwh = float(sum(l["curtail_kwh"] for l in sub))
        l_mae = fc_month[(fc_month["month"] == m) & (fc_month["series"] == "load")]
        p_mae = fc_month[(fc_month["month"] == m) & (fc_month["series"] == "pv")]
        rows.append({
            "月份": m,
            "负荷MAE_kwh": float(l_mae["MAE_kwh"].iloc[0]) if len(l_mae) else np.nan,
            "负荷WAPE": float(l_mae["WAPE"].iloc[0]) if len(l_mae) else np.nan,
            "光伏MAE_kwh": float(p_mae["MAE_kwh"].iloc[0]) if len(p_mae) else np.nan,
            "光伏WAPE": float(p_mae["WAPE"].iloc[0]) if len(p_mae) else np.nan,
            "紧急购电率": emergency_kwh / load_kwh if load_kwh else 0.0,
            "未提取计划比例": unext_kwh / x_kwh if x_kwh else 0.0,
            "弃光率": curtail_kwh / pv_kwh if pv_kwh else 0.0,
            "SOC越界数": int(sum(l["soc_violate_count"] for l in sub)),
            "计划购电费": float(sum(l["cost_plan"] for l in sub)),
            "紧急购电费": float(sum(l["cost_emergency"] for l in sub)),
            "总费用": float(sum(l["cost_total"] for l in sub)),
            "样本量天数": n_days,
            "样本量时段": n_days * T,
        })
    monthly = pd.DataFrame(rows)
    monthly_path = os.path.join(TABLES, "monthly_metrics.xlsx")
    with pd.ExcelWriter(monthly_path, engine="openpyxl") as writer:
        monthly.to_excel(writer, index=False, sheet_name="monthly")
    print(f"    已写 {monthly_path}")

    # ---- 4. annual_cost_summary ----
    total_plan = float(sum(l["cost_plan"] for l in logs))
    total_emg = float(sum(l["cost_emergency"] for l in logs))
    total_cost = float(sum(l["cost_total"] for l in logs))
    total_emg_kwh = float(sum(l["emergency_kwh"] for l in logs))
    total_cur_kwh = float(sum(l["curtail_kwh"] for l in logs))
    total_unext_kwh = float(sum(l["unextracted_kwh"] for l in logs))
    n = len(logs)
    s0 = float(logs[0]["s0"]); send = float(logs[-1]["final_soc"])
    terminal_adjustment = float(res["kappa2_base"] * max(0.0, s0 - send))
    annual = pd.DataFrame([
        {"指标": "计划购电费(元)", "全年合计": total_plan, "日均": total_plan / n, "样本量天数": n},
        {"指标": "紧急购电费(元)", "全年合计": total_emg, "日均": total_emg / n, "样本量天数": n},
        {"指标": "总费用(元)", "全年合计": total_cost, "日均": total_cost / n, "样本量天数": n},
        {"指标": "期末SOC等值修正后总费用(元)", "全年合计": total_cost + terminal_adjustment,
         "日均": (total_cost + terminal_adjustment) / n, "样本量天数": n},
        {"指标": "报告期期初SOC(kWh)", "全年合计": s0, "日均": np.nan, "样本量天数": n},
        {"指标": "报告期期末SOC(kWh)", "全年合计": send, "日均": np.nan, "样本量天数": n},
        {"指标": "紧急购电量(kWh)", "全年合计": total_emg_kwh, "日均": total_emg_kwh / n, "样本量天数": n},
        {"指标": "弃光量(kWh)", "全年合计": total_cur_kwh, "日均": total_cur_kwh / n, "样本量天数": n},
        {"指标": "未提取计划量(kWh)", "全年合计": total_unext_kwh, "日均": total_unext_kwh / n, "样本量天数": n},
    ])
    note = pd.DataFrame([{"指标": f"参数: beta={res['beta_best']}, M={res['m_best']}, "
                                   f"kappa2={res['kappa2_best']:.6f}, alpha={res['alpha']}；"
                                   f"费用不含 eps 与 kappa2 罚项", "全年合计": np.nan, "日均": np.nan, "样本量天数": np.nan}])
    annual = pd.concat([annual, note], ignore_index=True)
    annual_path = os.path.join(TABLES, "annual_cost_summary.xlsx")
    with pd.ExcelWriter(annual_path, engine="openpyxl") as writer:
        annual.to_excel(writer, index=False, sheet_name="annual")
    print(f"    已写 {annual_path}")

    # ---- 复核：annual 与 daily_rolling_log 求和一致 ----
    daily = pd.read_csv(os.path.join(TABLES, "daily_rolling_log.csv"))
    assert abs(float(daily["cost_total"].sum()) - total_cost) < 1e-6, "annual 与 daily 总费用不一致"
    print("    复核：annual_cost_summary 与 daily_rolling_log 求和一致")


def main() -> int:
    try:
        run_tables()
        return 0
    except Exception as exc:
        print("=" * 60)
        print("表格生成失败：")
        traceback.print_exc()
        print(f"错误信息: {exc}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
