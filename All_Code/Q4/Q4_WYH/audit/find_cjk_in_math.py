"""定位 CJK 字符出现在数学环境里的位置（会导致缺字告警）。只读。"""

import io
import os
import re
import glob

WS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
OUT = os.path.join(WS, "All_Code", "Q4", "Q4_wyh", "others", "_audit_readonly", "cjk_in_math.md")
CJK = re.compile(r"[\u4e00-\u9fff]")
L = []


def log(s=""):
    L.append(str(s))


def strip_comments(line):
    out = []
    i = 0
    while i < len(line):
        if line[i] == "%" and (i == 0 or line[i - 1] != "\\"):
            break
        out.append(line[i])
        i += 1
    return "".join(out)


def main():
    log("# CJK 出现在数学环境中的位置（缺字告警来源）")
    log("")
    total = 0
    for fp in sorted(glob.glob(os.path.join(WS, "Paper", "*", "*.tex"))):
        rel = os.path.relpath(fp, WS)
        lines = io.open(fp, encoding="utf-8", errors="replace").read().splitlines()
        hits = []
        # 逐行找 \( ... \) 与 $...$
        for i, raw in enumerate(lines, 1):
            line = strip_comments(raw)
            for m in re.finditer(r"\\\((.*?)\\\)", line):
                if CJK.search(m.group(1)):
                    hits.append((i, "inline \\( \\)", m.group(0)[:90]))
            for m in re.finditer(r"(?<!\$)\$([^$]{1,200})\$(?!\$)", line):
                if CJK.search(m.group(1)):
                    hits.append((i, "inline $ $", m.group(0)[:90]))
        # 跨行的 equation/align 环境
        text = "\n".join(strip_comments(x) for x in lines)
        for m in re.finditer(r"\\begin\{(equation|align|gather|eqnarray)\*?\}(.*?)\\end\{\1\*?\}", text, re.S):
            seg = m.group(2)
            if CJK.search(seg):
                ln = text[: m.start()].count("\n") + 1
                bad = [x for x in seg.splitlines() if CJK.search(x)]
                hits.append((ln, "display %s" % m.group(1), " / ".join(x.strip()[:60] for x in bad[:3])))
        if hits:
            log("## %s" % rel)
            log("")
            for ln, kind, frag in hits:
                log("- L%-4d [%s] `%s`" % (ln, kind, frag))
            log("")
            total += len(hits)
    if total == 0:
        log("（未发现 CJK 出现在数学环境中）")
    log("")
    log("合计 %d 处" % total)

    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L))
    print("report:", OUT, "| hits:", total)


if __name__ == "__main__":
    main()
