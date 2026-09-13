# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np
from pathlib import Path

ROOT = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\Data\raw\CUMCM2026_C")

pv   = pd.read_excel(ROOT/"附件/附件2.xlsx", sheet_name="光伏发电实际功率", header=None)
price= pd.read_excel(ROOT/"附件/附件4.xlsx", sheet_name=0, header=None)

pv_num = pv.iloc[1:, 1:].apply(pd.to_numeric, errors='coerce').to_numpy()
pr_num = price.iloc[1:, 1:].apply(pd.to_numeric, errors='coerce').to_numpy()

print("pv rows:", pv_num.shape, "price rows:", pr_num.shape)
print("pv[0,0..2] =", pv_num[0,:3], " price[0,0..2] =", pr_num[0,:3])
print("pv[2,0..2] =", pv_num[2,:3], " price[2,0..2] =", pr_num[2,:3])
print("equal? ", np.array_equal(pv_num[2,:3], pr_num[2,:3]))

ratio = [(np.abs(pv_num[i] - pr_num[i]) < 1e-12).mean() for i in range(pv_num.shape[0])]
ratio = np.array(ratio)
print("\nper-DAY identical-ratio vs price: first 6 days:", np.round(ratio[:6],3))
print("days with ratio>0.99:", int((ratio>0.99).sum()), "of", len(ratio))
print("days with ratio<0.01:", int((ratio<0.01).sum()))

print("\nper-DAY identical-ratio vs LOAD:")
load = pd.read_excel(ROOT/"附件/附件2.xlsx", sheet_name="小区负载", header=None)
lo_num = load.iloc[1:, 1:].apply(pd.to_numeric, errors='coerce').to_numpy()
r2 = np.array([(np.abs(pv_num[i]-lo_num[i])<1e-12).mean() for i in range(len(ratio))])
print(np.round(r2[:6],3), "days>0.99:", int((r2>0.99).sum()))

print("\nPV row 2025-01-01 (first 20):", np.round(pv_num[0,:20],4))
print("PV row 2025-01-01 (cols 50-70):", np.round(pv_num[0,50:70],4))
print("PV row 2025-01-02 (cols 45-60):", np.round(pv_num[1,45:60],4))
print("PR row 2025-01-02 (cols 45-60):", np.round(pr_num[1,45:60],4))

print("\nPV row max over year per day (first 10 days):", np.round(np.nanmax(pv_num,axis=1)[:10],2))
print("PV row max over year per day (last 5 days):", np.round(np.nanmax(pv_num,axis=1)[-5:],2))
print("PV global max:", np.nanmax(pv_num))
print("columns where PV==price on day index 2:", int((np.abs(pv_num[2]-pr_num[2])<1e-12).sum()))
