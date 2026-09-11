# -*- coding: utf-8 -*-
"""
P0 数据准备与 kappa2 校准（2026 数模 C 题 问题二）
====================================================
实现依据：总纲第 2 节（全局约定）、第 4 节（问题二）。

【数据来源与复用约定】
- 负荷/光伏的单位换算（kW -> kWh）、144 时段时间映射、模板列映射均已由
  `All_Code\\Data_preprocessing\\Data_transformation\\02_global_transform.py` 完成。
- 本模块不再重复做清洗、单位换算、时间对齐；直接读取 Data_transformation 的产物：
    * df_p1.parquet   附件1 固定日内电价（price，元/kWh）
    * df_load.parquet 附件2 负荷（T001..T144，已换算 kWh 电量）
    * df_pv.parquet   附件2 光伏（T001..T144，已换算 kWh 电量）
    * time_map.csv    内部时段 1..144 与附件标签/模板列标签的映射
- 问题二特有且未在其他模块完成的处理：kappa2 校准（来自问题一 SOC 对偶表）。

【全局铁律摘要】
1. 所有数值只能来自附件或其严格衍生；本模块只读取已换算的清洁数据。
2. 单位：负荷/光伏已是 kWh 电量；电价 元/kWh；充放电上限 833.3333 kWh/时段；
   eta_c=eta_r=0.9；SOC in [1200,10800] kWh；初始 SOC=6000 kWh。
3. kappa2 只用问题一 SOC 递推对偶 mu_t^soc 口径（storage_marginal_value_yuan_per_kwh）。
"""
import os
import sys
import pickle
import traceback
from datetime import datetime, date

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 路径常量（自包含）
# ---------------------------------------------------------------------------
GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
DATA_TRANS = os.path.join(GS, r"All_Code\Data_preprocessing\Data_transformation")
Q1MV = r"D:\Program Files(微信)\缓存文件夹\xwechat_files\wxid_wu6lwfcaguhi22_a75e\msg\file\2026-09\q1_storage_marginal_value_for_q2.csv"
Q2CODE = os.path.join(GS, r"All_Code\Q2")
DATA_PROC = os.path.join(Q2CODE, "Data_processing")
TABLES = os.path.join(Q2CODE, "Results", "Tables")

T = 144
D = 365
DELTA_T = 1.0 / 6.0
CHARGE_CAP_KWH = 5000.0 * DELTA_T
ETA_C = 0.9
ETA_R = 0.9
SOC_MIN = 1200.0
SOC_MAX = 10800.0
SOC0 = 6000.0


def ensure_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"无法创建目录 {path}: {exc}") from exc


def log_line(log: list, text: str) -> None:
    log.append(text)
    print(text)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def prepare() -> dict:
    log = []
    ensure_dir(DATA_PROC)
    ensure_dir(TABLES)

    # ---- 1. 读取 Data_transformation 已处理产物 ----
    log_line(log, f"[1] 复用 Data_transformation 已处理数据: {DATA_TRANS}")
    p1 = pd.read_parquet(os.path.join(DATA_TRANS, "df_p1.parquet"))
    load_df = pd.read_parquet(os.path.join(DATA_TRANS, "df_load.parquet"))
    pv_df = pd.read_parquet(os.path.join(DATA_TRANS, "df_pv.parquet"))
    time_map = pd.read_csv(os.path.join(DATA_TRANS, "time_map.csv"), encoding="utf-8-sig")

    # ---- 2. 复用验证（只验证读取结果，不重新清洗/换算） ----
    log_line(log, "[2] 复用验证（数据应已是 kWh 电量，不再换算）")
    if p1.shape[0] != T or "price" not in p1.columns:
        raise ValueError(f"df_p1 应为 144 行且含 price 列，实际 {p1.shape}")
    if load_df.shape != (D, T + 1) or pv_df.shape != (D, T + 1):
        raise ValueError(f"df_load/df_pv 应为 365x145，实际 load={load_df.shape} pv={pv_df.shape}")
    if time_map.shape[0] != T:
        raise ValueError(f"time_map 应为 144 行，实际 {time_map.shape[0]}")

    price_vec = p1["price"].to_numpy(dtype=float)
    time_cols = [f"T{i:03d}" for i in range(1, T + 1)]
    load_kwh = load_df[time_cols].to_numpy(dtype=float).T   # (144,365)
    pv_kwh = pv_df[time_cols].to_numpy(dtype=float).T       # (144,365)

    date_raw = load_df["date"]
    try:
        dates = [pd.Timestamp(v).date() for v in date_raw]
    except Exception as exc:
        raise ValueError(f"df_load date 列解析失败: {exc}") from exc
    if len(dates) != D or dates[0] != date(2025, 1, 1) or dates[-1] != date(2025, 12, 31):
        raise ValueError(f"日期范围异常: {dates[0]} .. {dates[-1]}")
    for k in range(1, D):
        if (dates[k] - dates[k - 1]).days != 1:
            raise ValueError(f"日期序列不连续，位于索引 {k}")

    # 复用数据合理性校验（数据完整性，不做修改）
    checks = []
    if (price_vec <= 0).any():
        checks.append(f"电价非正 {int((price_vec <= 0).sum())} 个")
    if (load_kwh < 0).any():
        checks.append(f"负荷负值 {int((load_kwh < 0).sum())} 个")
    if (pv_kwh < 0).any():
        checks.append(f"光伏负值 {int((pv_kwh < 0).sum())} 个")
    log_line(log, f"    负荷 kWh 范围 [{load_kwh.min():.3f}, {load_kwh.max():.3f}]；光伏 kWh 范围 [{pv_kwh.min():.3f}, {pv_kwh.max():.3f}]")
    log_line(log, f"    电价范围 [{price_vec.min():.4f}, {price_vec.max():.4f}]，非正 {int((price_vec <= 0).sum())} 个")

    # 时间映射复用
    internal_idx = time_map["time_idx"].to_numpy(dtype=int)
    data_labels = time_map["data_label"].astype(str).tolist()
    template_labels = time_map["template_col_label"].astype(str).tolist()
    if not (np.array_equal(internal_idx, np.arange(1, T + 1))):
        raise ValueError("time_map 的 time_idx 应为 1..144 连续")
    template_col = np.arange(2, T + 2, dtype=int)   # 官方模板 计划购电量 sheet 列号 2..145

    # 复用验证报告（替代问题二的重复质量清洗报告）
    report_path = os.path.join(DATA_PROC, "q2_data_quality_report.txt")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("问题二 数据复用与打包验证报告（不再重复清洗/换算）\n")
        fh.write(f"生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        fh.write(f"数据来源: {DATA_TRANS}\n")
        fh.write(f"清洗与单位换算已由 Data_preprocessing 完成；本报告仅验证复用读取结果。\n")
        fh.write(f"样本: 天数={D}, 时段={T}\n")
        fh.write("-" * 60 + "\n")
        if checks:
            for it in checks:
                fh.write(f"- {it}\n")
        else:
            fh.write("复用验证通过：无负值/非正电价/日期缺口。\n")
        fh.write(f"- 负荷 kWh 范围 [{load_kwh.min():.3f}, {load_kwh.max():.3f}]\n")
        fh.write(f"- 光伏 kWh 范围 [{pv_kwh.min():.3f}, {pv_kwh.max():.3f}]\n")
        fh.write(f"- 电价范围 [{price_vec.min():.4f}, {price_vec.max():.4f}] 元/kWh\n")
    log_line(log, f"    复用验证报告已写入: {report_path}")

    # ---- 3. kappa2 校准（问题二特有，总纲 4.4/4.6） ----
    log_line(log, "[3] kappa2 校准（问题一 SOC 递推对偶 mu_t^soc 统一符号口径）")
    if not os.path.exists(Q1MV):
        raise FileNotFoundError(f"Q1 储能边际价值文件不存在: {Q1MV}")
    q1 = pd.read_csv(Q1MV, encoding="utf-8-sig")
    col_mv = "storage_marginal_value_yuan_per_kwh"
    col_bal = "balance_dual_yuan_per_kwh"
    if col_mv not in q1.columns:
        raise KeyError(f"Q1 CSV 缺少列 {col_mv}，实际列: {list(q1.columns)}")
    if q1.shape[0] != T:
        log_line(log, f"    提示：Q1 CSV 行数 {q1.shape[0]} != 144，按实际行数统计")
    mv = q1[col_mv].to_numpy(dtype=float)
    mv = mv[np.isfinite(mv)]
    n_mv = int(mv.size)
    if n_mv == 0:
        raise ValueError("storage_marginal_value_yuan_per_kwh 无有效数值")

    kappa2_stats = {
        "median": float(np.median(mv)),
        "mean": float(np.mean(mv)),
        "min": float(np.min(mv)),
        "max": float(np.max(mv)),
        "p25": float(np.percentile(mv, 25)),
        "p75": float(np.percentile(mv, 75)),
        "n": n_mv,
    }
    kappa2_base = kappa2_stats["median"]
    log_line(log, f"    storage_marginal_value: median={kappa2_stats['median']:.6f}, mean={kappa2_stats['mean']:.6f}, "
                  f"min={kappa2_stats['min']:.6f}, max={kappa2_stats['max']:.6f}, p25={kappa2_stats['p25']:.6f}, p75={kappa2_stats['p75']:.6f}, n={n_mv}")
    if col_bal in q1.columns:
        bal = q1[col_bal].to_numpy(dtype=float)
        bal = bal[np.isfinite(bal)]
        log_line(log, f"    balance_dual（mu_t^bal，仅参照）: median={float(np.median(bal)):.6f}, n={int(bal.size)}")

    kappa2_xlsx = os.path.join(TABLES, "kappa2_calibration.xlsx")
    kappa2_df = pd.DataFrame([
        {"统计量": "median(作为 kappa2_base)", "数值": kappa2_stats["median"], "样本量": n_mv, "来源": "问题一 SOC 递推对偶 mu_t^soc 统一符号口径"},
        {"统计量": "mean", "数值": kappa2_stats["mean"], "样本量": n_mv, "来源": "问题一 SOC 递推对偶 mu_t^soc 统一符号口径"},
        {"统计量": "min", "数值": kappa2_stats["min"], "样本量": n_mv, "来源": "问题一 SOC 递推对偶 mu_t^soc 统一符号口径"},
        {"统计量": "max", "数值": kappa2_stats["max"], "样本量": n_mv, "来源": "问题一 SOC 递推对偶 mu_t^soc 统一符号口径"},
        {"统计量": "p25", "数值": kappa2_stats["p25"], "样本量": n_mv, "来源": "问题一 SOC 递推对偶 mu_t^soc 统一符号口径"},
        {"统计量": "p75", "数值": kappa2_stats["p75"], "样本量": n_mv, "来源": "问题一 SOC 递推对偶 mu_t^soc 统一符号口径"},
    ])
    with pd.ExcelWriter(kappa2_xlsx, engine="openpyxl") as writer:
        kappa2_df.to_excel(writer, index=False, sheet_name="kappa2")
    log_line(log, f"    kappa2_base = {kappa2_base:.6f}，校准表已写入: {kappa2_xlsx}")

    # ---- 4. 打包 q2_dataset.pkl ----
    log_line(log, "[4] 打包 q2_dataset.pkl")
    price_matrix = np.tile(price_vec.reshape(T, 1), (1, D))   # (144,365) 固定日内电价全年复用
    time_mapping = {
        "internal_idx": internal_idx.astype(int),
        "time_labels": data_labels,          # 附件结束时刻标签（0:10 .. 0:00+1）
        "template_col": template_col,        # 官方模板 计划购电量 sheet 列号 2..145
        "template_labels": template_labels,  # 官方模板列标签
    }
    dataset = {
        "dates": np.array(dates, dtype=object),
        "date_str": np.array([d.strftime("%Y-%m-%d") for d in dates], dtype=object),
        "price": price_matrix.astype(float),
        "load": load_kwh.astype(float),
        "pv": pv_kwh.astype(float),
        "time_mapping": time_mapping,
        "kappa2_base": kappa2_base,
        "kappa2_stats": kappa2_stats,
        "constants": {
            "T": T, "D": D, "DELTA_T": DELTA_T,
            "CHARGE_CAP_KWH": CHARGE_CAP_KWH, "ETA_C": ETA_C, "ETA_R": ETA_R,
            "SOC_MIN": SOC_MIN, "SOC_MAX": SOC_MAX, "SOC0": SOC0,
        },
    }
    pkl_path = os.path.join(DATA_PROC, "q2_dataset.pkl")
    with open(pkl_path, "wb") as fh:
        pickle.dump(dataset, fh, protocol=pickle.HIGHEST_PROTOCOL)
    log_line(log, f"    数据集已保存: {pkl_path}")

    # README
    readme_path = os.path.join(DATA_PROC, "README_data.md")
    with open(readme_path, "w", encoding="utf-8") as fh:
        fh.write("# q2_dataset.pkl 字段说明\n\n")
        fh.write(f"- 数据来源: {DATA_TRANS}（负荷/光伏已换算 kWh，电价 元/kWh）\n")
        fh.write(f"- dates / date_str: 日期 2025-01-01..12-31（共 {D} 天）\n")
        fh.write(f"- price: ({T} x {D}) 固定日内电价矩阵，元/kWh，来源附件1，全年复用\n")
        fh.write(f"- load: ({T} x {D}) 负荷电量 kWh（已换算）\n")
        fh.write(f"- pv: ({T} x {D}) 光伏电量 kWh（已换算）\n")
        fh.write(f"- time_mapping: internal_idx/time_labels/template_col/template_labels\n")
        fh.write(f"- kappa2_base / kappa2_stats: 软终端罚系数基准与统计量\n")
        fh.write(f"- constants: T/D/Delta_t/充放电上限/效率/SOC 边界/初始 SOC\n")
    log_line(log, f"    README 已写入: {readme_path}")

    return {"dataset": dataset, "kappa2_base": kappa2_base, "n_reuse_issues": len(checks)}


def main() -> int:
    try:
        result = prepare()
        ds = result["dataset"]
        print("-" * 60)
        print(f"天数={ds['constants']['D']}、时段={ds['constants']['T']}、"
              f"kappa2_base={result['kappa2_base']:.6f}、复用数据校验问题数={result['n_reuse_issues']}")
        return 0
    except Exception as exc:
        print("=" * 60)
        print("P0 数据准备执行失败：")
        traceback.print_exc()
        print(f"错误信息: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
