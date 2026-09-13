# -*- coding: utf-8 -*-
"""result4-2.xlsx 与关键汇总的人工抽查（只读）。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
import pandas as pd, numpy as np, openpyxl

WYH = Path(__file__).resolve().parents[2]
wb = openpyxl.load_workbook(WYH / "Results" / "Tables" / "result4-2.xlsx")
print("sheets:", wb.sheetnames)
ws = wb["计划购电量"]
print("计划购电量 dims:", ws.dimensions, "max_row", ws.max_row, "max_col", ws.max_column)
hdr = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
print("表头前3:", hdr[:3], "… 表头末5:", hdr[-5:])
for r in (2, 3, 200, 335):
    vals = [ws.cell(r, c).value for c in list(range(1, 6)) + [143, 144, 145, 146, 147]]
    print(f"  行{r}: 日期={vals[0]} 前4值={[round(v,3) if isinstance(v,float) else v for v in vals[1:5]]} "
          f"… 末列区={[round(v,3) if isinstance(v,float) else v for v in vals[5:]]}")

ws2 = wb["充放电量"]
print("\n充放电量 dims:", ws2.dimensions)
for r in (1, 2, 3, 4, ws2.max_row):
    print(f"  行{r}:", [ws2.cell(r, c).value for c in range(1, 7)])

ws3 = wb["紧急购电量"]
print("\n紧急购电量 dims:", ws3.dimensions)
for r in range(1, 6):
    print(f"  行{r}:", [ws3.cell(r, c).value for c in range(1, 4)])
print("  末行:", [ws3.cell(ws3.max_row, c).value for c in range(1, 4)])

print("\n=== 月度汇总 ===")
m = pd.read_csv(WYH / "Results" / "Tables" / "q4_2_monthly_summary.csv", encoding="utf-8-sig")
print(m.to_string(index=False))

print("\n=== 实验（进行中的部分结果） ===")
p = WYH / "Results" / "Tables" / "q4_2_experiments.csv"
if p.exists():
    print(pd.read_csv(p, encoding="utf-8-sig").to_string(index=False))
else:
    print("尚未生成")

res = pd.read_csv(WYH / "Results" / "Tables" / "q4_2_daily_rolling_log.csv", encoding="utf-8-sig")
print("\n=== 费用最高的 5 天 ===")
print(res.nlargest(5, "cost_total")[["date", "cost_plan", "cost_emergency", "emergency_kwh",
                                     "plan_total_kwh", "load_kwh", "price_mean"]].to_string(index=False))
print("\n=== 费用最低的 5 天 ===")
print(res.nsmallest(5, "cost_total")[["date", "cost_plan", "cost_emergency", "plan_total_kwh",
                                      "load_kwh", "price_mean"]].to_string(index=False))
