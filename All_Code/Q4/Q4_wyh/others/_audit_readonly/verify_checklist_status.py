# -*- coding: utf-8 -*-
"""只读核验：桌面《Q4建模与代码审核问题清单.md》8 条问题的当前状态。不修改任何产物。"""
from __future__ import annotations

import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS")
WYH = ROOT / "All_Code" / "Q4" / "Q4_wyh"
ZJY = ROOT / "All_Code" / "Q4" / "Q4_ZJY"
TABLES = WYH / "Results" / "Tables"


def hr(t):
    print("\n" + "=" * 84); print(t); print("=" * 84)


# ---- #2 B2 倍率 ----
hr("#2 B2 的结算倍率与命名")
src = (WYH / "Model_Establishment+Solution" / "validate_q4_2.py").read_text(encoding="utf-8")
m = re.search(r"def run_b2.*?return \{.*?\}", src, re.S)
print("  validate_q4_2.py::run_b2 关键行：")
for ln in (m.group(0).splitlines() if m else []):
    if "gap" in ln or "costs.append" in ln or "总费用" in ln:
        print("   ", ln.strip())
b = pd.read_csv(TABLES / "q4_2_baselines.csv", encoding="utf-8-sig")
print("\n  q4_2_baselines.csv：")
print(b.to_string(index=False))
b2 = float(b[b["方案"].str.startswith("B2")]["报告期总费用(元)"].iloc[0])
print(f"\n  B2 现值 = {b2:,.2f} 元；若按题目规则补 5 倍倍率 = {5*b2:,.2f} 元")
ex = pd.read_csv(TABLES / "q4_2_experiments.csv", encoding="utf-8-sig")
print("  q4_2_experiments.py 中的同源 B2 =",
      float(ex[ex["实验"].str.startswith("B2")]["总费用(元)"].iloc[0]), "（同一公式，需一并处理）")

# ---- #4 B0 命名与报表字段 ----
hr("#4 B0 字段与命名")
print("  validate_q4_2.py 中主模型行的增量字段写法：")
for ln in src.splitlines():
    if "bros = [" in ln or "bros.append" in ln:
        print("   ", ln.strip())
print("\n  q4_2_baselines.csv 的「较完美预见下界增量」列：")
print(b[["方案", "报告期总费用(元)", "较完美预见下界增量(元)"]].to_string(index=False))
mp = WYH / "others" / "03_Q4-2结果报告.md"
txt = mp.read_text(encoding="utf-8")
for kw in ["严格下界", "完美预见下界", "信息成本", "2,732,684.88", "不可避免"]:
    hits = [i + 1 for i, l in enumerate(txt.splitlines()) if kw in l]
    print(f"  报告 03_Q4-2结果报告.md 含「{kw}」的行号: {hits[:6]}")

# ---- #5 价格冷启动 ----
hr("#5 电价预测首日冷启动")
pf = pickle.load(open(WYH / "Data_processing" / "price_forecast.pkl", "rb"))
ds = pickle.load(open(WYH / "Data_processing" / "q4_dataset.pkl", "rb"))
ph, pr = np.asarray(pf["price_hat"], float), np.asarray(ds["price"], float)
for i in (0, 1, 2):
    print(f"  day{i}（{ds['date_str'][i]}）：max|预测−实际| = {np.max(np.abs(ph[:,i]-pr[:,i])):.6e}"
          f"；选中模型 = {pf['selection'].iloc[i]['selected']}")
sel = pf["selection"]
print("  selection 表 train_max_day_index 前 3 行：", sel["train_max_day_index"].head(3).tolist())
src2 = (WYH / "Data_processing" / "04_q4_price_forecast.py").read_text(encoding="utf-8")
for ln in src2.splitlines():
    if "fallback_mean" in ln:
        print("  代码行：", ln.strip())

# ---- #6 光伏预测源 ----
hr("#6 光伏预测源")
for f in sorted(TABLES.glob("V_*_summary.csv")):
    v = pd.read_csv(f, encoding="utf-8-sig").iloc[0]
    print(f"  {v['tag']:22s} pv={v['pv_source']:8s} price={v['price_mode']:8s} "
          f"总费用={v['report_total_cost']:,.2f}")

# ---- #7 报告期初始 SOC ----
hr("#7 报告期初始 SOC 口径")
for f in sorted(TABLES.glob("V_*_daily.csv")):
    d = pd.read_csv(f, encoding="utf-8-sig")
    print(f"  {f.name.replace('_daily.csv',''):22s} 2025-02-01 起点 SOC = {float(d['s0'].iloc[0]):.2f}")
m = pd.read_csv(TABLES / "q4_2_daily_rolling_log.csv", encoding="utf-8-sig")
print(f"  {'主口径(现行)':22s} 2025-02-01 起点 SOC = {float(m['s0'].iloc[0]):.2f}")
q3 = ROOT / "All_Code" / "Q3" / "Model_Establishment+Solution" / "run_q3.py"
if q3.exists():
    ls = q3.read_text(encoding="utf-8").splitlines()
    print("\n  Q3 run_q3.py 第 45-70 行：")
    for i in range(44, min(70, len(ls))):
        print(f"   {i+1:4d}| {ls[i]}")

# ---- #8 交付 ----
hr("#8 交付")
tex = ROOT / "Paper" / "10.Q4" / "content.tex"
print(f"  Paper/10.Q4/content.tex 存在={tex.exists()}，"
      f"字符数={len(tex.read_text(encoding='utf-8')) if tex.exists() else 0}")
zz = (ZJY / "Model_Establishment+Solution" / "q4_data.py").read_text(encoding="utf-8")
print("  Q4_ZJY/q4_data.py 仍声明「日前发布电价」:",
      any("日前发布电价" in l for l in zz.splitlines()))
print("  Q4_ZJY 目录最后修改时间:",
      max(p.stat().st_mtime for p in ZJY.rglob("*") if p.is_file()))
