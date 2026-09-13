# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np
from pathlib import Path

ROOT = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\Data\raw\CUMCM2026_C")

load = pd.read_excel(ROOT/"附件/附件2.xlsx", sheet_name="小区负载", header=None)
pv   = pd.read_excel(ROOT/"附件/附件2.xlsx", sheet_name="光伏发电实际功率", header=None)
price= pd.read_excel(ROOT/"附件/附件4.xlsx", sheet_name=0, header=None)

print("shapes:", load.shape, pv.shape, price.shape)
hdr = list(price.iloc[0, :6]) + ["..."] + list(price.iloc[0, -4:])
print("附件4 header:", hdr)

p_num = price.iloc[1:, 1:].apply(pd.to_numeric, errors='coerce').to_numpy()
v_num = pv.iloc[1:, 1:].apply(pd.to_numeric, errors='coerce').to_numpy()
l_num = load.iloc[1:, 1:].apply(pd.to_numeric, errors='coerce').to_numpy()

print("\n== 附件4 vs 附件2_光伏 逐元素 ==  ")
diff = np.abs(p_num - v_num)
print("identical element count:", int((diff < 1e-12).sum()), "/", diff.size)
print("max abs diff:", np.nanmax(diff))
# which columns are identical?
col_ident = [(diff[:, j] < 1e-12).mean() for j in range(diff.shape[1])]
print("per-column identical-ratio, first 10:", [round(x, 3) for x in col_ident[:10]])
print("per-column identical-ratio, last 10:", [round(x, 3) for x in col_ident[-10:]])
print("columns with ratio==1:", sum(1 for x in col_ident if x == 1))

print("\n== 附件4 数值范围（按列，前5列 / 后5列）==")
for j in [0, 1, 2, 3, 4, 140, 141, 142, 143]:
    c = p_num[:, j]
    print(f"  col{j+1:>3} ({price.iloc[0, j+1]}): min={np.nanmin(c):.4f} max={np.nanmax(c):.4f} mean={np.nanmean(c):.4f}")

print("\n== 附件4 vs 附件2_负载 相同元素比例 ==", float((np.abs(p_num - l_num) < 1e-12).mean()))

print("\n== 附件4 全行示例 2025-01-03 ==")
print(price.iloc[3, :12].to_list())
print(price.iloc[3, -6:].to_list())

print("\n== 附件4 全年每小时均值曲线（用整点列）==")
print("时间列前12:", price.iloc[0, 1:13].to_list())

print("\n== 附件2 光伏 全年 ==  行数(日):", pv.shape[0]-1, " 附件4 行数:", price.shape[0]-1)
print("附件2 首日:", pv.iloc[1, 0], " 末日:", pv.iloc[-1, 0])
print("附件4 首日:", price.iloc[1, 0], " 末日:", price.iloc[-1, 0])
print("附件4 是否有重复日期:", price.iloc[1:, 0].duplicated().any())
print("附件4 是否有缺失值:", int(pd.isna(p_num).sum()))
