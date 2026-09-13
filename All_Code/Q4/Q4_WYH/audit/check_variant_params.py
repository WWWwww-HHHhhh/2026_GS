# -*- coding: utf-8 -*-
"""只读：规范解析各 V_*_summary.csv，列出关键参数与费用，判断受控性。"""
import csv
from pathlib import Path

T = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q4\Q4_wyh\Results\Tables")
KEYS = ["tag", "pv_source", "price_mode", "select_rule", "selected_M", "selected_beta",
        "selected_kappa_mult", "report_total_cost", "report_emergency_cost", "cvar90_daily"]
rows = []
for f in sorted(T.glob("V_*_summary.csv")):
    with open(f, encoding="utf-8-sig", newline="") as fh:
        r = next(csv.DictReader(fh))
    rows.append({k: r.get(k, "") for k in KEYS})
hdr = ["变体", "预报源", "价格口径", "选参规则", "M", "β", "κ倍数", "总费用(元)", "紧急费(元)", "CVaR90(元)"]
print(f"{hdr[0]:<26}{hdr[1]:<10}{hdr[2]:<9}{hdr[3]:<12}{hdr[4]:>4}{hdr[5]:>7}{hdr[6]:>7}{hdr[7]:>16}{hdr[8]:>15}{hdr[9]:>13}")
for r in rows:
    tot = float(r["report_total_cost"]) if r["report_total_cost"] else 0.0
    emg = float(r["report_emergency_cost"]) if r["report_emergency_cost"] else 0.0
    cv = float(r["cvar90_daily"]) if r["cvar90_daily"] else 0.0
    print(f"{r['tag']:<26}{r['pv_source']:<10}{r['price_mode']:<9}{r['select_rule']:<12}"
          f"{r['selected_M'] or '-':>4}{r['selected_beta'] or '-':>7}{r['selected_kappa_mult'] or '-':>7}"
          f"{tot:>16,.2f}{emg:>15,.2f}{cv:>13,.0f}")

print("\n=== 受控性检查：要比较「价格信息假设」，两侧的 M/β/κ 必须一致 ===")
base = {"tag": "主口径(现行, 已提交)", "pv_source": "q2", "price_mode": "unknown",
        "selected_M": "30", "selected_beta": "0.2", "selected_kappa_mult": "1.0",
        "report_total_cost": "15561929.837286433"}
pair = [r for r in rows if r["pv_source"] == "q2" and r["price_mode"] == "known"
        and r["select_rule"] == "legacy" and r["tag"].endswith("q2params")]
if pair:
    p = pair[0]
    same = all(p[k] == base[k] for k in ("selected_M", "selected_beta", "selected_kappa_mult"))
    print(f"  主口径    : M={base['selected_M']} β={base['selected_beta']} κ×{base['selected_kappa_mult']}"
          f"  {float(base['report_total_cost']):,.2f} 元  (pv={base['pv_source']}, price={base['price_mode']})")
    print(f"  {p['tag']}: M={p['selected_M']} β={p['selected_beta']} κ×{p['selected_kappa_mult']}"
          f"  {float(p['report_total_cost']):,.2f} 元  (pv={p['pv_source']}, price={p['price_mode']})")
    print(f"  → 参数是否完全一致: {same}" + ("" if same else "   ⚠️ 存在混杂，不能把差额全部归因于价格信息假设"))
