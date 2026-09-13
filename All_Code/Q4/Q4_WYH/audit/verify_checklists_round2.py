"""按两份桌面核对清单逐条验证当前仓库状态（只读）。

输出：_audit_readonly/verify_checklists_round2.md
"""

import io
import os
import re
import glob
import pandas as pd

WS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q4W = os.path.join(WS, "All_Code", "Q4", "Q4_wyh")
Q4Z = os.path.join(WS, "All_Code", "Q4", "Q4_ZJY")
PAPER = os.path.join(WS, "Paper", "10.Q4", "content.tex")
TEMPL = os.path.join(Q4W, "others", "原始附件_CUMCM2026_C", "附件", "附件5")
OUT = os.path.join(Q4W, "others", "_audit_readonly", "verify_checklists_round2.md")

L = []


def log(s=""):
    L.append(str(s))


def grep(path, pats, limit=6):
    if not os.path.exists(path):
        return ["（文件不存在：%s）" % os.path.relpath(path, WS)]
    t = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
    out = []
    for i, line in enumerate(t, 1):
        for p in pats:
            if re.search(p, line):
                out.append("L%-4d %s" % (i, line.strip()[:150]))
                break
        if len(out) >= limit:
            break
    return out or ["（未命中）"]


def main():
    log("# 桌面两份核对清单的逐条复验（当前仓库状态）")
    log("")
    paper = io.open(PAPER, encoding="utf-8", errors="replace").read() if os.path.exists(PAPER) else ""

    # ---------- 1 代码事实 ----------
    log("## 1 代码事实")
    log("")
    log("### 1.1 q4_2_rolling.py 是否在问题四重新标定参数（清单 P0-1）")
    for x in grep(os.path.join(Q4W, "Model_Establishment+Solution", "q4_2_rolling.py"),
                  [r"候选", r"product", r"beta", r"kappa", r"M_LIST|M_list|Ms\b", r"标定|tuning|搜索|grid"], 14):
        log("- %s" % x)
    log("")
    log("### 1.2 q4_core.py 的 beta 默认值（清单 P2-1）")
    for x in grep(os.path.join(Q4W, "Model_Establishment+Solution", "q4_core.py"),
                  [r"def .*beta", r"beta\s*=\s*0\.", r"beta.*:.*float"], 8):
        log("- %s" % x)
    log("")
    log("### 1.3 价格场景下界（清单 ZJY P1-3）")
    log("- Q4_wyh 侧：")
    for f in ["Model_Establishment+Solution/q4_core.py", "Data_processing/05_q4_scenarios.py"]:
        for x in grep(os.path.join(Q4W, f.replace("/", os.sep)), [r"1e-6", r"0\.0076", r"price_min", r"floor", r"clip"], 4):
            log("  - `%s` %s" % (f, x))
    log("- Q4_ZJY 侧：")
    for x in grep(os.path.join(Q4Z, "Model_Establishment+Solution", "q4_price_core.py"),
                  [r"1e-6", r"0\.0076", r"floor", r"clip", r"tariff_energy"], 8):
        log("  - %s" % x)
    log("")
    log("### 1.4 导出与校验脚本的默认策略（清单 ZJY P1-4）")
    for name in ["export_result4.py", "prepare_result4.py", "validate_result4_workbook.py"]:
        log("- `%s`：" % name)
        for x in grep(os.path.join(Q4Z, "Model_Establishment+Solution", name), [r"S6_12", r"Sall", r"default"], 5):
            log("  - %s" % x)
    log("")
    log("### 1.5 日内重算是否使用当日已实现价格（清单 ZJY P0-2）")
    for x in grep(os.path.join(Q4Z, "Model_Establishment+Solution", "run_q4.py"),
                  [r"price\[.*:\s*\d", r"realized", r"actual", r"已实现", r"forecast\[", r"hat", r"pred"], 12):
        log("- %s" % x)
    log("")

    # ---------- 2 工作簿结构 ----------
    log("## 2 工作簿结构与附件5模板对照")
    log("")
    pairs = [("result4-2.xlsx", os.path.join(Q4W, "Results", "Tables", "result4-2.xlsx")),
             ("result4-3.xlsx", os.path.join(Q4Z, "Results", "Tables", "result4-3.xlsx")),
             ("模板 result2.xlsx", os.path.join(TEMPL, "result2.xlsx")),
             ("模板 result3.xlsx", os.path.join(TEMPL, "result3.xlsx"))]
    for label, fp in pairs:
        log("### %s" % label)
        log("")
        if not os.path.exists(fp):
            log("- 文件不存在：`%s`" % fp)
            log("")
            continue
        try:
            sheets = pd.read_excel(fp, sheet_name=None, header=None, nrows=6)
            log("- 大小 %d B，工作表 %d 个：%s" % (os.path.getsize(fp), len(sheets), "、".join(sheets.keys())))
            for sn, df in sheets.items():
                log("  - `%s`：形状（前6行）%s" % (sn, df.shape))
                head = df.head(3).fillna("").astype(str).values.tolist()
                for r in head:
                    log("    - %s" % " | ".join(x[:14] for x in r[:9]))
        except Exception as e:
            log("- 读取失败：%s: %s" % (type(e).__name__, e))
        log("")

    # ---------- 3 论文数字复核 ----------
    log("## 3 论文数字复核")
    log("")
    ss = os.path.join(Q4Z, "Results", "Tables", "strategy_summary.csv")
    if os.path.exists(ss):
        d = pd.read_csv(ss)
        log("### 3.1 六策略表分项与合计的四舍五入（清单 ZJY P2-1）")
        log("")
        log("| 策略 | 市场费(万元) | 紧急费(万元) | 分项和 | 总费用(万元) | 差 |")
        log("| --- | --- | --- | --- | --- | --- |")
        for _, r in d.iterrows():
            mk = round(r["market_cost_yuan"] / 1e4, 2)
            em = round(r["emergency_cost_yuan"] / 1e4, 2)
            tt = round(r["total_cost_yuan"] / 1e4, 2)
            log("| %s | %.2f | %.2f | %.2f | %.2f | %+.2f |" % (r["strategy"], mk, em, mk + em, tt, mk + em - tt))
        log("")
        log("### 3.2 S0→Sall 的费用构成变化（清单 ZJY P1-1）")
        log("")
        s0 = d[d.strategy == "S0"].iloc[0]
        sa = d[d.strategy == "Sall"].iloc[0]
        dm = s0["market_cost_yuan"] - sa["market_cost_yuan"]
        de = s0["emergency_cost_yuan"] - sa["emergency_cost_yuan"]
        dt = s0["total_cost_yuan"] - sa["total_cost_yuan"]
        log("- 市场费用减少 %.2f 元（占 %.1f%%）" % (dm, dm / dt * 100))
        log("- 紧急费用减少 %.2f 元（占 %.1f%%）" % (de, de / dt * 100))
        log("- 合计减少 %.2f 元" % dt)
        log("")
    log("### 3.3 论文中该段原话")
    for line in paper.splitlines():
        if "节省几乎全部" in line or "日均紧急购电率" in line or "不再对问题四重新选参" in line or "更新同时消化" in line:
            log("- `%s`" % line.strip()[:150])
    log("")

    # ---------- 4 价格与净负荷 ----------
    log("## 4 价格—净负荷关系（清单 ZJY P1-2 的因果解释能否成立）")
    log("")
    for name in ["q4_2_plan_timing.csv", "q4_2_band_allocation.csv", "q4_2_timing_main_vs_b1.csv"]:
        fp = os.path.join(Q4W, "Results", "Tables", name)
        log("### %s" % name)
        log("")
        if os.path.exists(fp):
            try:
                df = pd.read_csv(fp)
                log("```")
                log(df.to_string(index=False)[:1600])
                log("```")
            except Exception as e:
                log("- 读取失败：%s" % e)
        else:
            log("- 不存在")
        log("")

    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L))
    print("report:", OUT)


if __name__ == "__main__":
    main()
