"""只读查询：Q4 正文 content.tex 的历史版本，以及那份“只有标题”的残版内容。

用法：python show_q4_versions.py
"""

import os
import subprocess

BASE = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
PATH = "Paper/10.Q4/content.tex"


def run(*args):
    return subprocess.run(list(args), capture_output=True, cwd=BASE)


def lines_of(rev):
    body = run("git", "show", rev + ":" + PATH).stdout.decode("utf-8", "replace")
    return len(body.splitlines()), body


def main():
    print("=" * 68)
    print("一、38ac186 里那份只有标题的 content.tex 全文")
    print("=" * 68)
    n, body = lines_of("38ac186")
    print(body if body.strip() else "（空文件）")
    print("该版本共 %d 行 / %d 字符" % (n, len(body)))

    print()
    print("=" * 68)
    print("二、当前工作区的 Q4 正文")
    print("=" * 68)
    p = os.path.join(BASE, "Paper", "10.Q4", "content.tex")
    cur = open(p, "rb").read().decode("utf-8", "replace")
    ls = cur.splitlines()
    print("行数 %d | 红字 %d | 占位 %d" % (len(ls), cur.count("color{red}"), cur.count("占位")))
    print("标题行：%s" % (ls[1] if len(ls) > 1 else ""))

    print()
    print("=" * 68)
    print("三、content.tex 的全部历史版本（所有分支）")
    print("=" * 68)
    out = run("git", "log", "--all", "--format=%H|%h|%an|%ad|%s",
              "--date=format:%m-%d %H:%M", "--", PATH).stdout.decode("utf-8", "replace")
    seen = set()
    for row in out.splitlines():
        if not row.strip():
            continue
        full, short, author, date, subject = row.split("|", 4)
        if full in seen:
            continue
        seen.add(full)
        n, _ = lines_of(short)
        if n > 200:
            kind = "完整正文"
        elif n < 40:
            kind = "残版(仅标题)"
        else:
            kind = "中间版"
        anc = run("git", "merge-base", "--is-ancestor", full, "origin/main").returncode == 0
        print("  %s  %s  %-12s  %-16s %4d 行  %s%s"
              % (short, date, author, subject[:16], n, kind,
                 "  [在 origin/main 历史里]" if anc else ""))

    print()
    print("=" * 68)
    print("四、取用方式")
    print("=" * 68)
    print("  查看某版本：      git show <短哈希>:%s" % PATH)
    print("  用某版本覆盖当前：git checkout <短哈希> -- %s" % PATH)


if __name__ == "__main__":
    main()
