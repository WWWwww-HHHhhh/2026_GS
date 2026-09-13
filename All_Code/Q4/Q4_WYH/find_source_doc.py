"""定位 Q2_摘要定稿与Q3衔接口径确认.md 及其近邻文件（只读）。"""

import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ROOTS = [
    r"D:\Personal\Desktop",
    r"D:\Personal\Documents",
    r"D:\Personal\Downloads",
    WS,
    r"D:\Program Files(微信)\缓存文件夹\xwechat_files\wxid_wu6lwfcaguhi22_a75e\msg\file\2026-09",
]
NEEDLES = ["口径确认", "Q2_摘要定稿", "摘要定稿", "衔接口径"]
OUT = os.path.join(HERE, "find_source_doc.md")
L = []


def log(s=""):
    L.append(str(s))


def main():
    log("# 定位 Q2_摘要定稿与Q3衔接口径确认.md")
    log("")
    hits = []
    for root in ROOTS:
        log("## 扫描 `%s`" % root)
        log("")
        if not os.path.isdir(root):
            log("- 不存在或不可读")
            log("")
            continue
        n = 0
        for r, ds, fs in os.walk(root):
            depth = r[len(root):].count(os.sep)
            if depth >= 3:
                ds[:] = []
                continue
            for f in fs:
                n += 1
                if any(k in f for k in NEEDLES):
                    fp = os.path.join(r, f)
                    hits.append(fp)
                    log("- **命中** `%s`  %.0f KB" % (fp, os.path.getsize(fp) / 1024))
        log("- 共扫过 %d 个文件" % n)
        log("")
    log("## 命中汇总")
    log("")
    if not hits:
        log("（未找到）")
    for p in hits:
        log("- `%s`" % p)
    log("")
    log("## 命中文件目录列表（便于人工确认）")
    log("")
    for p in hits:
        d = os.path.dirname(p)
        log("- 目录 `%s`：" % d)
        try:
            for f in sorted(os.listdir(d)):
                log("  - `%s`" % f)
        except Exception as e:
            log("  - 列目录失败 %s" % e)

    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L))
    print("report:", OUT)
    for p in hits:
        print("HIT:", p)


if __name__ == "__main__":
    main()
