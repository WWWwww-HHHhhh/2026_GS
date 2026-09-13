# -*- coding: utf-8 -*-
"""查看 Q2_yy 已产出的数据集与预测，确认可复用的口径。"""
import sys, io, pickle
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PROJ = HERE.parents[3]
Q2 = PROJ / "All_Code" / "Q2_yy"

for rel in ["Data_processing/q2_dataset.pkl", "Data_processing/forecasts.pkl", "Data_processing/q2_rolling_results.pkl"]:
    p = Q2 / rel
    print("=" * 78); print(rel, "exists:", p.exists(), f"{p.stat().st_size/1e6:.2f} MB" if p.exists() else "")
    if not p.exists():
        continue
    with open(p, "rb") as f:
        obj = pickle.load(f)
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, np.ndarray):
                print(f"  {k:24s} ndarray{v.shape} {v.dtype}  min={np.nanmin(v):.4f} max={np.nanmax(v):.4f} mean={np.nanmean(v):.4f}")
            elif isinstance(v, (list, tuple)):
                print(f"  {k:24s} {type(v).__name__}[{len(v)}] head={list(v[:3])}")
            else:
                print(f"  {k:24s} {type(v).__name__} = {v}")
    else:
        print("  type:", type(obj), obj if not hasattr(obj, 'shape') else f"shape={obj.shape}")

print()
print("=" * 78); print("q2_dataset / forecasts 的日期轴核对")
with open(Q2 / "Data_processing" / "q2_dataset.pkl", "rb") as f:
    ds = pickle.load(f)
d = [str(x) for x in ds["date_str"]]
print("  date_str: n =", len(d), "first:", d[:2], "last:", d[-2:])
print("  price/load/pv shape:", ds["price"].shape)
