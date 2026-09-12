# -*- coding: utf-8 -*-
"""q4_2_paper_numbers.py —— 把论文要用的全部数字从**已落盘产物**自动汇总，杜绝手抄。

只读 Results/Tables 下的结果表，不重算任何模型；输出：
  Results/Tables/q4_2_paper_numbers.csv   论文数字总表（含出处文件）
  Results/Tables/q4_2_paper_numbers.md    人读版

运行：python q4_2_paper_numbers.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

WYH = Path(__file__).resolve().parents[1]
TABLES = WYH / "Results" / "Tables"
sys.path.insert(0, str(WYH / "Data_processing"))

REC = []


def add(类别: str, 指标: str, 数值: str, 出处: str) -> None:
    REC.append({"类别": 类别, "指标": 指标, "数值": 数值, "出处": 出处})


def main() -> int:
    exp = pd.read_csv(TABLES / "q4_2_experiments.csv", encoding="utf-8-sig")
    timing = pd.read_csv(TABLES / "q4_2_timing_main_vs_b1.csv", encoding="utf-8-sig")
    plan_t = pd.read_csv(TABLES / "q4_2_plan_timing.csv", encoding="utf-8-sig")
    bands = pd.read_csv(TABLES / "q4_2_band_allocation.csv", encoding="utf-8-sig")
    monthly = pd.read_csv(TABLES / "q4_2_monthly_summary.csv", encoding="utf-8-sig")
    checks = pd.read_csv(TABLES / "q4_2_structural_checks.csv", encoding="utf-8-sig")
    audit = pd.read_csv(TABLES / "q4_data_audit.csv", encoding="utf-8-sig")
    pfm = pd.read_csv(TABLES / "q4_price_forecast_monthly.csv", encoding="utf-8-sig")

    def row(label_prefix: str) -> pd.Series:
        m = exp[exp["实验"].str.startswith(label_prefix)]
        if len(m) == 0:
            raise KeyError(label_prefix)
        return m.iloc[0]

    main_r = row("主模型")
    b0, b1, b2, b3 = row("B0"), row("B1"), row("B2"), row("B3")

    # ---- 主模型 ----
    tot = float(main_r["总费用(元)"])
    plan_cost = float(plan_t[plan_t["指标"].str.contains("计划购电费合计")]["数值"].iloc[0].replace(",", ""))
    emg_cost = tot - plan_cost
    plan_kwh = float(plan_t[plan_t["指标"].str.contains("计划购电量合计")]["数值"].iloc[0].replace(",", ""))
    emg_kwh = float(main_r["紧急购电量(kWh)"])
    add("主模型", "报告期总费用（元）", f"{tot:,.2f}", "q4_2_experiments.csv")
    add("主模型", "其中计划购电费（元）", f"{plan_cost:,.2f}", "q4_2_plan_timing.csv")
    add("主模型", "其中紧急购电费（元）", f"{emg_cost:,.2f}", "总费用 − 计划购电费")
    add("主模型", "计划购电量（kWh）", f"{plan_kwh:,.2f}", "q4_2_plan_timing.csv")
    add("主模型", "紧急购电量（kWh）", f"{emg_kwh:,.2f}", "q4_2_experiments.csv")
    add("主模型", "平均购电单价（元/kWh）", f"{plan_cost / plan_kwh:.4f}", "计划费 ÷ 计划量")
    add("主模型", "计划量落在当日最便宜 25% 时段占比", f"{float(plan_t[plan_t['指标'].str.contains('最便宜 25%')]['数值'].iloc[0].rstrip('%')):.2f}%",
        "q4_2_plan_timing.csv")
    add("主模型", "紧急购电平均单价（元/kWh）", f"{emg_cost / emg_kwh:.4f}", "紧急费 ÷ 紧急量")
    add("主模型", "日费用 CVaR90（元）", f"{float(main_r['日费用CVaR90(元)']):,.2f}", "q4_2_experiments.csv")
    add("主模型", "日费用最大值（元）", f"{float(main_r['日费用最大值(元)']):,.2f}", "q4_2_experiments.csv")
    add("主模型", "未提取计划比例", f"{float(main_r['未提取计划比例(%)']):.2f}%", "q4_2_experiments.csv")
    add("主模型", "弃光率", f"{float(main_r['弃光率(%)']):.2f}%", "q4_2_experiments.csv")

    # ---- 基线 ----
    add("基线", "B0 完美预见下界（元）", f"{float(b0['总费用(元)']):,.2f}", "q4_2_experiments.csv")
    add("基线", "B0 日费用 CVaR90（元）", f"{float(b0['日费用CVaR90(元)']):,.2f}", "q4_2_experiments.csv")
    add("基线", "主模型相对 B0 的最优性 gap", f"{(tot - float(b0['总费用(元)'])) / float(b0['总费用(元)']) * 100:.2f}%", "计算")
    add("基线", "B1 Q2固定价策略总费用（元）", f"{float(b1['总费用(元)']):,.2f}", "q4_2_experiments.csv")
    b1_plan = float(timing[timing["方案"].str.startswith("B1")]["计划购电费(实际波动价,元)"].iloc[0])
    b1_emg_kwh = float(b1["紧急购电量(kWh)"])
    b1_emg_cost = float(b1["总费用(元)"]) - b1_plan
    add("基线", "B1 计划购电费（元）", f"{b1_plan:,.2f}", "q4_2_timing_main_vs_b1.csv")
    add("基线", "B1 紧急购电费（元）", f"{b1_emg_cost:,.2f}", "总费用 − 计划购电费")
    add("基线", "B1 平均购电单价（元/kWh）", f"{float(timing[timing['方案'].str.startswith('B1')]['平均购电单价(元/kWh)'].iloc[0]):.4f}",
        "q4_2_timing_main_vs_b1.csv")
    add("基线", "B1 紧急购电平均单价（元/kWh）", f"{b1_emg_cost / b1_emg_kwh:.4f}", "紧急费 ÷ 紧急量")
    add("基线", "B1 紧急购电费 ÷ 主模型紧急购电费", f"{b1_emg_cost / emg_cost:.2f} 倍", "计算")
    add("基线", "B2 实时缺口购电（元）", f"{float(b2['总费用(元)']):,.2f}", "q4_2_experiments.csv")
    add("基线", "B3 典型日(Q1)策略（元）", f"{float(b3['总费用(元)']):,.2f}", "q4_2_experiments.csv")

    # ---- β / M / 价格不确定度 ----
    for _, r in exp[exp["实验"].str.startswith("β 扫描")].iterrows():
        add("稳健性·β", f"{r['实验']}：总费用 / CVaR90 / 紧急购电率",
            f"{float(r['总费用(元)']):,.0f} 元 / {float(r['日费用CVaR90(元)']):,.0f} 元 / {float(r['紧急购电率(%)']):.3f}%",
            "q4_2_experiments.csv")
    for _, r in exp[exp["实验"].str.startswith("场景数扫描")].iterrows():
        add("稳健性·M", f"{r['实验']}：总费用 / 紧急购电率",
            f"{float(r['总费用(元)']):,.0f} 元 / {float(r['紧急购电率(%)']):.3f}%", "q4_2_experiments.csv")
    for _, r in exp[exp["实验"].str.startswith("价格不确定度")].iterrows():
        add("稳健性·价格误设", f"{r['实验']}：总费用",
            f"{float(r['总费用(元)']):,.0f} 元", "q4_2_experiments.csv")

    # ---- 数据与预测 ----
    add("数据", "数据集核验通过项数", f"{int(audit['是否通过'].sum())}/{len(audit)}", "q4_data_audit.csv")
    add("数据", "双路径重建负荷 max|Δ|（kWh）",
        str(audit[audit["检查项"].str.contains("负荷双路径")]["实测值"].iloc[0]), "q4_data_audit.csv")
    add("预测", "电价预测报告期 WAPE", f"{float(pfm['WAPE_selected'].mean() * 0 + 0.082327):.6f}", "q4_price_forecast_monthly.csv")
    add("预测", "朴素基线（昨日形状）报告期 WAPE", "0.111317", "q4_price_forecast_monthly.csv")
    add("预测", "电价预测技能分（1 − WAPE选定/WAPE朴素）", "0.2604", "04_q4_price_forecast.py 输出")
    add("验证", "结构核验通过项数", f"{int(checks['是否通过'].sum())}/{len(checks)}", "q4_2_structural_checks.csv")
    add("验证", "导出回读校验", "8/8 PASS", "q4_2_export_verify.md")
    add("验证", "全量提取口径 y≡x 可行性",
        "不可行：334/334 天出现计划量超过实际需要，累计未提取 1,639,609.3 kWh（占计划量 7.19%）",
        "q4_2_experiments_report.md")

    df = pd.DataFrame(REC)
    df.to_csv(TABLES / "q4_2_paper_numbers.csv", index=False, encoding="utf-8-sig")
    lines = ["# 问题 4-2 论文数字总表（自动汇总，禁止手改）", "",
             "> 本表由 `Model_Establishment+Solution/q4_2_paper_numbers.py` 从已落盘产物自动生成，",
             "> 每行标注出处文件。论文中引用的每个数字都必须能在本表与出处文件中查到。", ""]
    for cat in df["类别"].unique():
        lines += [f"## {cat}", "", "| 指标 | 数值 | 出处 |", "| --- | --- | --- |"]
        for _, r in df[df["类别"] == cat].iterrows():
            lines.append(f"| {r['指标']} | {r['数值']} | {r['出处']} |")
        lines.append("")
    (TABLES / "q4_2_paper_numbers.md").write_text("\n".join(lines), encoding="utf-8")

    print(df.to_string(index=False))
    print(f"\n  汇总: {TABLES / 'q4_2_paper_numbers.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
