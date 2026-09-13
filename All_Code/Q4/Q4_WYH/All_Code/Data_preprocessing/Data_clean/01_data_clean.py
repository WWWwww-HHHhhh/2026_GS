import os
import sys
import traceback
from pathlib import Path
from datetime import time as dt_time

import numpy as np
import pandas as pd
import openpyxl


# ============================== 全局配置 ==============================
INPUT_FILES = {
    "附件1": r"D:\Personal\Temp\附件1.xlsx",
    "附件2": r"D:\Personal\Temp\附件2.xlsx",
    "附件3": r"D:\Personal\Temp\附件3.xlsx",
    "附件4": r"D:\Personal\Temp\附件4.xlsx",
}

# 输出目录与脚本同目录
OUTPUT_DIR = Path(__file__).resolve().parent
OUTPUT_REPORT = OUTPUT_DIR / "01_clean_report.md"
OUTPUT_CSV = {
    "附件1": OUTPUT_DIR / "附件1_clean.csv",
    "附件2_load": OUTPUT_DIR / "附件2_load_clean.csv",
    "附件2_pv": OUTPUT_DIR / "附件2_pv_clean.csv",
    "附件3": OUTPUT_DIR / "附件3_clean.csv",
    "附件4": OUTPUT_DIR / "附件4_clean.csv",
}

# 日期连续性检查区间：2025-01-01 至 2025-12-31，恰好 365 天
START_DATE = pd.Timestamp("2025-01-01")
END_DATE = pd.Timestamp("2025-12-31")
EXPECTED_DAYS = 365

# 负荷/光伏合理量级上界（kW），只报告、不修改
LOAD_PV_UPPER = 12000.0

# 光伏夜间窗口：19:30 - 05:30（分钟数，含边界）
NIGHT_START_MIN = 19 * 60 + 30
NIGHT_END_MIN = 5 * 60 + 30

# 报告中每个异常/缺失项最多展示的样例位置数
MAX_POS_SAMPLE = 15


# ============================== 工具函数 ==============================
def setup_console():
    """保证 Windows 控制台以 UTF-8 输出中文，避免乱码。"""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def parse_time_to_minutes(value):
    """把时间单元格或时间列名解析为一天内的分钟数。

    支持：datetime.time 对象、"HH:MM"、"HH:MM:SS"、"0:00+1" 等格式。
    无法解析时返回 None，调用方应跳过而不是当作夜间。
    """
    if value is None:
        return None
    if isinstance(value, dt_time):
        return value.hour * 60 + value.minute
    text = str(value).strip()
    # 附件2/附件4 最后一列 "0:00+1" 表示次日 0:00，去掉 +1 后按 0:00 处理
    text = text.replace("+1", "").replace("+1天", "").replace("+1d", "")
    if not text or text.lower() in ("nan", "none", "nat", ""):
        return None
    try:
        parts = text.split(":")
        hour = int(float(parts[0]))
        minute = int(float(parts[1]))
        if hour == 24:
            hour = 0
        return hour * 60 + minute
    except Exception:
        return None


def is_night_minutes(minutes):
    """判断分钟数是否落在 19:30 - 05:30 的夜间窗口内（含边界）。"""
    if minutes is None:
        return False
    return minutes >= NIGHT_START_MIN or minutes <= NIGHT_END_MIN


def normalize_header_name(col):
    """把 Excel 表头统一成字符串，避免 datetime.time 与字符串混用导致比对失败。"""
    if isinstance(col, dt_time):
        return col.strftime("%H:%M:%S")
    return str(col)


def normalize_headers(df):
    """复制 DataFrame 并规范化列名，原表不改变。"""
    df = df.copy()
    df.columns = [normalize_header_name(c) for c in df.columns]
    return df


def get_missing_mask(df):
    """返回缺失掩码：既包含 NaN/None，也包含空白字符串。"""
    nan_mask = df.isna()
    try:
        # pandas 3.x 用 DataFrame.map，旧版本用 applymap，这里做兼容
        empty_mask = df.map(lambda x: isinstance(x, str) and x.strip() == "")
    except AttributeError:
        empty_mask = df.applymap(lambda x: isinstance(x, str) and x.strip() == "")
    return (nan_mask | empty_mask).astype(bool)


def mask_count(mask):
    """统计布尔掩码中 True 的数量。"""
    return int(mask.to_numpy().sum()) if hasattr(mask, "to_numpy") else int(np.asarray(mask).sum())


def mask_positions(df, mask, max_sample=MAX_POS_SAMPLE):
    """把布尔掩码转为 Excel 行号(1 基) + 列名的样例位置列表。"""
    arr = mask.to_numpy() if hasattr(mask, "to_numpy") else np.asarray(mask)
    positions = []
    for row_idx, col_idx in np.argwhere(arr)[:max_sample]:
        excel_row = int(row_idx) + 2  # DataFrame 第 0 行对应 Excel 第 2 行（第 1 行是表头）
        positions.append((excel_row, str(df.columns[int(col_idx)])))
    return positions


def numeric_value_columns(df, exclude_cols):
    """返回除排除列外的所有数值列名（字符串形式）。"""
    exclude = {str(c) for c in exclude_cols}
    cols = []
    for c in df.columns:
        if str(c) in exclude:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(str(c))
    return cols


def excel_dimensions(path, sheet_name):
    """用 openpyxl 读取工作表的 Excel 原始维度（行数 x 列数）。"""
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            ws = wb[sheet_name]
            return ws.max_row, ws.max_column
        finally:
            wb.close()
    except Exception:
        return None, None


def to_numeric_series(df, col):
    """把某列安全转换为数值序列，无法转换的当作 NaN，不修改原表。"""
    return pd.to_numeric(df[col], errors="coerce")


def flag_negative_and_clip(df, cols):
    """报告负值并把负值截断为 0（只对负荷/光伏数值列使用）。

    返回：修改后的 df、负值数量、负值样例位置。
    """
    neg_positions = []
    total = 0
    for col in cols:
        series = to_numeric_series(df, col)
        neg_mask = series.lt(0)
        n = int(neg_mask.sum())
        total += n
        arr = neg_mask.to_numpy()
        for row_idx in np.argwhere(arr)[:MAX_POS_SAMPLE]:
            excel_row = int(row_idx[0]) + 2
            neg_positions.append((excel_row, str(col), float(series.iloc[int(row_idx[0])])))
        # 物理不可能值：负负荷、负光伏截断为 0
        df[col] = series.clip(lower=0)
    return df, total, neg_positions[:MAX_POS_SAMPLE]


def flag_upper_bound(df, cols, upper):
    """报告超过上界的可疑值，但不修改数据。"""
    positions = []
    total = 0
    for col in cols:
        series = to_numeric_series(df, col)
        mask = series.gt(upper)
        total += int(mask.sum())
        for row_idx in np.argwhere(mask.to_numpy())[:MAX_POS_SAMPLE]:
            excel_row = int(row_idx[0]) + 2
            positions.append((excel_row, str(col), float(series.iloc[int(row_idx[0])])))
    return total, positions[:MAX_POS_SAMPLE]


def flag_price_nonpositive(df, cols):
    """报告电价 <= 0 的可疑值，但不修改数据。"""
    positions = []
    total = 0
    for col in cols:
        series = to_numeric_series(df, col)
        mask = series.le(0)
        total += int(mask.sum())
        for row_idx in np.argwhere(mask.to_numpy())[:MAX_POS_SAMPLE]:
            excel_row = int(row_idx[0]) + 2
            positions.append((excel_row, str(col), float(series.iloc[int(row_idx[0])])))
    return total, positions[:MAX_POS_SAMPLE]


def flag_pv_night_wide(df, time_cols):
    """对宽表（日期 x 144 个时间列）检查光伏夜间非零，仅报告不修改。"""
    total = 0
    positions = []
    date_col = str(df.columns[0])
    for col in time_cols:
        minutes = parse_time_to_minutes(col)
        if not is_night_minutes(minutes):
            continue
        series = to_numeric_series(df, col)
        mask = series.gt(0)  # 严格 >0，不给容差
        total += int(mask.sum())
        for row_idx in np.argwhere(mask.to_numpy())[:MAX_POS_SAMPLE]:
            date_val = str(df.iloc[int(row_idx[0])][date_col])
            positions.append((date_val, str(col), float(series.iloc[int(row_idx[0])])))
    return total, positions[:MAX_POS_SAMPLE]


def flag_pv_night_long(df, time_col, pv_col):
    """对长表（附件1）检查光伏夜间非零，仅报告不修改。"""
    minutes = df[time_col].map(parse_time_to_minutes)
    night = minutes.map(is_night_minutes).fillna(False).astype(bool)
    series = to_numeric_series(df, pv_col)
    mask = night & series.gt(0)
    total = int(mask.sum())
    positions = []
    for row_idx in np.argwhere(mask.to_numpy())[:MAX_POS_SAMPLE]:
        positions.append((str(df.iloc[int(row_idx[0])][time_col]), str(pv_col),
                          float(series.iloc[int(row_idx[0])])))
    return total, positions


def check_daily_date_continuity(date_series, row_dups_expected=False):
    """检查 2025-01-01 至 2025-12-31 的日期连续性。

    row_dups_expected=True 用于附件3：每天有 4 个预报时刻，行级重复日期是正常结构，
    此时只检查“唯一日期集合”是否恰好为 365 天且无缺日/多余日。
    """
    series = pd.to_datetime(date_series, errors="coerce")
    n_raw = int(series.notna().sum())
    n_nan = int(series.isna().sum())
    normalized = series.dt.normalize()
    valid = normalized.dropna()

    # 行级重复日（同一天出现多次）
    dup_count = int(valid.duplicated(keep="first").sum())
    dup_days = sorted(valid[valid.duplicated(keep=False)].dt.strftime("%Y-%m-%d").unique().tolist())

    unique = pd.Series(sorted(valid.unique()))
    expected = pd.date_range(START_DATE, END_DATE, freq="D")
    missing_days = [d.strftime("%Y-%m-%d") for d in expected if d not in set(unique)]
    extra_days = [d.strftime("%Y-%m-%d") for d in unique if d not in set(expected)]

    passed = (n_nan == 0) and (len(unique) == EXPECTED_DAYS) and \
             (len(missing_days) == 0) and (len(extra_days) == 0)
    if not row_dups_expected:
        passed = passed and (dup_count == 0)

    return {
        "passed": bool(passed),
        "n_raw": n_raw,
        "n_nan": n_nan,
        "n_unique": int(len(unique)),
        "dup_count": dup_count,
        "dup_days": dup_days,
        "missing_days": missing_days,
        "extra_days": extra_days,
    }


def check_duplicates_wide(df, date_col):
    """对宽表按“日期 + 时段”组合查重。

    宽表中一行对应一个完整日期（144 个时段），因此重复组合等价于重复日期行。
    返回值：重复日期行数、待删除重复单元格数、样例日期。
    """
    dup_rows = int(df.duplicated(subset=[date_col], keep="first").sum())
    dup_dates = df.loc[df.duplicated(subset=[date_col], keep=False), date_col]
    sample_dates = sorted(dup_dates.drop_duplicates().astype(str).head(MAX_POS_SAMPLE).tolist())

    value_cols = [str(c) for c in df.columns if str(c) != date_col]
    long_df = df.melt(id_vars=[date_col], value_vars=value_cols,
                      var_name="时段", value_name="数值")
    dup_cells = int(long_df.duplicated(subset=[date_col, "时段"], keep="first").sum())
    return dup_rows, dup_cells, sample_dates


def drop_duplicate_rows(df, keys, keep="first"):
    """删除重复记录，保留第一条，返回清洗后的表与删除行数。"""
    before = len(df)
    df = df.drop_duplicates(subset=keys, keep=keep).reset_index(drop=True)
    return df, before - len(df)


def compare_wide_consistency(a, b, label_a, label_b):
    """比对两张宽表的“日期列 + 144 个时间列”是否完全一致。"""
    cols_a = [str(c) for c in a.columns]
    cols_b = [str(c) for c in b.columns]
    col_match = cols_a == cols_b
    col_diff = []
    if not col_match:
        for i in range(max(len(cols_a), len(cols_b))):
            ca = cols_a[i] if i < len(cols_a) else None
            cb = cols_b[i] if i < len(cols_b) else None
            if ca != cb:
                col_diff.append((i + 1, ca, cb))

    date_col_a = cols_a[0] if cols_a else None
    date_col_b = cols_b[0] if cols_b else None
    dates_a = pd.to_datetime(a[date_col_a], errors="coerce").dt.strftime("%Y-%m-%d").tolist()
    dates_b = pd.to_datetime(b[date_col_b], errors="coerce").dt.strftime("%Y-%m-%d").tolist()
    date_match = dates_a == dates_b
    date_diff_idx = [i + 2 for i, (x, y) in enumerate(zip(dates_a, dates_b)) if x != y]

    passed = col_match and date_match
    return {
        "passed": bool(passed),
        "col_match": bool(col_match),
        "date_match": bool(date_match),
        "n_cols_a": len(cols_a),
        "n_cols_b": len(cols_b),
        "col_diff": col_diff,
        "date_diff_idx": date_diff_idx[:MAX_POS_SAMPLE],
    }


# ============================== 主流程 ==============================
def main():
    setup_console()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 90)
    print("开始读取原始 xlsx（只读，不修改原文件）")
    print("=" * 90)

    # ---------- 1. 读取所有 xlsx 的所有 sheet ----------
    raw_sheets = {}
    for key, path in INPUT_FILES.items():
        if not os.path.exists(path):
            print(f"[错误] 找不到输入文件：{path}")
            sys.exit(1)
        try:
            raw_sheets[key] = pd.read_excel(path, sheet_name=None, header=0)
        except Exception as exc:
            print(f"[错误] 读取 {key} 失败：{exc}")
            traceback.print_exc()
            sys.exit(1)
        for sheet_name in raw_sheets[key]:
            raw_sheets[key][sheet_name] = normalize_headers(raw_sheets[key][sheet_name])

    # ---------- 2. 打印每个 sheet 的名称、维度、列名、前 3 行 ----------
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 300)
    for key, sheet_dict in raw_sheets.items():
        path = INPUT_FILES[key]
        for sheet_name, df in sheet_dict.items():
            max_row, max_col = excel_dimensions(path, sheet_name)
            print("-" * 90)
            print(f"[{key}] sheet 名：{sheet_name}")
            print(f"[{key}] Excel 维度：{max_row} 行 x {max_col} 列；"
                  f"pandas 读取：{df.shape[0]} 行 x {df.shape[1]} 列")
            print(f"[{key}] 列名：{list(df.columns)}")
            print(f"[{key}] 前 3 行：")
            print(df.head(3).to_string(index=False))

    # ---------- 3. 逐文件检查并清洗 ----------
    report = []
    checklist = []

    def add_report(line=""):
        report.append(line)

    def add_check(name, passed, detail):
        checklist.append((name, bool(passed), detail))

    cleaned = {}

    # ============================== 附件1 ==============================
    a1 = raw_sheets["附件1"]["Sheet1"]
    add_report("## 附件1（Sheet1，单日曲线，无日期列）")
    a1_missing = get_missing_mask(a1)
    a1_missing_n = mask_count(a1_missing)
    a1_missing_pos = mask_positions(a1, a1_missing)
    msg = f"- 缺失值：共 {a1_missing_n} 个（仅报告，不填充）。"
    if a1_missing_n:
        msg += f" 样例位置：{a1_missing_pos}"
    add_report(msg)
    add_check("附件1 缺失值检查", a1_missing_n == 0, f"缺失 {a1_missing_n} 个")

    a1_dup_mask = a1.duplicated(subset=["时间"], keep="first")
    a1_dup_n = int(a1_dup_mask.sum())
    a1_dup_samples = a1.loc[a1.duplicated(subset=["时间"], keep=False), "时间"] \
        .drop_duplicates().head(MAX_POS_SAMPLE).astype(str).tolist()
    msg = f"- 重复（按时间/时段）：待删除 {a1_dup_n} 条。"
    if a1_dup_n:
        msg += f" 样例时段：{a1_dup_samples}"
    add_report(msg)
    add_check("附件1 重复检查", a1_dup_n == 0, f"重复 {a1_dup_n} 条")

    a1_price_bad, a1_price_pos = flag_price_nonpositive(a1, ["电价"])
    msg = f"- 电价<=0：{a1_price_bad} 个（仅报告，不修改）。"
    if a1_price_bad:
        msg += f" 样例：{a1_price_pos}"
    add_report(msg)
    add_check("附件1 电价<=0检查", a1_price_bad == 0, f"可疑 {a1_price_bad} 个")

    a1_pv_night_n, a1_pv_night_pos = flag_pv_night_long(a1, "时间", "光伏发电预测功率")
    msg = f"- 光伏夜间非零(19:30-05:30,>0)：{a1_pv_night_n} 个（仅报告，不修改）。"
    if a1_pv_night_n:
        msg += f" 样例：{a1_pv_night_pos}"
    add_report(msg)
    add_check("附件1 光伏夜间非零检查", a1_pv_night_n == 0, f"可疑 {a1_pv_night_n} 个")

    a1_upper_n, a1_upper_pos = flag_upper_bound(
        a1, ["小区负载", "光伏发电预测功率"], LOAD_PV_UPPER)
    msg = f"- 负荷/光伏超出 {LOAD_PV_UPPER:.0f} kW：{a1_upper_n} 个（仅报告，不修改）。"
    if a1_upper_n:
        msg += f" 样例：{a1_upper_pos}"
    add_report(msg)
    add_check("附件1 负荷/光伏上界检查", a1_upper_n == 0, f"超限 {a1_upper_n} 个")

    a1, a1_neg_n, a1_neg_pos = flag_negative_and_clip(a1, ["小区负载", "光伏发电预测功率"])
    msg = f"- 负负荷/负光伏：{a1_neg_n} 个，已截断为 0。"
    if a1_neg_n:
        msg += f" 样例：{a1_neg_pos}"
    add_report(msg)

    a1, a1_drop_n = drop_duplicate_rows(a1, ["时间"])
    cleaned["附件1"] = a1

    # ============================== 附件2 ==============================
    a2_load = raw_sheets["附件2"]["小区负载"]
    a2_pv = raw_sheets["附件2"]["光伏发电实际功率"]
    a2_load_date = str(a2_load.columns[0])
    a2_pv_date = str(a2_pv.columns[0])
    a2_load_cols = numeric_value_columns(a2_load, [a2_load_date])
    a2_pv_cols = numeric_value_columns(a2_pv, [a2_pv_date])

    add_report("## 附件2（sheet：小区负载）")
    a2l_missing = get_missing_mask(a2_load)
    a2l_missing_n = mask_count(a2l_missing)
    a2l_missing_pos = mask_positions(a2_load, a2l_missing)
    msg = f"- 缺失值：共 {a2l_missing_n} 个（仅报告，不填充）。"
    if a2l_missing_n:
        msg += f" 样例位置：{a2l_missing_pos}"
    add_report(msg)
    add_check("附件2(负荷) 缺失值检查", a2l_missing_n == 0, f"缺失 {a2l_missing_n} 个")

    a2l_dup_rows, a2l_dup_cells, a2l_dup_dates = check_duplicates_wide(a2_load, a2_load_date)
    msg = (f"- 重复：重复日期行 {a2l_dup_rows} 行；展开后日期+时段重复单元格(不含首条) "
           f"{a2l_dup_cells} 个。")
    if a2l_dup_rows:
        msg += f" 样例日期：{a2l_dup_dates}"
    add_report(msg)
    add_check("附件2(负荷) 重复检查", a2l_dup_rows == 0, f"重复日期行 {a2l_dup_rows} 行")

    a2l_upper_n, a2l_upper_pos = flag_upper_bound(a2_load, a2_load_cols, LOAD_PV_UPPER)
    msg = f"- 负荷超出 {LOAD_PV_UPPER:.0f} kW：{a2l_upper_n} 个（仅报告，不修改）。"
    if a2l_upper_n:
        msg += f" 样例：{a2l_upper_pos}"
    add_report(msg)
    add_check("附件2(负荷) 上界检查", a2l_upper_n == 0, f"超限 {a2l_upper_n} 个")

    a2_load, a2l_neg_n, a2l_neg_pos = flag_negative_and_clip(a2_load, a2_load_cols)
    msg = f"- 负负荷：{a2l_neg_n} 个，已截断为 0。"
    if a2l_neg_n:
        msg += f" 样例：{a2l_neg_pos}"
    add_report(msg)

    cont = check_daily_date_continuity(a2_load[a2_load_date], row_dups_expected=False)
    msg = (f"- 日期连续性：唯一 {cont['n_unique']} 天，缺日 {len(cont['missing_days'])}，"
           f"多余日 {len(cont['extra_days'])}，重复日 {cont['dup_count']}。")
    if cont["missing_days"]:
        msg += f" 缺日：{cont['missing_days']}"
    if cont["extra_days"]:
        msg += f" 多余日：{cont['extra_days']}"
    add_report(msg)
    add_check("附件2(负荷) 365天连续性", cont["passed"],
              "唯一日期集合连续" if cont["passed"] else "日期连续性异常")

    a2_load, a2l_drop_n = drop_duplicate_rows(a2_load, [a2_load_date])
    cleaned["附件2_load"] = a2_load

    add_report("## 附件2（sheet：光伏发电实际功率）")
    a2p_missing = get_missing_mask(a2_pv)
    a2p_missing_n = mask_count(a2p_missing)
    a2p_missing_pos = mask_positions(a2_pv, a2p_missing)
    msg = f"- 缺失值：共 {a2p_missing_n} 个（仅报告，不填充）。"
    if a2p_missing_n:
        msg += f" 样例位置：{a2p_missing_pos}"
    add_report(msg)
    add_check("附件2(光伏) 缺失值检查", a2p_missing_n == 0, f"缺失 {a2p_missing_n} 个")

    a2p_dup_rows, a2p_dup_cells, a2p_dup_dates = check_duplicates_wide(a2_pv, a2_pv_date)
    msg = (f"- 重复：重复日期行 {a2p_dup_rows} 行；展开后日期+时段重复单元格(不含首条) "
           f"{a2p_dup_cells} 个。")
    if a2p_dup_rows:
        msg += f" 样例日期：{a2p_dup_dates}"
    add_report(msg)
    add_check("附件2(光伏) 重复检查", a2p_dup_rows == 0, f"重复日期行 {a2p_dup_rows} 行")

    a2p_night_n, a2p_night_pos = flag_pv_night_wide(a2_pv, a2_pv_cols)
    msg = f"- 光伏夜间非零(19:30-05:30,>0)：{a2p_night_n} 个（仅报告，不修改）。"
    if a2p_night_n:
        msg += f" 样例：{a2p_night_pos}"
    add_report(msg)
    add_check("附件2(光伏) 夜间非零检查", a2p_night_n == 0, f"可疑 {a2p_night_n} 个")

    a2p_upper_n, a2p_upper_pos = flag_upper_bound(a2_pv, a2_pv_cols, LOAD_PV_UPPER)
    msg = f"- 光伏超出 {LOAD_PV_UPPER:.0f} kW：{a2p_upper_n} 个（仅报告，不修改）。"
    if a2p_upper_n:
        msg += f" 样例：{a2p_upper_pos}"
    add_report(msg)
    add_check("附件2(光伏) 上界检查", a2p_upper_n == 0, f"超限 {a2p_upper_n} 个")

    a2_pv, a2p_neg_n, a2p_neg_pos = flag_negative_and_clip(a2_pv, a2_pv_cols)
    msg = f"- 负光伏：{a2p_neg_n} 个，已截断为 0。"
    if a2p_neg_n:
        msg += f" 样例：{a2p_neg_pos}"
    add_report(msg)

    cont = check_daily_date_continuity(a2_pv[a2_pv_date], row_dups_expected=False)
    msg = (f"- 日期连续性：唯一 {cont['n_unique']} 天，缺日 {len(cont['missing_days'])}，"
           f"多余日 {len(cont['extra_days'])}，重复日 {cont['dup_count']}。")
    if cont["missing_days"]:
        msg += f" 缺日：{cont['missing_days']}"
    if cont["extra_days"]:
        msg += f" 多余日：{cont['extra_days']}"
    add_report(msg)
    add_check("附件2(光伏) 365天连续性", cont["passed"],
              "唯一日期集合连续" if cont["passed"] else "日期连续性异常")

    a2_pv, a2p_drop_n = drop_duplicate_rows(a2_pv, [a2_pv_date])
    cleaned["附件2_pv"] = a2_pv

    # ============================== 附件3 ==============================
    a3 = raw_sheets["附件3"]["Sheet1"]
    add_report("## 附件3（Sheet1，负荷预测）")
    a3_missing = get_missing_mask(a3)
    a3_missing_n = mask_count(a3_missing)
    a3_date_nan = int(a3["日期"].isna().sum())
    a3_other_missing_n = a3_missing_n - a3_date_nan
    a3_missing_pos = mask_positions(a3, a3_missing)
    msg = (f"- 缺失值：共 {a3_missing_n} 个；其中“日期”列 {a3_date_nan} 个为合并单元格占位，"
           f"按约定 ffill，不视为真实缺失；其余字段缺失 {a3_other_missing_n} 个（仅报告，不填充）。")
    if a3_missing_n:
        msg += f" 样例位置：{a3_missing_pos}"
    add_report(msg)
    add_check("附件3 缺失值检查", a3_other_missing_n == 0,
              f"日期占位 {a3_date_nan} 个(已ffill)，其余缺失 {a3_other_missing_n} 个")

    a3["日期"] = a3["日期"].ffill()
    a3_dup_mask = a3.duplicated(subset=["日期", "预报时刻"], keep="first")
    a3_dup_n = int(a3_dup_mask.sum())
    a3_dup_samples = a3.loc[a3.duplicated(subset=["日期", "预报时刻"], keep=False),
                            ["日期", "预报时刻"]].drop_duplicates().head(MAX_POS_SAMPLE).astype(str).values.tolist()
    msg = f"- 重复（日期+预报时刻）：待删除 {a3_dup_n} 条。"
    if a3_dup_n:
        msg += f" 样例：{a3_dup_samples}"
    add_report(msg)
    add_check("附件3 重复检查", a3_dup_n == 0, f"重复 {a3_dup_n} 条")

    a3_forecast_cols = [str(c) for c in a3.columns
                        if str(c).startswith("预报") and str(c) != "预报时刻"]
    a3_upper_n, a3_upper_pos = flag_upper_bound(a3, a3_forecast_cols, LOAD_PV_UPPER)
    msg = f"- 负荷预测超出 {LOAD_PV_UPPER:.0f} kW：{a3_upper_n} 个（仅报告，不修改）。"
    if a3_upper_n:
        msg += f" 样例：{a3_upper_pos}"
    add_report(msg)
    add_check("附件3 负荷预测上界检查", a3_upper_n == 0, f"超限 {a3_upper_n} 个")

    a3, a3_neg_n, a3_neg_pos = flag_negative_and_clip(a3, a3_forecast_cols)
    msg = f"- 负负荷预测：{a3_neg_n} 个，已截断为 0。"
    if a3_neg_n:
        msg += f" 样例：{a3_neg_pos}"
    add_report(msg)

    cont = check_daily_date_continuity(a3["日期"], row_dups_expected=True)
    msg = (f"- 日期连续性：唯一 {cont['n_unique']} 天，缺日 {len(cont['missing_days'])}，"
           f"多余日 {len(cont['extra_days'])}。每日期有 4 个预报时刻，行级重复属正常结构。")
    if cont["missing_days"]:
        msg += f" 缺日：{cont['missing_days']}"
    if cont["extra_days"]:
        msg += f" 多余日：{cont['extra_days']}"
    add_report(msg)
    add_check("附件3 365天连续性", cont["passed"],
              "唯一日期集合连续" if cont["passed"] else "日期连续性异常")

    a3, a3_drop_n = drop_duplicate_rows(a3, ["日期", "预报时刻"])
    cleaned["附件3"] = a3

    # ============================== 附件4 ==============================
    a4 = raw_sheets["附件4"]["Sheet1"]
    a4_date = str(a4.columns[0])
    a4_cols = numeric_value_columns(a4, [a4_date])
    add_report("## 附件4（Sheet1，电价）")
    a4_missing = get_missing_mask(a4)
    a4_missing_n = mask_count(a4_missing)
    a4_missing_pos = mask_positions(a4, a4_missing)
    msg = f"- 缺失值：共 {a4_missing_n} 个（仅报告，不填充）。"
    if a4_missing_n:
        msg += f" 样例位置：{a4_missing_pos}"
    add_report(msg)
    add_check("附件4 缺失值检查", a4_missing_n == 0, f"缺失 {a4_missing_n} 个")

    a4_dup_rows, a4_dup_cells, a4_dup_dates = check_duplicates_wide(a4, a4_date)
    msg = (f"- 重复：重复日期行 {a4_dup_rows} 行；展开后日期+时段重复单元格(不含首条) "
           f"{a4_dup_cells} 个。")
    if a4_dup_rows:
        msg += f" 样例日期：{a4_dup_dates}"
    add_report(msg)
    add_check("附件4 重复检查", a4_dup_rows == 0, f"重复日期行 {a4_dup_rows} 行")

    a4_price_bad, a4_price_pos = flag_price_nonpositive(a4, a4_cols)
    msg = f"- 电价<=0：{a4_price_bad} 个（仅报告，不修改）。"
    if a4_price_bad:
        msg += f" 样例：{a4_price_pos}"
    add_report(msg)
    add_check("附件4 电价<=0检查", a4_price_bad == 0, f"可疑 {a4_price_bad} 个")

    cont = check_daily_date_continuity(a4[a4_date], row_dups_expected=False)
    msg = (f"- 日期连续性：唯一 {cont['n_unique']} 天，缺日 {len(cont['missing_days'])}，"
           f"多余日 {len(cont['extra_days'])}，重复日 {cont['dup_count']}。")
    if cont["missing_days"]:
        msg += f" 缺日：{cont['missing_days']}"
    if cont["extra_days"]:
        msg += f" 多余日：{cont['extra_days']}"
    add_report(msg)
    add_check("附件4 365天连续性", cont["passed"],
              "唯一日期集合连续" if cont["passed"] else "日期连续性异常")

    a4, a4_drop_n = drop_duplicate_rows(a4, [a4_date])
    cleaned["附件4"] = a4

    # ============================== 一致性检查 ==============================
    add_report("## 一致性检查：附件2 与 附件4 的“日期列 + 144 个时间列”")
    for a2_key, label in [("小区负载", "附件2_小区负载"),
                          ("光伏发电实际功率", "附件2_光伏实际功率")]:
        cmp = compare_wide_consistency(raw_sheets["附件2"][a2_key],
                                       raw_sheets["附件4"]["Sheet1"], label, "附件4")
        if cmp["passed"]:
            add_report(f"- {label} 与 附件4：通过"
                       f"（日期列与 {cmp['n_cols_a'] - 1} 个时间列完全一致）")
        else:
            add_report(f"- {label} 与 附件4：不通过")
            if not cmp["col_match"]:
                add_report(f"  - 列名不一致：{cmp['col_diff'][:MAX_POS_SAMPLE]}")
            if not cmp["date_match"]:
                add_report(f"  - 日期值不一致的 Excel 行号：{cmp['date_diff_idx']}")
        add_check(f"{label} 与 附件4 一致性", cmp["passed"],
                  "日期列+时间列完全一致" if cmp["passed"] else "存在不一致")

    # ---------- 4. 写出清洗后的 CSV ----------
    add_report("## 输出文件")
    for key, df in cleaned.items():
        path = OUTPUT_CSV[key]
        try:
            df.to_csv(path, index=False, encoding="utf-8-sig")
            add_report(f"- {path.name}：{df.shape[0]} 行 x {df.shape[1]} 列")
        except Exception as exc:
            add_report(f"- {path.name}：写出失败：{exc}")

    # ---------- 5. 写出清洗报告 ----------
    header = [
        "# 01 数据清洗检查报告",
        "",
        f"- 输入文件：{', '.join(INPUT_FILES.values())}",
        f"- 输出目录：{OUTPUT_DIR}",
        f"- 日期连续性区间：2025-01-01 至 2025-12-31（应恰好 365 天）",
        f"- 负荷/光伏合理量级上界：{LOAD_PV_UPPER:.0f} kW（只报告，不修改）",
        f"- 光伏夜间窗口：19:30 - 05:30（严格 >0 报告，无容差）",
        "",
        "## 处理规则说明",
        "1. 附件3 日期列合并单元格占位 NaN：向下填充（ffill），不视为真实缺失。",
        "2. 负负荷、负光伏：报告后截断为 0。",
        "3. 重复记录：保留第一条，删除后续重复并记录条数。",
        "4. 缺失值：只报告，不自动填充。",
        "5. 电价<=0、负荷/光伏超上界、光伏夜间非零：只报告，不修改。",
        "6. 储能 12000 kWh 为模型约束参数，不进入清洗阈值。",
        "",
    ]
    report_text = "\n".join(header + report)
    try:
        OUTPUT_REPORT.write_text(report_text, encoding="utf-8")
        print(f"\n清洗报告已写出：{OUTPUT_REPORT}")
    except Exception as exc:
        print(f"[错误] 写出报告失败：{exc}")

    # ---------- 6. 打印清洗检查清单 ----------
    print("\n" + "=" * 90)
    print("清洗检查清单（每项标注 通过/不通过）")
    print("=" * 90)
    for name, passed, detail in checklist:
        status = "通过" if passed else "不通过"
        print(f"[{status}] {name}：{detail}")
    print("=" * 90)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[严重错误] {exc}")
        traceback.print_exc()
        sys.exit(1)
