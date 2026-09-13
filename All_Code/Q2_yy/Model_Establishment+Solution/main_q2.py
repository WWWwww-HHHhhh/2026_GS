# -*- coding: utf-8 -*-
"""
问题二主程序（2026 数模 C 题）。

依次执行：数据准备 -> 预测与场景生成 -> 滚动优化与参数标定 -> 结果导出 -> 严格校验。
中间结果已存在时自动跳过对应步骤。
"""
import os
import sys
import subprocess
import time
import pickle
import traceback
from datetime import datetime

import numpy as np

from paths import Q2_ROOT, Q2_DATA_PROCESSING, Q2_TABLES
Q2CODE = str(Q2_ROOT)
DATA_PROC = str(Q2_DATA_PROCESSING)
TABLES = str(Q2_TABLES)
MODEL_DIR = os.path.dirname(os.path.abspath(__file__))

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

    # 第一步：数据准备（结果已存在则跳过）
    pkl = os.path.join(DATA_PROC, "q2_dataset.pkl")
    if os.path.exists(pkl):
        print("数据准备跳过：q2_dataset.pkl 已存在")
    else:
        steps["数据准备"] = run_script(os.path.join(DATA_PROC, "q2_data_prepare.py"))

    # 第二步：负荷与光伏预测、场景生成（缓存已存在则跳过）
    fc_path = os.path.join(DATA_PROC, "forecasts.pkl")
    if os.path.exists(fc_path):
        print("预测跳过：forecasts.pkl 已存在")
    else:
        steps["负荷与光伏预测"] = run_script(os.path.join(MODEL_DIR, "forecast.py"))
    for m in (10, 20, 30):
        cache = os.path.join(DATA_PROC, f"scenarios_M{m}.pkl")
        if not os.path.exists(cache):
            t0 = time.time()
            cp = subprocess.run([PY, os.path.join(MODEL_DIR, "scenarios.py"), "--M", str(m)], cwd=MODEL_DIR)
            if cp.returncode != 0:
                raise RuntimeError(f"scenarios.py --M {m} 退出码 {cp.returncode}")
            steps[f"场景生成 M={m}"] = time.time() - t0

    # 第三步：滚动优化与参数标定
    steps["滚动优化与参数标定"] = run_script(os.path.join(MODEL_DIR, "rolling.py"))

    # 第四步：结果导出与校验（先导出 result2.xlsx，再逐格核对磁盘文件）
    steps["结果导出"] = run_script(os.path.join(MODEL_DIR, "export.py"))
    steps["严格校验"] = run_script(os.path.join(MODEL_DIR, "validate.py"))

    # 控制台汇总本次运行的步骤耗时与报告期费用。
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

    print("\n" + "\n".join(lines))
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
