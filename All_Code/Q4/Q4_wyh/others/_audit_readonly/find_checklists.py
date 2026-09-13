"""定位桌面上的两份核对清单（只读，探测沙箱可读范围）。"""

import io
import os

TARGETS = ["ZJY_Q4_3_核对清单.md", "WYH_Q4_2_核对清单.md"]
ROOTS = [
    r"C:\Users\Lenovo",
    r"C:\Users\Lenovo\Desktop",
    r"C:\Users\Lenovo\OneDrive",
    r"C:\Users\Lenovo\OneDrive\Desktop",
    r"C:\Users\Lenovo\OneDrive\桌面",
    r"C:\Users\Lenovo\OneDrive - ",
    r"C:\Users\Public\Desktop",
    r"C:\Users\Lenovo\Documents",
    r"C:\Users\Lenovo\Downloads",
    "D:" + "\\",
    "C:" + "\\",
]
WS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
OUT = os.path.join(WS, "All_Code", "Q4", "Q4_wyh", "others", "_audit_readonly", "find_checklists.md")

L = []


def log(s=""):
    L.append(s)


def probe(p, depth=0, maxdepth=2):
    try:
        entries = os.listdir(p)
    except Exception as e:
        log("%s- `%s`：无法读取（%s: %s）" % ("  " * depth, p, type(e).__name__, e))
        return []
    log("%s- `%s`：可读，%d 项" % ("  " * depth, p, len(entries)))
    hits = []
    for n in sorted(entries):
        if n in TARGETS:
            hits.append(os.path.join(p, n))
            log("%s  * 命中 `%s`" % ("  " * depth, n))
    if depth < maxdepth:
        for n in sorted(entries):
            fp = os.path.join(p, n)
            if os.path.isdir(fp) and not n.startswith(".") and n.lower() not in ("appdata", "application data", "cookies", "local settings", "my documents", "netbeans", "printhood", "recent", "sendto", "templates", "开始菜单"):
                hits += probe(fp, depth + 1, maxdepth)
    return hits


def main():
    log("# 桌面核对清单定位报告")
    log("")
    log("## 探测各候选根目录")
    log("")
    found = []
    for r in ROOTS:
        if r.endswith("OneDrive - "):
            try:
                base = r"C:\Users\Lenovo"
                for n in os.listdir(base):
                    if n.startswith("OneDrive"):
                        found += probe(os.path.join(base, n), 0, 2)
            except Exception as e:
                log("- OneDrive 变体探测失败：%s" % e)
            continue
        if os.path.exists(r):
            found += probe(r, 0, 2)
        else:
            log("- `%s`：不存在或不可读（isdir=%s, isfile=%s）" % (r, os.path.isdir(r), os.path.isfile(r)))
    log("")
    log("## 命中结果")
    log("")
    if not found:
        log("（未找到目标文件）")
    for p in found:
        log("- `%s`  %d B" % (p, os.path.getsize(p)))
    log("")
    log("## 命中文件内容")
    log("")
    for p in found:
        log("### %s" % os.path.basename(p))
        log("")
        try:
            t = io.open(p, encoding="utf-8", errors="replace").read()
            log("```markdown")
            log(t)
            log("```")
        except Exception as e:
            log("读取失败：%s" % e)
        log("")

    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L))
    print("report:", OUT)


if __name__ == "__main__":
    main()
