# -*- coding: utf-8 -*-
"""Q2'' 一键复现：数据准备 -> 预测 -> 滚动 -> 导出 -> 校验 -> 表格 -> 图。"""
import os, subprocess, sys
GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q2P = os.path.join(GS, "Q2''")
DP = os.path.join(Q2P, "Data_processing")
ME = os.path.join(Q2P, "Model_Establishment")
PY = sys.executable

def run(path, cwd=None):
    print("\n===== ", os.path.basename(path), " =====", flush=True)
    cp = subprocess.run([PY, path], cwd=cwd or os.path.dirname(path))
    if cp.returncode != 0:
        raise SystemExit(cp.returncode)

def main():
    run(os.path.join(DP, "q2_data_prepare.py"))
    run(os.path.join(ME, "forecast.py"))
    run(os.path.join(ME, "rolling.py"))
    run(os.path.join(ME, "export.py"))
    run(os.path.join(ME, "validate.py"))
    run(os.path.join(ME, "make_tables.py"))
    run(os.path.join(ME, "make_figures.py"))
    print("\nALL_DONE")

if __name__ == "__main__":
    main()
