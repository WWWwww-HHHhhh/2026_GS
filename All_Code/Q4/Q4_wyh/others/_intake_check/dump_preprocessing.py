# -*- coding: utf-8 -*-
"""盘点 All_Code/Data_preprocessing 的清洗表与全局变换产物（只读）。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
import pandas as pd, numpy as np

HERE = Path(__file__).resolve().parent
WYH = HERE.parents[1]
PROJ = HERE.parents[3]
DP = PROJ / "All_Code" / "Data_preprocessing"
CLEAN = DP / "Data_clean"
TRANS = DP / "Data_transformation"

print("=" * 78); print("[A] Data_clean/*.csv"); print("=" * 78)
for p in sorted(CLEAN.glob("*.csv")):
    d = pd.read_csv(p)
    print(f"\n--- {p.name}: shape={d.shape}")
    print("    columns:", list(d.columns)[:8], "..." if d.shape[1] > 8 else "")
    print(d.head(3).iloc[:, :7].to_string())
    num = d.select_dtypes('number')
    if num.shape[1]:
        print(f"    数值列 min={num.min().min():.4f} max={num.max().max():.4f} NaN={int(num.isna().sum().sum())}")

print()
print("=" * 78); print("[B] Data_transformation/*.parquet"); print("=" * 78)
for p in sorted(TRANS.glob("*.parquet")):
    try:
        d = pd.read_parquet(p)
    except Exception as e:
        print(f"--- {p.name}: 读取失败 {e}")
        continue
    print(f"\n--- {p.name}: shape={d.shape}")
    print("    columns:", list(d.columns))
    print("    dtypes:", {c: str(t) for c, t in d.dtypes.items()})
    print(d.head(4).to_string())

print()
print("=" * 78); print("[C] time_map / template_map"); print("=" * 78)
for nm in ["time_map.csv", "template_map.csv"]:
    p = TRANS / nm
    if p.exists():
        d = pd.read_csv(p)
        print(f"\n--- {nm}: shape={d.shape} cols={list(d.columns)}")
        print(d.head(4).to_string())
        print("..."); print(d.tail(3).to_string())

print()
print("=" * 78); print("[D] df_* 关键量纲核对（kW -> kWh 是否已换算）"); print("=" * 78)
try:
    d = pd.read_parquet(TRANS / "df_load.parquet")
    print("df_load 描述:"); print(d.describe().T.to_string())
except Exception as e:
    print("df_load err", e)
