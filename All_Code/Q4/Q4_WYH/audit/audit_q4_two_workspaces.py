# -*- coding: utf-8 -*-
"""Q4 双工作区只读审计取证（本次审计新增；不修改、不导入、不运行任何模型代码）。

只做两件事：
  1. 读 Q4_wyh 已落盘结果，检查物理自洽性（同时充放电、同时紧急购电与弃电、弃光/溢流量级等）；
  2. 读 Q4_ZJY 已落盘产物（电价矩阵缓存、summary/daily、result4-3.xlsx），检查数据贴合度与
     工作簿结构一致性。
不写任何模型产物，仅在 Results/Tables 之外打印结论。

运行：python audit_q4_two_workspaces.py
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS")
WYH = ROOT / "All_Code" / "Q4" / "Q4_wyh"
ZJY = ROOT / "All_Code" / "Q4" / "Q4_ZJY"
T, D = 144, 365


def hr(t: str) -> None:
    print("\n" + "=" * 82)
    print(t)
    print("=" * 82)


# ============================================================ A. Q4_wyh 物理自洽性
hr("A. Q4_wyh（问题4-2）已落盘结果的物理自洽性")
res = pickle.load(open(WYH / "Data_processing" / "q4_2_rolling_results.pkl", "rb"))
logs = res["report_logs"]
n_cr = n_esp = 0
max_x = 0.0
tot_curt = tot_pv = tot_spill = tot_emg = tot_plan = 0.0
for l in logs:
    c = np.asarray(l["plan_c"]); r = np.asarray(l["plan_r"])
    e = np.asarray(l["settle_e"]); sp = np.asarray(l["settle_spill"]); w = np.asarray(l["settle_w"])
    x = np.asarray(l["plan_x"])
    n_cr += int(np.sum((c > 1e-6) & (r > 1e-6)))
    n_esp += int(np.sum((e > 1e-6) & (sp > 1e-6)))
    max_x = max(max_x, float(x.max()))
    tot_curt += float(w.sum()); tot_spill += float(sp.sum()); tot_emg += float(e.sum())
    tot_plan += float(x.sum()); tot_pv += float(np.asarray(l["pv_actual"]).sum())
print(f"  同时充电与放电的时段数            = {n_cr}   （应为 0）")
print(f"  同一时段既有紧急购电又有弃电      = {n_esp}   （应为 0）")
print(f"  单时段最大计划购电量              = {max_x:.2f} kWh/10min = {max_x*6:.0f} kW")
print(f"  计划购电量合计 / 紧急购电量合计    = {tot_plan:,.1f} / {tot_emg:,.1f} kWh")
print(f"  弃光量 / 光伏实际总量             = {tot_curt:,.1f} / {tot_pv:,.1f} kWh = {tot_curt/tot_pv*100:.2f}%")
print(f"  供给过剩弃电量(spill)             = {tot_spill:,.1f} kWh")

# ============================================================ B. Q4_ZJY 电价矩阵贴合度
hr("B. Q4_ZJY 电价矩阵缓存 vs 附件4（数据贴合度）")
npy = ZJY / "Data_processing" / "q4_price_matrix.npy"
p_zjy = np.load(npy)
df_price = pd.read_parquet(ROOT / "All_Code" / "Data_preprocessing" / "Data_transformation" / "df_price.parquet")
T_COLS = [f"T{i:03d}" for i in range(1, T + 1)]
p_ref = df_price[T_COLS].to_numpy(float).T
print(f"  ZJY 缓存 shape={p_zjy.shape}；参考(parquet) shape={p_ref.shape}")
if p_zjy.shape == p_ref.shape:
    dv = float(np.max(np.abs(p_zjy - p_ref)))
    print(f"  逐元素最大差 = {dv:.3e}  →  {'完全一致（数据贴合）' if dv == 0 else '不一致'}")
    print(f"  均值 ZJY={p_zjy.mean():.6f}  参考={p_ref.mean():.6f}；"
          f"范围 ZJY=[{p_zjy.min():.4f},{p_zjy.max():.4f}]")

my = pickle.load(open(WYH / "Data_processing" / "q4_dataset.pkl", "rb"))
p_my = np.asarray(my["price"], float)
print(f"  Q4_wyh 数据集电价 shape={p_my.shape}；与参考最大差={float(np.max(np.abs(p_my-p_ref))):.3e}")

# ============================================================ C. Q4_ZJY 结果一致性
hr("C. Q4_ZJY 已落盘结果的自洽性")
summary = pd.read_csv(ZJY / "Results" / "Tables" / "strategy_summary.csv")
print(summary[["strategy", "plan_cost_yuan", "adjustment_cost_yuan", "market_cost_yuan",
               "emergency_cost_yuan", "total_cost_yuan", "emergency_kwh", "curtail_kwh",
               "simultaneous_charge_discharge_count"]].to_string(index=False))
for _, r in summary.iterrows():
    s = r["strategy"]
    daily = pd.read_csv(ZJY / "Results" / "Tables" / s / "daily.csv")
    sj = json.loads((ZJY / "Results" / "Tables" / s / "summary.json").read_text(encoding="utf-8"))
    col = "total_cost_yuan" if "total_cost_yuan" in daily.columns else daily.columns[-1]
    dsum = float(pd.to_numeric(daily[col], errors="coerce").sum())
    print(f"  {s:6s} daily.csv 行数={len(daily):4d} Σ{col}={dsum:,.2f}  "
          f"summary.total={r['total_cost_yuan']:,.2f}  Δ={dsum - r['total_cost_yuan']:+.2f}  "
          f"json.total={sj.get('total_cost_yuan', float('nan')):,.2f}")

# ============================================================ D. Q4_ZJY 工作簿结构
hr("D. Q4_ZJY result4-3.xlsx 结构（只读）")
import openpyxl
wb = openpyxl.load_workbook(ZJY / "Results" / "Tables" / "result4-3.xlsx", data_only=True)
print("  sheets:", wb.sheetnames)
for name in wb.sheetnames:
    ws = wb[name]
    print(f"  [{name}] dims={ws.dimensions} max_row={ws.max_row} max_col={ws.max_column}")
ws1 = wb["计划购电量"]
hdr = [ws1.cell(1, c).value for c in range(1, ws1.max_column + 1)]
print("  计划表头首3:", hdr[:3], "末5:", hdr[-5:])
for r in (2, ws1.max_row):
    vals = [ws1.cell(r, c).value for c in list(range(1, 4)) + [143, 144, 145, 146, 147]]
    print(f"  行{r}: 日期={vals[0]} 前2值={[round(v,3) if isinstance(v,float) else v for v in vals[1:3]]}"
          f" 末区={[round(v,3) if isinstance(v,float) else v for v in vals[3:]]}")
if "调整购电量" in wb.sheetnames:
    ws2 = wb["调整购电量"]
    print("  调整表 max_row/max_col =", ws2.max_row, ws2.max_column)
ws3 = wb["紧急购电量"]
esum = float(np.nansum([ws3.cell(r, 3).value or 0 for r in range(2, ws3.max_row + 1)]))
print(f"  紧急购电表行数={ws3.max_row-1}（事件数） Σ购电量={esum:,.2f} kWh")
print(f"  S6_12 summary 紧急购电量={float(summary[summary.strategy=='S6_12']['emergency_kwh'].iloc[0]):,.2f} kWh")
ws4 = wb["充放电量"]
print(f"  充放电表行数={ws4.max_row-1}（应为 334×6={334*6}）")

# ============================================================ E. Q4_wyh 计划购电功率峰值贴合度
hr("E. Q4_wyh 计划购电的等效功率峰值（与小区规模贴合度）")
peak_load_kw = float(np.max(my["load"]) * 6)          # 附件2 负载峰值（kWh/10min × 6 = kW）
pk = []
for l in logs:
    x = np.asarray(l["plan_x"], float)
    t = int(np.argmax(x))
    pk.append((l["date"], t, float(x.max()) * 6.0))
pk_df = pd.DataFrame(pk, columns=["date", "slot", "plan_kw"])
print(f"  附件2 全年负载峰值                     = {peak_load_kw:,.2f} kW")
print(f"  计划购电等效功率峰值（全年最高）        = {pk_df['plan_kw'].max():,.1f} kW")
print(f"  超过全年负载峰值的时段数                = {int((pk_df['plan_kw'] > peak_load_kw).sum())} / 334 天")
print(f"  超过 5000 kW（储能功率上限）的天数       = {int((pk_df['plan_kw'] > 5000).sum())} / 334 天")
print("  等效功率峰值最高的 5 天：")
print(pk_df.nlargest(5, "plan_kw").to_string(index=False))
unext = float(sum(l["unextracted_kwh"] for l in logs))
print(f"\n  全年未提取计划电量 = {unext:,.1f} kWh，按平均购电单价 0.6433 元/kWh 计"
      f"≈ {unext * 0.6433:,.0f} 元（已付费但未使用）")

# ============================================================ F. 两边 SOC 终端口径对照
hr("F. SOC 终端口径对照（Q4_wyh 软终端 vs Q4_ZJY 日末回日初）")
dmy = pd.read_csv(WYH / "Results" / "Tables" / "q4_2_daily_rolling_log.csv", encoding="utf-8-sig")
dmy["dsoc"] = dmy["final_soc"] - dmy["s0"]
print(f"  Q4_wyh：每日 |24:00 − 0:00| SOC 最大偏离 = {dmy['dsoc'].abs().max():.6f} kWh；"
      f"偏离 >1 kWh 的天数 = {int((dmy['dsoc'].abs() > 1).sum())}/334")
print(f"          偏离绝对值均值 = {dmy['dsoc'].abs().mean():.6f} kWh")

rows = []
for r in range(2, ws4.max_row + 1):
    if ws4.cell(r, 1).value is not None and ws4.cell(r, 6).value is not None:
        s0d = ws4.cell(r, 6).value
        s24 = ws4.cell(r + 1, 6).value if r + 1 <= ws4.max_row else None
        rows.append((str(ws4.cell(r, 1).value)[:10], s0d, s24))
z = pd.DataFrame(rows, columns=["date", "soc_0000", "soc_2400"])
z["dsoc"] = pd.to_numeric(z["soc_2400"], errors="coerce") - pd.to_numeric(z["soc_0000"], errors="coerce")
print(f"  Q4_ZJY：result4-3.xlsx 充放电表可解析 {len(z)} 天；"
      f"每日 |24:00 − 0:00| 最大偏离 = {z['dsoc'].abs().max():.6f} kWh；"
      f"偏离 >1 kWh 的天数 = {int((z['dsoc'].abs() > 1).sum())}/{len(z)}")
