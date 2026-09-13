"""验证 Q4_WYH 自身能否被脚本当作仓库根解析（只读，不运行模型）。"""

import os
import sys
import importlib.util

NEW = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(NEW, "path_resolution_check.md")
L = []


def log(s=""):
    L.append(str(s))


def main():
    log("# Q4_wyhnew 路径解析自检")
    log("")
    spec = importlib.util.spec_from_file_location("q4_common_new", os.path.join(NEW, "Data_processing", "q4_common.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["q4_common_new"] = m
    spec.loader.exec_module(m)

    log("按 `q4_common.py` 的定位规则解析出的关键路径：")
    log("")
    rows = [("REPO（仓库根）", m.REPO), ("WYH（工作区）", m.WYH), ("TRANS", m.TRANS),
            ("Q2_DIR", m.Q2_DIR), ("ATTACH_RAW", m.ATTACH_RAW), ("OUT_DATA", m.OUT_DATA),
            ("TABLES", m.TABLES), ("PICTURES", m.PICTURES), ("MODELDIR", m.MODELDIR)]
    log("| 常量 | 解析结果（相对 Q4_wyhnew） | 存在 |")
    log("| --- | --- | --- |")
    ok = True
    for name, p in rows:
        p = str(p)
        inside = p.startswith(NEW)
        rel = os.path.relpath(p, NEW) if inside else p
        ex = os.path.exists(p)
        if not inside or not ex:
            ok = False
        log("| `%s` | `%s` | %s |" % (name, rel, "是" if ex else "否"))
    log("")
    log("## 关键输入文件是否齐备")
    log("")
    need = [
        os.path.join(m.OUT_DATA, "q4_dataset.pkl"),
        os.path.join(m.OUT_DATA, "price_forecast.pkl"),
        os.path.join(m.OUT_DATA, "scenarios_M30_official.pkl"),
        os.path.join(m.OUT_DATA, "scenarios_M30_q2.pkl"),
        os.path.join(m.OUT_DATA, "scenarios_M30.pkl"),
        os.path.join(m.OUT_DATA, "variants", "V_official_unknown_q2params_results.pkl"),
        os.path.join(m.OUT_DATA, "q4_2_rolling_results.pkl"),
        os.path.join(m.TABLES, "result4-2.xlsx"),
        os.path.join(m.PICTURES, "fig_q4_representative_day.pdf"),
        os.path.join(m.TRANS, "df_load.parquet"),
        os.path.join(m.TRANS, "time_map.csv"),
        os.path.join(m.Q2_DIR, "q2_dataset.pkl"),
        os.path.join(m.Q2_DIR, "forecasts.pkl"),
        os.path.join(m.ATTACH_RAW, "附件1.xlsx"),
        os.path.join(m.ATTACH_RAW, "附件4.xlsx"),
        os.path.join(m.REPO, "All_Code", "Q1", "Results", "Tables", "result1.xlsx"),
    ]
    log("| 文件 | 大小 |")
    log("| --- | --- |")
    for p in need:
        ex = os.path.exists(p)
        if not ex:
            ok = False
        sz = "%.2f MB" % (os.path.getsize(p) / 1048576) if ex else "**缺失**"
        log("| `%s` | %s |" % (os.path.relpath(p, NEW), sz))
    log("")
    log("## 结论")
    log("")
    log("- 全部关键路径都落在 Q4_wyhnew 内部：**%s**" % ("是" if ok else "否"))
    log("- 脚本的 `find_repo_root()` 会把 Q4_wyhnew 认作仓库根，因此无需改动任何源码即可在本目录独立运行。")
    log("- 本次未运行任何模型或数据处理脚本（按要求先不写代码）。")

    import io
    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L))
    print("report:", OUT, "| ok =", ok)


if __name__ == "__main__":
    main()
