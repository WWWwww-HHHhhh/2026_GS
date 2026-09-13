"""纯文本保真核验：检查 Paper/10.Q4/Q4正文.txt 是否忠实覆盖 content.tex 的内容。

只读检查，报告三类证据：
  1. 中文长句片段（>=8 个连续汉字）是否逐条出现在纯文本中
  2. LaTeX 中的全部数字字面量是否出现在纯文本中（结构性数字单独列出）
  3. 纯文本的禁则（分号、破折号、直引号）与行数统计

用法：
  python check_txt_fidelity.py            # 只核验
  python check_txt_fidelity.py --apply    # 核验后写 BOM 并生成归档副本
"""

import io
import os
import re
import shutil
import sys

BASE = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
TEX = os.path.join(BASE, "Paper", "10.Q4", "content.tex")
TXT = os.path.join(BASE, "Paper", "10.Q4", "Q4正文.txt")
COPY = os.path.join(BASE, "All_Code", "Q4", "Q4_wyh", "others", "09_Q4正文纯文本.txt")

# 结构性数字：只属于排版参数，不是正文内容
STRUCTURAL = {"0.95"}


def main() -> int:
    tex = io.open(TEX, encoding="utf-8").read()
    txt = io.open(TXT, encoding="utf-8").read()
    fails = []

    # 1 中文长句片段
    runs = []
    for run in re.findall(r"[\u4e00-\u9fff]{8,}", tex):
        if run not in runs:
            runs.append(run)
    missing_runs = [r for r in runs if r not in txt]
    print("[1] 中文长句片段：%d 条，缺失 %d 条" % (len(runs), len(missing_runs)))
    for r in missing_runs:
        print("    缺失：%s" % r)
        fails.append("run:" + r)

    # 2 数字字面量
    nums = []
    for n in re.findall(r"\d+(?:\.\d+)?", tex):
        if n not in nums:
            nums.append(n)
    missing_nums = [n for n in nums if n not in txt and n not in STRUCTURAL]
    print("[2] 数字字面量：%d 个，缺失 %d 个（结构性数字已排除 %s）"
          % (len(nums), len(missing_nums), sorted(STRUCTURAL)))
    for n in missing_nums:
        print("    缺失：%s" % n)
        fails.append("num:" + n)

    # 3 禁则与统计
    print("[3] 纯文本禁则检查")
    for label, ch in (("分号", "\uff1b"), ("破折号", "\u2014\u2014"), ("直引号", '"')):
        cnt = txt.count(ch)
        print("    %s：%d" % (label, cnt))
        if cnt:
            fails.append("punct:" + label)
    print("    正文行数：%d，字符数：%d" % (txt.count("\n") + 1, len(txt)))
    print("    红字占位：%d 处" % txt.count("【红字】"))
    print("    公式块：%d 处" % len(re.findall(r"式\(\d+\)", txt)))

    if fails:
        print("\n结论：核验未通过，共 %d 项问题" % len(fails))
        return 1

    print("\n结论：核验通过，纯文本与 LaTeX 内容一致")

    if "--apply" in sys.argv:
        body = txt.lstrip("\ufeff")
        io.open(TXT, "w", encoding="utf-8-sig", newline="").write(body)
        shutil.copyfile(TXT, COPY)
        head = io.open(TXT, "rb").read(3)
        print("已写入 BOM：%s" % (head == b"\xef\xbb\xbf"))
        print("归档副本：%s（%d 字节）" % (COPY, os.path.getsize(COPY)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
