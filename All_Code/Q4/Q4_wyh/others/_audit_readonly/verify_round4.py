"""追查论文里 0.63% 这个紧急购电率的来源。只读。"""

import io
import os
import glob
import pandas as pd

WS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
T = os.path.join(WS, "All_Code", "Q4", "Q4_wyh", "Results", "Tables")
OUT = os.path.join(WS, "All_Code", "Q4", "Q4_wyh", "others", "_audit_readonly", "verify_round4.md")
L = []


def log(s=""):
    L.append(str(s))


def main():
    log("# 追查 0.63% 的来源")
    log("")

    log("## 1 q4_2_paper_numbers.csv 里与紧急购电率有关的行")
    log("")
    fp = os.path.join(T, "q4_2_paper_numbers.csv")
    t = io.open(fp, encoding="utf-8-sig").read()
    for line in t.splitlines():
        if ("紧急" in line and "率" in line) or "0.63" in line or "0.59" in line or "0.58" in line:
            log("- %s" % line.strip()[:170])
    log("")

    log("## 2 q4_2_experiments.csv 的紧急购电率列")
    log("")
    d = pd.read_csv(os.path.join(T, "q4_2_experiments.csv"))
    cols = [c for c in d.columns if "率" in c or "rate" in c.lower()]
    log("- 率相关列：%s" % "、".join(cols))
    if cols:
        log("```")
        log(d[[d.columns[0]] + cols].to_string(index=False))
        log("```")
    log("")

    log("## 3 全部 V_* 汇总文件与它们的总费用")
    log("")
    log("| 文件 | 总费用(元) | 紧急购电率(%) |")
    log("| --- | --- | --- |")
    for f in sorted(glob.glob(os.path.join(T, "V_*summary*.csv"))):
        df = pd.read_csv(f)
        tot = [x for x in df.columns if "total" in x.lower()]
        rate = [x for x in df.columns if "rate" in x.lower()]
        log("| %s | %s | %s |" % (
            os.path.basename(f),
            ("%.2f" % float(df[tot[0]].iloc[0])) if tot else "?",
            ("%.3f" % float(df[rate[0]].iloc[0])) if rate else "?",
        ))
    log("")

    log("## 4 主模型那一格（价格未知 + 自建预报）的文件名")
    log("")
    for f in sorted(glob.glob(os.path.join(T, "V_*q2*"))):
        log("- `%s`" % os.path.basename(f))
    log("")

    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L))
    print("report:", OUT)


if __name__ == "__main__":
    main()
