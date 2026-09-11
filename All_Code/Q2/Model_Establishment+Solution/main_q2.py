# -*- coding: utf-8 -*-
"""
P4 主程序 main_q2.py（2026 数模 C 题 问题二）
============================================
按顺序编排：P0 数据准备（已存在则跳过）-> P1 预测/场景（已存在则跳过）
            -> P3 滚动与调参 -> P4 校验 -> P4 导出，并写 run_summary.txt。
"""
import os
import sys
import subprocess
import time
import pickle
import traceback
from datetime import datetime

import numpy as np

GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q2CODE = os.path.join(GS, r"All_Code\Q2")
DATA_PROC = os.path.join(Q2CODE, "Data_processing")
TABLES = os.path.join(Q2CODE, "Results", "Tables")
MODEL_DIR = os.path.join(Q2CODE, "Model_Establishment+Solution")

PY = sys.executable


def run_script(path):
    print(f"\n==== 运行 {os.path.basename(path)} ====")
    t0 = time.time()
    cp = subprocess.run([PY, path], cwd=MODEL_DIR)
    dt = time.time() - t0
    if cp.returncode != 0:
        raise RuntimeError(f"{os.path.basename(path)} 退出码 {cp.returncode}")
    return dt


def main() -> int:
    t_start = time.time()
    steps = {}

    # P0：数据准备（pkl 已存在则跳过）
    pkl = os.path.join(DATA_PROC, "q2_dataset.pkl")
    if os.path.exists(pkl):
        print("P0 跳过：q2_dataset.pkl 已存在")
    else:
        steps["P0_data_prepare"] = run_script(os.path.join(DATA_PROC, "q2_data_prepare.py"))

    # P1：预测与场景（缓存已存在则跳过）
    fc_path = os.path.join(DATA_PROC, "forecasts.pkl")
    if os.path.exists(fc_path):
        print("P1 forecast 跳过：forecasts.pkl 已存在")
    else:
        steps["P1_forecast"] = run_script(os.path.join(MODEL_DIR, "forecast.py"))
    if not os.path.exists(os.path.join(DATA_PROC, "scenarios_M20.pkl")):
        steps["P1_scenarios"] = run_script(os.path.join(MODEL_DIR, "scenarios.py"))
    else:
        print("P1 scenarios 跳过：scenarios_M20.pkl 已存在")

    # P3：滚动与调参
    steps["P3_rolling"] = run_script(os.path.join(MODEL_DIR, "rolling.py"))

    # P4：导出与校验（先导出 result2，再让第 12 项逐格核对磁盘文件）
    steps["P4_export"] = run_script(os.path.join(MODEL_DIR, "export.py"))
    steps["P4_validate"] = run_script(os.path.join(MODEL_DIR, "validate.py"))

    # 汇总
    with open(os.path.join(DATA_PROC, "q2_rolling_results.pkl"), "rb") as fh:
        res = pickle.load(fh)
    total_elapsed = time.time() - t_start

    lines = []
    lines.append(f"问题二 运行汇总（生成于 {datetime.now():%Y-%m-%d %H:%M:%S}）")
    lines.append("-" * 60)
    lines.append(f"总运行时间: {total_elapsed:.1f} 秒")
    lines.append("各步骤耗时:")
    for k, v in steps.items():
        lines.append(f"  - {k}: {v:.1f} 秒")
    lines.append("-" * 60)
    lines.append(f"最终参数: beta={res['beta_best']}, M={res['m_best']}, "
                 f"kappa2={res['kappa2_best']:.6f} (kappa2_base={res['kappa2_base']:.6f}), alpha={res['alpha']}")
    logs = res["report_logs"]
    total_cost = float(sum(l["cost_total"] for l in logs))
    plan_cost = float(sum(l["cost_plan"] for l in logs))
    emg_cost = float(sum(l["cost_emergency"] for l in logs))
    lines.append(f"报告期(334天)费用: 总费用={total_cost:.2f} 元, 计划购电费={plan_cost:.2f}, 紧急购电费={emg_cost:.2f}")
    lines.append(f"报告期紧急购电率(电量): {float(sum(l['emergency_kwh'] for l in logs)/sum(l['load_kwh'] for l in logs)):.6f}")
    lines.append(f"报告期弃光率: {float(sum(l['curtail_kwh'] for l in logs)/sum(float(np.sum(l['pv_actual'])) for l in logs)):.6f}")
    lines.append("注：报告费用不含 eps 与 kappa2 罚项。")

    summary_path = os.path.join(TABLES, "run_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
    print(f"\nrun_summary.txt 已写入: {summary_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("=" * 60)
        print("main_q2 执行失败：")
        traceback.print_exc()
        print(f"错误信息: {exc}")
        sys.exit(1)
