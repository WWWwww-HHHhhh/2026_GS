"""取外部输入（只读）：C题 PDF、附件、桌面两份核对清单。

外部路径可能被沙箱拒绝，脚本对每一项单独 try 并记录错误，最后写报告文件。
"""

import io
import os
import sys
import glob
import zipfile

DESK_CANDIDATES = [
    r"C:\Users\Lenovo\Desktop",
    r"C:\Users\Lenovo\OneDrive\Desktop",
    r"C:\Users\Lenovo\OneDrive\桌面",
]
CHECK_FILES = ["ZJY_Q4_3_核对清单.md", "WYH_Q4_2_核对清单.md"]
ZIP = r"D:\Program Files(微信)\缓存文件夹\xwechat_files\wxid_wu6lwfcaguhi22_a75e\msg\file\2026-09\CUMCM2026Problems.zip"
WS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
OUT = os.path.join(WS, "All_Code", "Q4", "Q4_wyh", "others", "_audit_readonly", "external_inputs_report.md")

L = []


def log(s=""):
    L.append(s)


def main():
    log("# 外部输入读取报告")
    log("")

    # 1 桌面核对清单
    log("## 1 桌面核对清单")
    log("")
    found = {}
    for d in DESK_CANDIDATES:
        log("- 桌面候选目录 `%s`：存在=%s" % (d, os.path.isdir(d)))
        if not os.path.isdir(d):
            continue
        try:
            names = os.listdir(d)
        except Exception as e:
            log("  - 列目录失败：%s" % e)
            continue
        log("  - 目录项 %d 个" % len(names))
        for f in CHECK_FILES:
            if f in names:
                found[f] = os.path.join(d, f)
        # 模糊匹配
        for n in names:
            if n.endswith(".md") and ("Q4" in n or "核对" in n):
                log("  - 相关 md：`%s`" % n)
    log("")
    for f, p in found.items():
        log("### %s" % f)
        log("")
        try:
            t = io.open(p, encoding="utf-8", errors="replace").read()
            log("路径：`%s`，%d 字符" % (p, len(t)))
            log("")
            log("```markdown")
            log(t)
            log("```")
        except Exception as e:
            log("读取失败：%s" % e)
        log("")

    # 2 问题 zip
    log("## 2 题目压缩包")
    log("")
    log("- 路径存在=%s" % os.path.exists(ZIP))
    if os.path.exists(ZIP):
        try:
            with zipfile.ZipFile(ZIP) as z:
                items = z.infolist()
                log("- 条目 %d 个，压缩包 %.2f MB" % (len(items), os.path.getsize(ZIP) / 1048576))
                log("")
                log("| 条目 | 未压缩大小 |")
                log("| --- | --- |")
                for it in items:
                    try:
                        nm = it.filename.encode("cp437").decode("gbk")
                    except Exception:
                        nm = it.filename
                    log("| `%s` | %d B |" % (nm, it.file_size))
        except Exception as e:
            log("- 打开失败：%s" % e)
    log("")

    # 3 工作区内已有的原始附件
    log("## 3 工作区内已有的原始附件")
    log("")
    pats = [
        os.path.join(WS, "All_Code", "Q4", "Q4_wyh", "others", "原始附件_CUMCM2026_C"),
        os.path.join(WS, "Data"),
        os.path.join(WS, "Data", "附件"),
    ]
    for p in pats:
        log("- `%s`：存在=%s" % (os.path.relpath(p, WS) if p.startswith(WS) else p, os.path.exists(p)))
        if os.path.isdir(p):
            for root, _d, files in os.walk(p):
                for f in sorted(files)[:40]:
                    fp = os.path.join(root, f)
                    log("  - `%s`  %d B" % (os.path.relpath(fp, WS), os.path.getsize(fp)))
    log("")

    # 4 PDF 文本库可用性
    log("## 4 PDF 文本提取能力")
    log("")
    for cand in ["pypdf", "PyPDF2", "pdfplumber", "fitz", "pdfminer"]:
        try:
            mod = __import__(cand)
            log("- `%s`：可用（%s）" % (cand, getattr(mod, "__version__", "?")))
        except Exception as e:
            log("- `%s`：不可用（%s）" % (cand, type(e).__name__))
    log("")
    log("- python: %s" % sys.version.replace("\n", " "))

    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L))
    print("report:", OUT)


if __name__ == "__main__":
    main()
