"""只读审计：Q4 的图与文档是否与官方结果对齐（陈旧资产排查）。

输出报告：同目录下 audit_q4_stale_assets.md（UTF-8，便于阅读）

检查内容
  A 时间线：图文件与官方结果文件的修改时间对比
  B 生成脚本的数据源：图是从哪张表/哪个文件画出来的
  C 工作文档里的旧版数字残留（HANDOVER 一系）
  D 论文 Q4 正文数字与官方 strategy_summary.csv 的逐项对照
  E （若环境有 PDF 文本库）直接读出图里的数字，判定新旧
"""

import io
import os
import re
import csv
import time
import glob
import subprocess

BASE = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q4W = os.path.join(BASE, "All_Code", "Q4", "Q4_wyh")
Q4Z = os.path.join(BASE, "All_Code", "Q4", "Q4_ZJY")
PAPER = os.path.join(BASE, "Paper", "10.Q4", "content.tex")
OUT = os.path.join(Q4W, "others", "_audit_readonly", "audit_q4_stale_assets.md")

# 官方结果（来自 Q4_ZJY/Results/Tables/strategy_summary.csv，单位 元）
OFFICIAL = {
    "S0": 15746005.832569197, "S6": 15511017.444025595, "S12": 15526460.89371447,
    "S18": 15753029.392939035, "S6_12": 15358037.803259166, "Sall": 15355290.646485314,
}
# 截图里指出的旧版数字（万元）
STALE_WAN = ["1549.9", "1531.4", "1527.8", "1513.7", "1513.72"]
STALE_SEARCH = ["1513.72", "1513.7", "1531.4", "1527.8", "1549.9", "HANDOVER", "q4_fig2", "q4_fig3"]


def mt(p):
    return time.strftime("%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p)))


def walk_files(root, exts):
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if os.path.splitext(f)[1].lower() in exts:
                fp = os.path.join(dirpath, f)
                out.append(fp)
    return out


def main():
    L = []
    L.append("# Q4 陈旧资产审计（只读）")
    L.append("")
    L.append("生成时间：" + time.strftime("%Y-%m-%d %H:%M:%S"))
    L.append("")

    # ---------- A 时间线 ----------
    L.append("## A 时间线：图文件 vs 官方结果文件")
    L.append("")
    L.append("注意：本仓库刚做过 git reset，被重写的文件修改时间会变成 reset 时刻，因此时间只能作为参考，不能单独定性。")
    L.append("")
    L.append("### A1 问题四第三问（队友工作区）的图")
    L.append("")
    L.append("| 文件 | 修改时间 | 大小 |")
    L.append("| --- | --- | --- |")
    pics = sorted(walk_files(os.path.join(Q4Z, "Results", "Pictures"), {".pdf", ".png", ".svg"}))
    for p in pics:
        L.append("| %s | %s | %d B |" % (os.path.relpath(p, Q4Z), mt(p), os.path.getsize(p)))
    L.append("")
    L.append("### A2 问题四第三问的官方结果")
    L.append("")
    L.append("| 文件 | 修改时间 | 大小 |")
    L.append("| --- | --- | --- |")
    for rel in ["Results/Tables/strategy_summary.csv", "Results/Tables/run_metadata.json",
                "Results/Tables/validation_report.json", "Results/Tables/result4-3.xlsx",
                "Results/Tables/Sall/summary.json", "Results/Tables/Sall/daily.csv"]:
        fp = os.path.join(Q4Z, rel.replace("/", os.sep))
        if os.path.exists(fp):
            L.append("| %s | %s | %d B |" % (rel, mt(fp), os.path.getsize(fp)))
    L.append("")
    L.append("### A3 问题四第二问（本工作区）的图与官方结果")
    L.append("")
    L.append("| 文件 | 修改时间 | 大小 |")
    L.append("| --- | --- | --- |")
    for p in sorted(walk_files(os.path.join(Q4W, "Results", "Pictures"), {".pdf"})):
        L.append("| Pictures/%s | %s | %d B |" % (os.path.basename(p), mt(p), os.path.getsize(p)))
    for rel in ["Results/Tables/result4-2.xlsx", "Results/Tables/q4_2_daily_rolling_log.csv",
                "Results/Tables/q4_2_experiments.csv", "Results/Tables/q4_2_paper_numbers.csv",
                "Data_processing/q4_2_rolling_results.pkl"]:
        fp = os.path.join(Q4W, rel.replace("/", os.sep))
        if os.path.exists(fp):
            L.append("| %s | %s | %d B |" % (rel, mt(fp), os.path.getsize(fp)))
    L.append("")

    # ---------- B 生成脚本的数据源 ----------
    L.append("## B 图脚本读的是什么数据")
    L.append("")
    for rel in [("Q4_ZJY", os.path.join(Q4Z, "Model_Establishment+Solution", "make_q4_figures.py")),
                ("Q4_wyh", os.path.join(Q4W, "Results", "Pictures", "make_figures_q4_2.py"))]:
        name, fp = rel
        L.append("### %s 的 %s" % (name, os.path.basename(fp)))
        L.append("")
        if not os.path.exists(fp):
            L.append("（脚本不存在）")
            L.append("")
            continue
        t = io.open(fp, encoding="utf-8", errors="replace").read()
        pats = re.findall(r"(read_csv|read_json|read_excel|read_pickle|load\(|json\.load|open\()\s*\(?[^\n)]{0,120}", t)
        L.append("```")
        for x in pats[:40]:
            L.append(x.strip())
        L.append("```")
        paths = re.findall(r"[\"']([^\"'\n]*\.(?:csv|json|xlsx|pkl|npy))[\"']", t)
        L.append("脚本里出现的输入文件名：")
        L.append("")
        for x in sorted(set(paths)):
            L.append("- `%s`" % x)
        L.append("")

    # ---------- C 旧版数字残留 ----------
    L.append("## C 工作文档里的旧版数字与 HANDOVER 引用（残留排查）")
    L.append("")
    hits = 0
    scan = walk_files(Q4W, {".md", ".py", ".txt"}) + walk_files(Q4Z, {".md", ".py"})
    for fp in sorted(scan):
        if os.path.basename(fp).startswith("audit_q4_stale_assets"):
            continue
        try:
            t = io.open(fp, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if "color{red}" in t:
            continue
        for i, line in enumerate(t.splitlines(), 1):
            for k in STALE_SEARCH:
                if k in line:
                    hits += 1
                    L.append("- `%s` L%d 命中 `%s`：%s" % (os.path.relpath(fp, BASE), i, k, line.strip()[:130]))
                    break
    if not hits:
        L.append("（无命中）")
    L.append("")

    # ---------- D 论文数字对照 ----------
    L.append("## D 论文 Q4 正文数字 vs 官方结果")
    L.append("")
    PAPER_EXISTS = os.path.exists(PAPER)
    if PAPER_EXISTS:
        paper = io.open(PAPER, encoding="utf-8").read()
        L.append("官方六策略（万元，来自 strategy_summary.csv）与论文引用对照：")
        L.append("")
        L.append("| 策略 | 官方(万元) | 论文是否出现该数字 |")
        L.append("| --- | --- | --- |")
        for k, v in OFFICIAL.items():
            wan = "%.2f" % (v / 10000.0)
            L.append("| %s | %s | %s |" % (k, wan, "是" if wan in paper else "否"))
        L.append("")
        L.append("旧版数字是否出现在论文正文：")
        L.append("")
        for s in STALE_WAN:
            L.append("- `%s`：%s" % (s, "出现（需处理）" if s in paper else "未出现（正常）"))
        L.append("")
        # 派生量复核
        s0, sall, s18, s612 = OFFICIAL["S0"], OFFICIAL["Sall"], OFFICIAL["S18"], OFFICIAL["S6_12"]
        L.append("派生量复核：")
        L.append("")
        L.append("- 更新价值 S0−Sall = %.2f 元 = %.2f 万元，降幅 %.2f%%，论文写 39.07 万元与 2.48%%" %
                 (s0 - sall, (s0 - sall) / 10000, (s0 - sall) / s0 * 100))
        L.append("- S18−S0 = %.2f 元 = %.2f 万元，论文写比 S0 高 0.70 万元" % (s18 - s0, (s18 - s0) / 10000))
        L.append("- S6,12−Sall = %.2f 元 = %.2f 万元，占 %.4f%%，论文写 0.27 万元与 0.018%%" %
                 (s612 - sall, (s612 - sall) / 10000, (s612 - sall) / sall * 100))
        L.append("")

    # ---------- E 直接读图里的数字 ----------
    L.append("## E 直接读取图中的数字（判定新旧）")
    L.append("")
    lib = None
    for cand in ["pypdf", "PyPDF2", "pdfplumber", "fitz"]:
        try:
            __import__(cand)
            lib = cand
            break
        except Exception:
            pass
    L.append("可用 PDF 文本库：%s" % (lib or "无"))
    L.append("")
    if lib:
        figs = [p for p in pics if p.lower().endswith(".pdf")]
        for fp in figs:
            try:
                if lib == "pypdf":
                    from pypdf import PdfReader
                    txt = "\n".join((pg.extract_text() or "") for pg in PdfReader(fp).pages)
                elif lib == "PyPDF2":
                    from PyPDF2 import PdfReader
                    txt = "\n".join((pg.extract_text() or "") for pg in PdfReader(fp).pages)
                elif lib == "pdfplumber":
                    import pdfplumber
                    with pdfplumber.open(fp) as pdf:
                        txt = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
                else:
                    import fitz
                    doc = fitz.open(fp)
                    txt = "\n".join(pg.get_text() for pg in doc)
            except Exception as e:
                L.append("- `%s` 读取失败：%s" % (os.path.basename(fp), e))
                continue
            nums = re.findall(r"\d+\.\d", txt.replace(",", ""))
            L.append("- `%s`：抓到数字 %s" % (os.path.basename(fp), ", ".join(sorted(set(nums))[:14]) or "（无）"))
        L.append("")

    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L))
    print("report written:", OUT)


if __name__ == "__main__":
    main()
