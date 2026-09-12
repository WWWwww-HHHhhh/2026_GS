# -*- coding: utf-8 -*-
"""只读自检：Paper/10.Q4/content.tex 的格式纪律与交叉引用完整性。不修改任何文件。"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

PAPER = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\Paper")
TARGET = PAPER / "10.Q4" / "content.tex"
tex = TARGET.read_text(encoding="utf-8")
lines = tex.splitlines()

print("=" * 88)
print(f"文件：{TARGET.name}　行数 {len(lines)}　字符数 {len(tex)}")
print("=" * 88)

print("\n[1] 标点纪律")
for name, ch in (("中文分号 ；", "；"), ("半角分号 ;", ";"), ("中文破折号 ——", "——"), ("半角双连字符 --", "--")):
    hits = [i + 1 for i, l in enumerate(lines) if ch in l and not l.strip().startswith("%")]
    print(f"  {name:<16} 出现 {len(hits)} 次" + (f"　行号 {hits[:8]}" if hits else ""))

print("\n[2] 标题层级（要求最多到 subsubsection）")
for i, l in enumerate(lines):
    m = re.match(r"\\(section|subsection|subsubsection|paragraph|subparagraph)\*?\{", l)
    if m:
        lvl = {"section": 1, "subsection": 2, "subsubsection": 3, "paragraph": 4, "subparagraph": 5}[m.group(1)]
        flag = "  ← 超出限制" if lvl > 3 else ""
        print(f"  L{lvl} 第{i+1:>4}行  {l[:70]}{flag}")

print("\n[3] 环境配对")
beg = Counter(re.findall(r"\\begin\{([^}]+)\}", tex))
end = Counter(re.findall(r"\\end\{([^}]+)\}", tex))
ok = True
for k in sorted(set(beg) | set(end)):
    a, b = beg.get(k, 0), end.get(k, 0)
    if a != b:
        ok = False
        print(f"  ✗ {k}: begin {a} / end {b}")
print("  全部配对正确" if ok else "  存在不配对环境")

print("\n[4] 公式后是否加了句号")
bad = []
for i, l in enumerate(lines):
    if re.match(r"\s*\\end\{(equation|aligned|align)\}", l):
        rest = "".join(lines[i + 1:i + 3]).strip()
        if rest.startswith(".") or rest.startswith("。"):
            bad.append(i + 1)
print(f"  紧跟句号的 \\end 行：{bad if bad else '无'}")

print("\n[5] 交叉引用完整性（本文件引用的标签是否在 Paper 全树中定义）")
refs = set(re.findall(r"\\(?:eqref|ref)\{([^}]+)\}", tex))
defined = set()
for f in PAPER.rglob("*.tex"):
    if f.name == "layout.tex":
        continue
    defined |= set(re.findall(r"\\label\{([^}]+)\}", f.read_text(encoding="utf-8", errors="replace")))
missing = sorted(r for r in refs if r not in defined)
print(f"  本文件引用 {len(refs)} 个标签：{sorted(refs)}")
print(f"  未定义（会显示 ??）：{missing if missing else '无'}")

print("\n[6] 本文件定义的标签")
own = re.findall(r"\\label\{([^}]+)\}", tex)
dup = [k for k, v in Counter(own).items() if v > 1]
print(f"  {own}")
print(f"  重复标签：{dup if dup else '无'}")

print("\n[7] 图片路径是否存在（相对主文件 main.tex 所在目录解析）")
for m in re.finditer(r"\\includegraphics\[[^\]]*\]\s*\{([^}]+)\}", tex):
    rel = m.group(1).strip()
    p = (PAPER / rel).resolve()
    print(f"  {'OK  ' if p.exists() else '缺失'} {rel}  ->  {p}")
