# -*- coding: utf-8 -*-
"""只读：比对"首日价格冷启动修复前后"的预热末 SOC（判定 #5 是否需要全链重跑）。"""
import pickle
import sys
from pathlib import Path

WYH = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q4\Q4_wyh")
res = pickle.load(open(WYH / "Data_processing" / "q4_2_rolling_results.pkl", "rb"))
full = res["full_logs"]
warm = [l for l in full if l["day_index"] <= 13]
tune = [l for l in full if 14 <= l["day_index"] <= 30]
print(f"[修复前] 预热段 {len(warm)} 天，day13 末 SOC = {warm[-1]['final_soc']:.6f} kWh")
print(f"[修复前] 调参段 {len(tune)} 天，day30 末 SOC = {tune[-1]['final_soc']:.6f} kWh")
print(f"[修复前] 报告期起点 SOC  = {res['report_logs'][0]['s0']:.6f} kWh")
print(f"[修复前] 报告期总费用    = {res['report_logs'] and sum(l['cost_total'] for l in res['report_logs']):,.2f} 元")
print("\n用法：重生成场景后再跑一次 q4_2_rolling.py --mode smoke，用其 '预热后 SOC' 与本文件对比。")
