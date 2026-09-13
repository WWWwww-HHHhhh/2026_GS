"""补充验证：紧急购电率口径、受控 2x2 数值、默认参数。只读。"""

import io
import os
import re
import pandas as pd

WS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q4W = os.path.join(WS, "All_Code", "Q4", "Q4_wyh")
T = os.path.join(Q4W, "Results", "Tables")
OUT = os.path.join(Q4W, "others", "_audit_readonly", "verify_round3.md")
L = []


def log(s=""):
    L.append(str(s))


def main():
    log("# 补充验证（紧急率口径 / 受控 2x2 / 默认参数）")
    log("")

    # 1 紧急购电率口径
    log("## 1 紧急购电率到底是多少（论文写“日均紧急购电率 0.63%”）")
    log("")
    fp = os.path.join(T, "q4_2_daily_rolling_log.csv")
    if os.path.exists(fp):
        d = pd.read_csv(fp)
        log("- 逐日日志列名：%s" % "、".join(d.columns))
        log("- 天数：%d" % len(d))
        ecol = next((c for c in d.columns if "emergency" in c.lower() and "kwh" in c.lower()), None)
        lcol = next((c for c in d.columns if c.lower() in ("load_kwh", "load", "demand_kwh")), None)
        log("- 紧急量列=%s，负荷列=%s" % (ecol, lcol))
        if ecol and lcol:
            te, tl = d[ecol].sum(), d[lcol].sum()
            log("- 全年紧急购电量 %.2f kWh，全年负荷 %.2f kWh" % (te, tl))
            log("- **口径A 全年之和的比值 = %.4f%%**" % (te / tl * 100))
            r = d[ecol] / d[lcol]
            log("- **口径B 逐日比值的平均 = %.4f%%**（中位数 %.4f%%）" % (r.mean() * 100, r.median() * 100))
    log("")

    # 2 受控 2x2
    log("## 2 受控 2x2 四格与派生量")
    log("")
    cells = {
        "价格未知 + 自建预报（主模型）": "V_q2_unknown_q2params_summary.csv",
        "价格已知 + 自建预报": "V_q2_known_q2params_summary.csv",
        "价格未知 + 附件3预报": "V_official_unknown_q2params_summary.csv",
        "价格已知 + 附件3预报": "V_official_known_q2params_summary.csv",
    }
    vals = {}
    for k, f in cells.items():
        fp = os.path.join(T, f)
        if not os.path.exists(fp):
            log("- `%s` 不存在" % f)
            continue
        df = pd.read_csv(fp)
        log("- **%s**（%s）" % (k, f))
        log("  列：%s" % "、".join(df.columns))
        log("```")
        log(df.to_string(index=False)[:700])
        log("```")
        # 猜测总费用列
        for c in df.columns:
            if "total" in c.lower():
                try:
                    vals[k] = float(df[c].iloc[0])
                except Exception:
                    pass
    log("")
    if len(vals) == 4:
        a = vals["价格未知 + 自建预报（主模型）"]
        b = vals["价格已知 + 自建预报"]
        c = vals["价格未知 + 附件3预报"]
        dd = vals["价格已知 + 附件3预报"]
        log("四格总费用（元）：主模型 %.2f，价格已知 %.2f，附件3 %.2f，附件3且价格已知 %.2f" % (a, b, c, dd))
        log("")
        log("- 价格信息价值（自建口径）= %.2f 元 = %.2f 万元 = %.2f%%" % (a - b, (a - b) / 1e4, (a - b) / a * 100))
        log("- 附件3预报代价（价格未知口径）= %.2f 元 = %.2f 万元 = %.2f%%" % (c - a, (c - a) / 1e4, (c - a) / a * 100))
        log("- 价格信息价值（附件3口径）= %.2f 元 = %.2f 万元 = %.2f%%" % (c - dd, (c - dd) / 1e4, (c - dd) / c * 100))
        log("- 附件3预报代价（价格已知口径）= %.2f 元 = %.2f 万元 = %.2f%%" % (dd - b, (dd - b) / 1e4, (dd - b) / b * 100))
        log("- 交互项 = (c-a) - (dd-b) = %.2f 元 = %.2f 万元" % ((c - a) - (dd - b), ((c - a) - (dd - b)) / 1e4))
    log("")

    # 3 默认参数
    log("## 3 q4_core.py 里的默认参数")
    log("")
    fp = os.path.join(Q4W, "Model_Establishment+Solution", "q4_core.py")
    if os.path.exists(fp):
        t = io.open(fp, encoding="utf-8", errors="replace").read().splitlines()
        hits = [(i, x.strip()) for i, x in enumerate(t, 1) if re.search(r"beta", x)]
        log("- 含 beta 的行 %d 条：" % len(hits))
        for i, x in hits[:12]:
            log("  - L%-4d %s" % (i, x[:140]))
    log("")
    fp2 = os.path.join(Q4W, "Model_Establishment+Solution", "q4_2_rolling.py")
    if os.path.exists(fp2):
        t = io.open(fp2, encoding="utf-8", errors="replace").read()
        m = re.search(r"BETA_CAND\s*=\s*[^\n]+", t)
        m2 = re.search(r"BASELINE\s*=\s*[^\n]+", t)
        log("- q4_2_rolling.py 候选与基线：%s | %s" % (m.group(0) if m else "?", m2.group(0) if m2 else "?"))
    log("")

    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L))
    print("report:", OUT)


if __name__ == "__main__":
    main()
