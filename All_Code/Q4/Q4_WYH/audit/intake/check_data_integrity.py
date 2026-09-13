# -*- coding: utf-8 -*-
"""Q4 入场数据核验（只读）：官方附件指纹 + 结构与量纲核对。
运行： python check_data_integrity.py
"""
import sys, io, hashlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WYH = HERE.parents[1]                      # .../Q4/Q4_wyh
RAW = WYH / "others" / "原始附件_CUMCM2026_C" / "附件"
PROJ_ATT = HERE.parents[3] / "Data" / "附件"   # 项目原有 Data/附件（Q1-Q3 使用）


def sha(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


print("=" * 78)
print("[1] 官方附件指纹一致性（Q4_wyh/others vs 项目 Data/附件）")
print("=" * 78)
files = ["附件1.xlsx", "附件2.xlsx", "附件3.xlsx", "附件4.xlsx"]
for f in files:
    a, b = RAW / f, PROJ_ATT / f
    ok = a.exists() and b.exists() and sha(a) == sha(b)
    print(f"  {f:<12} {'OK  ' if ok else 'DIFF'}  {sha(a)[:16] if a.exists() else 'missing'}")

print()
print("=" * 78)
print("[2] 附件1（题目给定单日曲线：电价/负载/光伏）")
print("=" * 78)
a1 = pd.read_excel(RAW / "附件1.xlsx", sheet_name=0)
print("  shape:", a1.shape, " columns:", list(a1.columns))
print(a1.head(3).to_string())
print(a1.tail(2).to_string())
for c in a1.columns[1:]:
    v = pd.to_numeric(a1[c], errors='coerce')
    print(f"  {c:<10} min={v.min():.4f} max={v.max():.4f} mean={v.mean():.4f} NaN={int(v.isna().sum())}")

print()
print("=" * 78)
print("[3] 附件2（全年 365 天 × 144 个 10min 时段）")
print("=" * 78)
for sh, scale_hint in [("小区负载", "kW"), ("光伏发电实际功率", "kW")]:
    d = pd.read_excel(RAW / "附件2.xlsx", sheet_name=sh, header=None)
    num = d.iloc[1:, 1:].apply(pd.to_numeric, errors='coerce').to_numpy()
    print(f"  [{sh}] shape={d.shape} 日期 {d.iloc[1,0]} ~ {d.iloc[-1,0]}")
    print(f"      全域 min={np.nanmin(num):.4f} max={np.nanmax(num):.2f} "
          f"mean={np.nanmean(num):.2f} NaN={int(np.isnan(num).sum())}")
    dmax = np.nanmax(num, axis=1)
    print(f"      单日最大值 top5 天: {sorted(np.round(dmax,1), reverse=True)[:5]}")
    print(f"      单日最大值最低5天: {sorted(np.round(dmax,1))[:5]}")

print()
print("=" * 78)
print("[4] 附件4（全年 365 天 × 144 时段电价，元/kWh）== Q4 的关键新增")
print("=" * 78)
a4 = pd.read_excel(RAW / "附件4.xlsx", sheet_name=0, header=None)
pr = a4.iloc[1:, 1:].apply(pd.to_numeric, errors='coerce').to_numpy()
print(f"  shape={a4.shape} 日期 {a4.iloc[1,0]} ~ {a4.iloc[-1,0]}")
print(f"  全域 min={np.nanmin(pr):.4f} max={np.nanmax(pr):.4f} mean={np.nanmean(pr):.4f} "
      f"std={np.nanstd(pr):.4f} NaN={int(np.isnan(pr).sum())}")
print(f"  负电价个数={int((pr < 0).sum())}  低于0.1元个数={int((pr < 0.1).sum())}  高于1.0元个数={int((pr > 1.0).sum())}")
day_mean = np.nanmean(pr, axis=1)
print(f"  单日均价 min={day_mean.min():.4f} max={day_mean.max():.4f}")
print(f"  日内价差(峰谷差) 全年 min={np.nanmin(np.nanmax(pr,1)-np.nanmin(pr,1)):.4f} "
      f"max={np.nanmax(np.nanmax(pr,1)-np.nanmin(pr,1)):.4f}")
print("  首日 00:10-01:00:", np.round(pr[0, :6], 4))
print("  首日 11:00-13:00:", np.round(pr[0, 66:78], 4))
# 与附件2 光伏/负载是否存在同值污染（排查数据陷阱）
pv = pd.read_excel(RAW / "附件2.xlsx", sheet_name="光伏发电实际功率", header=None)
pv_n = pv.iloc[1:, 1:].apply(pd.to_numeric, errors='coerce').to_numpy()
same_pv = float((np.abs(pv_n - pr) < 1e-12).mean())
print(f"  附件4 与 附件2光伏 逐元素相同比例 = {same_pv:.6f}（应为 0，非 0 即有串行风险）")
print(f"  附件4 与 附件1 电价列是否一致: {np.allclose(np.sort(pr[0]), np.sort(pd.to_numeric(a1.iloc[:,1],errors='coerce').to_numpy()))}")

print()
print("=" * 78)
print("[5] 附件3（每日 0/6/12/18 时发布的未来24h整点光伏预报）")
print("=" * 78)
a3 = pd.read_excel(RAW / "附件3.xlsx", sheet_name=0, header=None, nrows=6)
print("  shape(前6行):", a3.shape)
print(a3.to_string())

print()
print("=" * 78)
print("[6] 附件5 模板（result4-2 / result4-3 是待填模板）")
print("=" * 78)
for f in ["result2.xlsx", "result4-2.xlsx", "result3.xlsx", "result4-3.xlsx"]:
    p = RAW / "附件5" / f
    xl = pd.ExcelFile(p)
    print(f"  {f}: sheets={xl.sheet_names}")
    for sh in xl.sheet_names:
        d = xl.parse(sh, header=None)
        filled = d.iloc[1:, 1:].apply(pd.to_numeric, errors='coerce').notna().sum().sum() if d.shape[1] > 1 else 0
        print(f"      [{sh}] shape={d.shape} 已填数值格数={int(filled)}")
print(f"  result4-2 与 result2 内容相同? {sha(RAW/'附件5'/'result4-2.xlsx') == sha(RAW/'附件5'/'result2.xlsx')}")
