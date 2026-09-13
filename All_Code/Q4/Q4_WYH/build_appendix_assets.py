"""建立 附件汇总 目录，按附录归档素材，写索引，并对新初稿做格式自检。"""

import io
import os
import re
import shutil

NEW = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(NEW, "..", "..", ".."))
T = os.path.join(NEW, "Results", "Tables")
PIC = os.path.join(NEW, "Results", "Pictures")
AGG = os.path.join(NEW, "附件汇总")
DRAFT = os.path.join(WS, "Paper", "10.Q4", "content.tex")

# 附录 -> [(源文件相对 Results 的路径, 说明, 口径状态)]
PLAN = {
    "K": [
        ("Tables/q4_2_settlement_R1_vs_R2.csv", "两种结算口径的逐日对照（R1 按结算时刻实际价，R2 按零点预测价）", "口径无关"),
    ],
    "L": [
        ("Pictures/fig_q4_price_forecast.pdf", "图 L-1 逐日均价与日内形状分位", "口径无关"),
        ("Pictures/fig_q4_price_forecast.png", "图 L-1 的预览图", "口径无关"),
        ("Tables/q4_price_forecast_monthly.csv", "表 L-1 逐月预测精度", "口径无关"),
        ("Tables/q4_price_forecast_selection.csv", "表 L-2 候选模型逐日选择记录", "口径无关"),
        ("Tables/q4_price_forecast_report.md", "预测精度与选择规则的文字记录", "口径无关"),
    ],
    "M": [
        ("Pictures/fig_q4_scenario_fan.pdf", "图 M-1 三维联合场景扇形图", "待按新主口径重绘"),
        ("Pictures/fig_q4_scenario_fan.png", "图 M-1 的预览图", "待按新主口径重绘"),
        ("Tables/q4_scenario_diagnostics_q2.csv", "表 M-1 自建预测源下的场景诊断", "对照口径"),
        ("Tables/q4_scenario_diagnostics_official.csv", "表 M-2 附件3 预报源下的场景诊断", "新主口径"),
        ("Tables/q4_scenario_report_official.md", "附件3 源场景的文字诊断", "新主口径"),
        ("Tables/q4_scenario_report_q2.md", "自建源场景的文字诊断", "对照口径"),
    ],
    "N": [
        ("Tables/q4_2_tuning_sensitivity.xlsx", "表 N-2 标定期参数扫描记录", "对照口径"),
        ("Tables/V_official_unknown_q2params_summary.csv", "受控四格之一（附件3 加价格未知）的选参结果", "新主口径"),
        ("Tables/V_official_known_q2params_summary.csv", "受控四格之一（附件3 加价格已知）", "对照"),
        ("Tables/V_q2_known_q2params_summary.csv", "受控四格之一（自建预测加价格已知）", "对照"),
    ],
    "O": [
        ("Tables/q4_2_structural_checks.csv", "表 O-1 结构核验残差（旧口径跑批）", "旧口径，需按新主口径复核"),
        ("Tables/q4_2_plan_timing.csv", "表 O-2 择时指标（旧口径）", "旧口径，新口径数值见 official_cell_numbers.md"),
        ("Tables/q4_2_band_allocation.csv", "分价格档的未提取与紧急购电分布（旧口径）", "旧口径，需重算"),
        ("Tables/q4_2_export_verify.md", "工作簿导出回读校验记录", "旧口径对应旧工作簿"),
    ],
    "P": [
        ("Pictures/fig_q4_frontier_baseline.pdf", "图 P-1 风险与成本曲线及基线对比", "含旧口径主模型点，需更新"),
        ("Pictures/fig_q4_frontier_baseline.png", "图 P-1 的预览图", "同上"),
        ("Pictures/fig_q4_main_vs_b1_cost_structure.pdf", "图 P-2 主模型与 B1 的费用结构对比", "待按新主口径重绘"),
        ("Pictures/fig_q4_main_vs_b1_cost_structure.png", "图 P-2 的预览图", "待按新主口径重绘"),
        ("Tables/q4_2_baselines.csv", "表 P-1 基线汇总", "B0 与 B2 系列口径无关，B1 相对关系已更新"),
        ("Tables/q4_2_fig_main_vs_b1_data.csv", "表 P-2 费用结构作图数据", "待按新主口径重算"),
        ("Tables/q4_2_timing_main_vs_b1.csv", "主模型与 B1 的择时对比", "待按新主口径重算"),
    ],
    "Q": [
        ("Tables/q4_2_experiments.csv", "表 Q-2 反事实实验矩阵（风险权重、场景数、不确定度注入）", "自建预测口径，正文已注明同组内比较"),
        ("Tables/V_cap8000_summary.csv", "表 Q-3 联络线容量对照", "对照口径"),
        ("Tables/V_official_unknown_q2params_summary.csv", "表 Q-1 受控四格中的主口径格", "新主口径"),
        ("Tables/V_official_known_q2params_summary.csv", "表 Q-1 受控四格之二", "对照"),
        ("Tables/V_q2_known_q2params_summary.csv", "表 Q-1 受控四格之三", "对照"),
        ("Tables/V_q2_unknown_risk_summary.csv", "表 Q-1 相关格（风险感知选参）", "对照"),
        ("official_cell_numbers.md", "新主口径全部论文用数与新旧对照", "新主口径"),
        ("official_cell_numbers.csv", "同上，表格形式", "新主口径"),
        ("Results/Tables/result4-2.xlsx", "唯一正式结果工作簿（附件3 口径）", "新主口径"),
        ("Results/Tables/口径说明.md", "各结果表所属口径的逐项说明", "说明文件"),
    ],
}


def main():
    os.makedirs(AGG, exist_ok=True)
    lines = ["# 附件汇总索引", "",
             "本目录按附录归档可供附录使用的图与表。口径状态一栏标明该素材属于新主口径、对照口径还是需要重生成，",
             "附录定稿时按该栏决定是否直接引用或先重算。" , ""]
    copied = 0
    for app, items in PLAN.items():
        d = os.path.join(AGG, app)
        os.makedirs(d, exist_ok=True)
        lines += ["## 附录 %s" % app, "", "| 文件 | 说明 | 口径状态 |", "| --- | --- | --- |"]
        for rel, desc, status in items:
            cands = [os.path.join(NEW, rel.replace("/", os.sep)),
                     os.path.join(NEW, "Results", rel.replace("/", os.sep))]
            src = next((c for c in cands if os.path.exists(c)), None)
            if src:
                dst = os.path.join(d, os.path.basename(rel))
                shutil.copy2(src, dst)
                copied += 1
                lines.append("| `%s/%s` | %s | %s |" % (app, os.path.basename(rel), desc, status))
            else:
                lines.append("| `%s`（缺失） | %s | %s |" % (rel, desc, status))
        lines.append("")
    io.open(os.path.join(AGG, "索引.md"), "w", encoding="utf-8", newline="").write("\n".join(lines) + "\n")
    print("附件汇总：复制 %d 个文件，索引已写入 附件汇总/索引.md" % copied)

    # 格式自检
    t = io.open(DRAFT, encoding="utf-8").read()
    body = re.sub(r"\\textcolor\{red\}\{[^}]*\}", "", t)
    checks = [
        ("中文分号", body.count("；")),
        ("破折号", body.count("——")),
        ("半角分号", body.count(";")),
        ("公式后紧跟句号", len(re.findall(r"\\end\{equation\}\s*\n\s*。", t))),
        ("标题层级超过 subsubsection", len(re.findall(r"\\(paragraph|subparagraph)\{", t))),
        ("红字占位", t.count("color{red}")),
        ("表格环境", t.count("\\begin{table}")),
        ("图环境", t.count("\\begin{figure}")),
        ("公式环境", t.count("\\begin{equation}")),
        ("字符数", len(t)),
        ("行数", t.count("\n") + 1),
    ]
    print("\n初稿自检：")
    for k, v in checks:
        print("   %-26s %s" % (k, v))


if __name__ == "__main__":
    main()
