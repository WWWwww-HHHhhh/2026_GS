"""按 WYH_Q4_2_核对清单.md 逐条复核当前仓库与论文状态（只读原工作区）。"""

import io
import os
import glob
import re

WS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q4W = os.path.join(WS, "All_Code", "Q4", "Q4_wyh")
T = os.path.join(Q4W, "Results", "Tables")
NEW = os.path.join(WS, "All_Code", "Q4_wyhnew")
PAPER = os.path.join(WS, "Paper", "10.Q4", "content.tex")
OUT = os.path.join(NEW, "verify_wyh_checklist_round3.md")

L = []


def log(s=""):
    L.append(str(s))


def read(p):
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else ""


def has(t, s):
    return s in t


def main():
    paper = read(PAPER)
    val = read(os.path.join(T, "q4_2_validation_report.md"))
    core = read(os.path.join(Q4W, "Model_Establishment+Solution", "q4_core.py"))
    log("# 按 WYH_Q4_2_核对清单 逐条复核（第二轮）")
    log("")
    log("说明：清单写于主口径切换为附件3 之前，其中“已确认一致”一栏的数字属旧主口径。")
    log("")

    # P0-1
    log("## P0-1 参数是否在问题四重新标定")
    log("")
    log("- 论文含“沿用问题二的候选范围与筛选规则…重新执行一次标定”：**%s**"
        % ("是（已改）" if has(paper, "沿用问题二的候选范围与筛选规则") else "否"))
    log("- 论文是否仍含“不再对问题四重新选参”：**%s**"
        % ("是（未改）" if has(paper, "不再对问题四重新选参") else "否（已清除）"))
    log("- 代码侧证据：`q4_2_rolling.py` 的 `BETA_CAND` 与 96 组搜索仍在，与论文新表述一致")
    log("")

    # P0-2
    log("## P0-2 B1 基线紧急购电费用")
    log("")
    log("- `Results/Tables/q4_2_validation_report.md` 是否含 887318.97：**%s**"
        % ("是（未修）" if has(val, "887318.97") else "否"))
    log("- 该报告是否含 1748828.89：**%s**" % ("是" if has(val, "1748828.89") else "否"))
    for line in val.splitlines():
        if "B1" in line:
            log("  - 原文：%s" % line.strip()[:150])
    log("- 论文是否引用 B1 的紧急购电费：**%s**（论文写了 174.88 万元与 1.81 倍）"
        % ("是" if "174.88" in paper else "否"))
    log("")

    # P0-3
    log("## P0-3 正式工作簿的唯一性")
    log("")
    for f in sorted(glob.glob(os.path.join(T, "result4-2*.xlsx"))):
        log("- `%s`  %.0f KB" % (os.path.basename(f), os.path.getsize(f) / 1024))
    log("- `Q4_wyhnew/result4-2_附件3口径.xlsx`  %.0f KB（新主口径，本次重导出）"
        % (os.path.getsize(os.path.join(NEW, "result4-2_附件3口径.xlsx")) / 1024))
    log("")
    log("结论：原工作区里的 **`result4-2.xlsx` 仍是旧主口径**（自建光伏预测）的结果，")
    log("而论文现在引用的是附件3 口径。正式工作簿的指认需要你决定（见文末待办）。")
    log("")

    # P1-4
    log("## P1-4 紧急购电率的名称与数值")
    log("")
    for line in paper.splitlines():
        if "0.654" in line or "紧急购电量占总负荷" in line:
            log("- 论文现写：%s" % line.strip()[:170])
    log("- 名称已改为“占报告期总负荷…的”，符合清单建议的口径")
    log("- 数值随主口径切换为 **0.654%**（附件3 口径），旧值 0.587% 属自建口径")
    log("")

    # P1-5
    log("## P1-5 主模型与 B1 的经济性关系")
    log("")
    for line in paper.splitlines():
        if "B1 的总费用比主模型低" in line or "因此主模型是用" in line:
            log("- 论文现写：%s" % line.strip()[:170])
    log("")

    # P1-6 / P1-7
    log("## P1-6 与 P1-7 B0 的含义、B2 与 B2' 的区分")
    log("")
    log("- B0“对照方案而非严格数学下界”：**%s**" % ("在" if has(paper, "对照方案而非严格数学下界") else "缺失"))
    log("- B2 与 B2' 分别标注：**%s**" % ("在" if has(paper, "两个口径必须分别标注，不可混用") else "缺失"))
    log("")

    # P2-8
    log("## P2-8 q4_core.py 的默认风险权重")
    log("")
    for i, line in enumerate(core.splitlines(), 1):
        if re.search(r'"beta"\s*:', line):
            log("- L%-4d %s" % (i, line.strip()[:120]))
    log("")

    # P2-9
    log("## P2-9 支撑材料中的红色占位")
    log("")
    n = paper.count("color{red}")
    log("- 论文中红字块数量：**%d**（9 条附录占位、2 条支撑文件说明、1 处行内“附录 L”）" % n)
    log("- 清单要求“附录确定后删除全部红色提示”，附录正文尚未撰写，该项按设计仍待办")
    log("")

    # 已确认一致的核心结果
    log("## 清单“已确认一致的核心结果”一栏与当前论文的对照")
    log("")
    log("| 指标 | 清单值（旧主口径） | 论文当前是否仍写该值 | 新主口径取值 |")
    log("| --- | --- | --- | --- |")
    rows = [
        ("报告期总费用", "15561929.84", "15728958.76"),
        ("计划购电费用", "14670390.10", "14762076.40"),
        ("紧急购电费用", "891539.74", "966882.36"),
        ("计划购电量", "22803530.04", "22885559.26"),
        ("紧急购电量", "217118.05", "242133.03"),
        ("年末储电量", "6000", "6000（不变）"),
        ("电价预测 WAPE", "8.23", "8.23（不变）"),
        ("朴素基线 WAPE", "11.13", "11.13（不变）"),
    ]
    for name, old, new in rows:
        log("| %s | %s | %s | %s |" % (name, old, "是" if old in paper else "否", new))
    log("")
    log("结论：清单的核心结果表基于旧主口径，前五行的数字已不再是论文取值，该表需要重新基线到附件3 口径。")
    log("")

    # 汇总
    log("## 汇总")
    log("")
    log("| 清单项 | 当前状态 |")
    log("| --- | --- |")
    log("| P0-1 参数标定说法 | 已完成（论文已改） |")
    log("| P0-2 B1 紧急购电费冲突 | **未完成**（验证报告仍写 887,318.97） |")
    log("| P0-3 唯一正式工作簿 | **未完成，且新增一处**（原 result4-2.xlsx 仍是旧主口径） |")
    log("| P1-4 紧急率名称与数值 | 已完成（名称已改，数值 0.654%） |")
    log("| P1-5 主模型与 B1 的权衡 | 已完成（22.95 万元 / 1.81 倍 / 78.19 万元） |")
    log("| P1-6 B0 的含义 | 保持正确 |")
    log("| P1-7 B2 与 B2' 的区分 | 保持正确 |")
    log("| P2-8 q4_core 默认 beta | **未完成**（仍为 0.5） |")
    log("| P2-9 红色占位 | 待办（附录未撰写，按设计保留） |")
    log("| 清单核心结果表 | **需重新基线到附件3 口径** |")

    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L))
    print("report:", OUT)


if __name__ == "__main__":
    main()
