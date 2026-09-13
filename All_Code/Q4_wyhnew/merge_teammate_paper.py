"""把队友分支的论文改动三方合并到当前工作区，并同步到 Q4_wyhnew/paper。

三方：base = 53c1c12 的 Paper/10.Q4/content.tex（队友改动的基点）
      ours = 当前工作区文件（含 Q4-2 口径切换的全部改动）
      theirs = origin/fix/q4-reconcile-20260913 的文件
合并结果写回 Paper/10.Q4/content.tex（保持 CRLF）、Q4_wyhnew/paper/10.Q4_content.tex、
Q4_wyhnew/paper/Q4_latex代码.txt，并核对双方标记都在。
"""

import io
import os
import subprocess

WS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
PAPER = os.path.join(WS, "Paper", "10.Q4", "content.tex")
NEW = os.path.join(WS, "All_Code", "Q4_wyhnew")
BASE_REV = "53c1c12"
THEIRS_REV = "origin/fix/q4-reconcile-20260913"
REL = "Paper/10.Q4/content.tex"
TMP = os.path.join(NEW, "_merge_tmp")

OURS_MARKS = ["15728958.76", "14762076.40", "966882.36", "0.654", "0.6450", "14.85",
              "40.86", "72.26", "1763979.96", "22.60", "22.95", "78.19", "1.81",
              "沿用问题二的候选范围与筛选规则", "两处结构性差异"]
THEIRS_MARKS = ["eq:q4_rolling_cost", "共享计费电量", "71.7", "11.06",
                "表中分项与合计均由原始结果分别四舍五入",
                "delta_{\\pi}", "10^{-6}", "两小问的数值保护口径并不相同",
                "不能把增量单独归因", "作为简化方案"]


def run(*a, cwd=WS):
    return subprocess.run(list(a), capture_output=True, cwd=cwd)


def show(rev):
    out = run("git", "show", "%s:%s" % (rev, REL)).stdout
    return out.decode("utf-8").replace("\r\n", "\n")


def main():
    os.makedirs(TMP, exist_ok=True)
    base_p = os.path.join(TMP, "base.tex")
    theirs_p = os.path.join(TMP, "theirs.tex")
    ours_p = os.path.join(TMP, "ours.tex")
    merged_p = os.path.join(TMP, "merged.tex")

    io.open(base_p, "w", encoding="utf-8", newline="\n").write(show(BASE_REV))
    io.open(theirs_p, "w", encoding="utf-8", newline="\n").write(show(THEIRS_REV))
    ours = io.open(PAPER, encoding="utf-8").read().replace("\r\n", "\n")
    io.open(ours_p, "w", encoding="utf-8", newline="\n").write(ours)
    print("base %d 行 | ours %d 行 | theirs %d 行"
          % (show(BASE_REV).count("\n"), ours.count("\n"), show(THEIRS_REV).count("\n")))

    # 三方合并（-p 输出到 stdout，--diff3 便于看冲突）
    r = run("git", "merge-file", "-p", "--diff3", ours_p, base_p, theirs_p)
    merged = r.stdout.decode("utf-8")
    print("merge-file 退出码 =", r.returncode, "（0 = 无冲突）")
    if r.returncode > 0:
        io.open(merged_p, "w", encoding="utf-8", newline="\n").write(merged)
        print("存在冲突，已保存中间结果：", merged_p)
        for i, line in enumerate(merged.splitlines(), 1):
            if line.startswith("<<<<<<<") or line.startswith(">>>>>>>"):
                print("  冲突标记 L%d: %s" % (i, line[:80]))
        return 2

    # 校验双方标记都在
    miss_ours = [m for m in OURS_MARKS if m not in merged]
    miss_theirs = [m for m in THEIRS_MARKS if m not in merged]
    print("本地方（口径切换）缺失标记：", miss_ours or "无")
    print("队友方缺失标记：", miss_theirs or "无")
    if miss_ours or miss_theirs:
        io.open(merged_p, "w", encoding="utf-8", newline="\n").write(merged)
        print("标记不全，未写回，中间结果：", merged_p)
        return 3

    # 写回三处
    out_b = merged.replace("\n", "\r\n").encode("utf-8")
    io.open(PAPER, "wb").write(out_b)
    print("已写回 %s（%d 字节）" % (os.path.relpath(PAPER, WS), len(out_b)))
    for name in ["10.Q4_content.tex", "Q4_latex代码.txt"]:
        dst = os.path.join(NEW, "paper", name)
        io.open(dst, "wb").write(out_b)
        print("已同步 %s（%d 字节）" % (os.path.relpath(dst, WS), len(out_b)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
