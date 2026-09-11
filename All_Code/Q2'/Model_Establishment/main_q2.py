# -*- coding: utf-8 -*-
"""优化版 Q2 一键主程序：数据准备->净负荷预测->场景->滚动调参->导出->校验->图表。"""
import os, sys, subprocess, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
Q2_ROOT = os.path.dirname(HERE)
DATA_PROC = os.path.join(Q2_ROOT, "Data_processing")
TABLES = os.path.join(Q2_ROOT, "Results", "Tables")
PY = sys.executable


def run(path, args=None):
    print(f"\n==== 运行 {os.path.basename(path)} ====")
    t0 = time.time()
    cmd = [PY, path] + (args or [])
    cp = subprocess.run(cmd, cwd=HERE)
    if cp.returncode != 0:
        raise RuntimeError(f"{os.path.basename(path)} 退出码 {cp.returncode}")
    print(f"---- {os.path.basename(path)} 完成，耗时 {time.time()-t0:.1f}s ----")


def main():
    t0 = time.time()
    if not os.path.exists(os.path.join(DATA_PROC, "q2_dataset.pkl")):
        run(os.path.join(DATA_PROC, "q2_data_prepare.py"))
    if not os.path.exists(os.path.join(DATA_PROC, "net_forecasts.pkl")):
        run(os.path.join(HERE, "net_forecast.py"))
    for M in (10, 20, 30):
        if not os.path.exists(os.path.join(DATA_PROC, f"net_scenarios_M{M}.pkl")):
            run(os.path.join(HERE, "net_scenarios.py"), [str(M)])
    run(os.path.join(HERE, "net_rolling.py"))
    run(os.path.join(HERE, "net_export.py"))
    run(os.path.join(HERE, "net_validate.py"))
    run(os.path.join(HERE, "net_figures.py"))
    print(f"\n==== 优化版 Q2 全流程完成，总耗时 {time.time()-t0:.1f}s ====")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
