# -*- coding: utf-8 -*-
"""只读：判定每个场景缓存是否为「首日冷启动修复后」版本。

判据：day0 的场景中心 = 冷启动预测。
  修复前 → 等于 2025-01-01 当天实际电价（泄露）
  修复后 → 等于附件1 典型日曲线（题目给定先验）
"""
import pickle
import sys
from pathlib import Path

import numpy as np

WYH = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q4\Q4_wyh")
ds = pickle.load(open(WYH / "Data_processing" / "q4_dataset.pkl", "rb"))
prior = np.asarray(ds["price_q2_fixed"], float)          # 附件1 典型日曲线
actual0 = np.asarray(ds["price"], float)[:, 0]           # 2025-01-01 实际电价
print(f"附件1 先验曲线：均值 {prior.mean():.6f}，形状首末 {prior[0]:.4f}/{prior[-1]:.4f}")
print(f"2025-01-01 实际：均值 {actual0.mean():.6f}，形状首末 {actual0[0]:.4f}/{actual0[-1]:.4f}")
print()
rows = []
for f in sorted((WYH / "Data_processing").glob("scenarios_M*.pkl")):
    sc = pickle.load(open(f, "rb"))
    c0 = np.asarray(sc["P_all"][0], float).mean(axis=0)   # day0 场景中心
    d_prior = float(np.max(np.abs(c0 - prior)))
    d_actual = float(np.max(np.abs(c0 - actual0)))
    verdict = "修复后(先验)" if d_prior < 1e-9 else ("修复前(泄露)" if d_actual < 1e-9 else "未知")
    rows.append((f.name, sc.get("pv_source"), round(float(c0.mean()), 6),
                 f"{d_prior:.2e}", f"{d_actual:.2e}", verdict))
print(f"{'文件':34s} {'源':8s} {'day0中心均值':>12s} {'vs先验':>10s} {'vs实际':>10s}  判定")
for r in rows:
    print(f"{r[0]:34s} {str(r[1]):8s} {r[2]:12.6f} {r[3]:>10s} {r[4]:>10s}  {r[5]}")
bad = [r[0] for r in rows if r[5] != "修复后(先验)"]
print("\n需重生成的场景文件：", bad if bad else "无")
sys.exit(0 if not bad else 1)
