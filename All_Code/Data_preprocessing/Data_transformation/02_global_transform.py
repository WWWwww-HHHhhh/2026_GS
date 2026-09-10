#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""02_global_transform.py -- 2026 CUMCM C 题 数据转换（Data_clean -> Data_transformation）。

将上一阶段 Data_clean 中的 *_clean.csv 标准化为统一内部格式，并导出模板对齐映射。

本脚本只做"由原值严格推导"的转换，不新增、不伪造任何数据：
  1. 时间映射：附件 1/2/4 的时间标签按"时段结束时刻"映射为内部序号 1..144。
     0:10 -> 时段1 (0:00,0:10]；...；24:00 / 0:00+1 -> 时段144 (23:50,24:00]。
  2. 单位换算：负载、光伏为功率 kW，乘 Delta t = 1/6 h 得到每时段电量 kWh；
     电价为 元/kWh，保持不变。附件3 的小时级光伏预报保留原 kW 结构（不插值）。
  3. 日期解析：附件 2/3/4 的日期列统一转为 datetime；附件3 保留
     "预报时刻(0/6/12/18) + 预测1~24小时" 结构，日期只在同一天 4 个发布时刻块内向下填充。
  4. 模板对齐：导出 time_map.csv（内部 1..144 与模板区间标签双向映射）与
     template_map.csv（result1~result4 各 sheet 的填写位置映射），不改动模板表头。
  5. 输出：df_p1.parquet / df_load.parquet / df_pv.parquet / df_fcst.parquet /
     df_price.parquet / time_map.csv / template_map.csv。
  6. 校验：每文件行数 = 144 / 365 / 365x4；打印转换后 min/max；144 个时段列无缺漏、无重复。

本脚本不进行建模，因此不会把整点值复制 6 次、不会把"预测1小时"当作前 1 小时、
也不会在 0 点决策中使用当天未来值（预报保持 24 列原始小时结构，不做任何平移）。

依赖：numpy、pandas、pyarrow。模板映射优先使用内置的确定性布局（依据官方
result1~result4 模板），若本机存在 result*.xlsx 且装有 openpyxl 可另行核对表头。

运行：
    python 02_global_transform.py [--clean-dir ...] [--out-dir ...]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

N_PERIODS = 144
N_DAYS = 365
N_FORECAST_HORIZON = 24
ISSUE_HOURS = (0, 6, 12, 18)
N_FCST_ROWS = N_DAYS * len(ISSUE_HOURS)
DT_H = 1.0 / 6.0

T_COLS = [f"T{i:03d}" for i in range(1, N_PERIODS + 1)]
FH_COLS = [f"fh_{i:02d}" for i in range(1, N_FORECAST_HORIZON + 1)]

ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk")


def _fmt_hm(minutes: int) -> str:
    h, m = divmod(int(round(minutes)), 60)
    return f"{h}:{m:02d}"


def _data_label(idx: int) -> str:
    if idx == N_PERIODS:
        return "0:00+1"
    return _fmt_hm(idx * 10)


def _period_start(idx: int) -> str:
    return _fmt_hm((idx - 1) * 10)


def _period_end(idx: int) -> str:
    return _fmt_hm(idx * 10)


def _interval_label(idx: int) -> str:
    return f"{_period_start(idx)}-{_period_end(idx)}"


def _template_endpoint(k: int, first_plus: bool) -> str:
    minutes = k * 10
    if minutes == 1440:
        return "0:00+1" if first_plus else "0:00"
    if minutes > 1440:
        minutes -= 1440
        return f"{minutes // 60}:{minutes % 60:02d}+1"
    h, m = divmod(minutes, 60)
    if h == 7 and m == 0:
        return "7:0" if not first_plus else "7:00"
    return f"{h}:{m:02d}"


def _template_label(k: int, first_plus: bool) -> str:
    return f"{_template_endpoint(k, first_plus)}-{_template_endpoint(k + 1, first_plus)}"


def template_col_label(idx: int) -> str:
    """result2/3/4-2/4-3 横向 sheet 中第 idx 个时段列的表头区间标签。"""
    return _template_label(idx, first_plus=False)


def template_row_label(idx: int) -> str:
    """result1 纵向 sheet 中第 idx 个时段行的区间标签。"""
    return _template_label(idx, first_plus=True)


def parse_time_to_index(value) -> int:
    """把时段结束时刻标签映射为内部序号 1..144。

    支持：Excel 小数(0.006944... / 1.0)、字符串("00:10" / "00:10:00" /
    "24:00" / "0:00+1" / "0:00(+1)")、datetime.time / Timestamp / Timedelta。
    """
    if value is None:
        raise ValueError("空时间标签")
    if isinstance(value, (pd.Timestamp, _dt.datetime)):
        value = value.time()
    if isinstance(value, _dt.time):
        minutes = value.hour * 60 + value.minute + value.second / 60.0
    elif isinstance(value, pd.Timedelta):
        minutes = value.total_seconds() / 60.0
    elif isinstance(value, (int, np.integer)):
        if 1 <= int(value) <= N_PERIODS:
            return int(value)
        minutes = int(round(float(value) * 1440.0))
    elif isinstance(value, (float, np.floating)):
        if pd.isna(value):
            raise ValueError("空时间标签")
        minutes = int(round(float(value) * 1440.0))
    else:
        s = str(value).strip().replace("\uFF1A", ":")
        m = re.match(r"^[Tt]?0*(\d{1,3})$", s)
        if m and 1 <= int(m.group(1)) <= N_PERIODS:
            return int(m.group(1))
        minutes = _string_time_to_minutes(s)

    idx = int(round(minutes / 10.0))
    if idx < 1 or idx > N_PERIODS:
        raise ValueError(f"时间无法映射为 1..{N_PERIODS}: {value!r}")
    return idx


def _string_time_to_minutes(s: str) -> int:
    s = s.strip().replace("\uFF1A", ":")
    if s in ("", "nan", "None", "NaT"):
        raise ValueError("空时间标签")

    plus1 = False
    core = s
    m = re.match(r"^(.*?)\s*[\(\[]?\s*\+1\s*[\)\]]?$", s)
    if m and m.group(1):
        plus1 = True
        core = m.group(1).strip()
    else:
        m2 = re.match(r"^(.*?)\s*[\(\[]\s*1\s*[\)\]]$", s)
        if m2 and m2.group(1):
            plus1 = True
            core = m2.group(1).strip()

    if core in ("24:00", "24:00:00"):
        return 1440

    hm = re.match(r"^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$", core)
    if not hm:
        try:
            return int(round(float(s) * 1440.0))
        except ValueError:
            raise ValueError(f"无法解析时间: {s!r}")

    h, mi = int(hm.group(1)), int(hm.group(2))
    sec = int(hm.group(3)) if hm.group(3) else 0
    minutes = h * 60 + mi + sec / 60.0
    if plus1:
        minutes += 1440.0
    return int(round(minutes))


def col_to_time_idx(name) -> int:
    """把列名/表头映射为内部序号 1..144（支持 T001、整数、时段结束标签）。"""
    s = str(name).strip()
    m = re.match(r"^[Tt]?0*(\d{1,3})$", s)
    if m and 1 <= int(m.group(1)) <= N_PERIODS:
        return int(m.group(1))
    return parse_time_to_index(s)


def find_col(columns, keywords, exclude=()):
    for kw in keywords:
        for c in columns:
            if any(x in str(c) for x in exclude):
                continue
            if kw.lower() in str(c).lower():
                return c
    return None


def read_csv_robust(path: Path) -> pd.DataFrame:
    last_err = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc)
        except (UnicodeDecodeError, LookupError) as err:
            last_err = err
    raise ValueError(f"无法读取 {path}: {last_err}")


def _parse_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def load_p1(path: Path) -> pd.DataFrame:
    df = read_csv_robust(path)
    cols = list(df.columns)
    time_col = find_col(cols, ["时间", "时刻", "time", "时段"])
    price_col = find_col(cols, ["电价", "购电价", "price"], exclude=["光伏", "负载", "负荷"])
    load_col = find_col(cols, ["负载", "负荷", "load"], exclude=["光伏", "电价"])
    pv_col = find_col(cols, ["光伏", "pv", "solar", "预测功率", "发电"], exclude=["负载", "负荷", "电价"])

    if time_col is None:
        for c in cols:
            try:
                df[c].map(parse_time_to_index)
                time_col = c
                break
            except Exception:
                continue
    missing = [k for k, c in (("时间", time_col), ("电价", price_col), ("负载", load_col), ("光伏", pv_col)) if c is None]
    if missing:
        raise ValueError(f"{path.name} 缺少列: {missing}；实际列: {cols}")

    idx = df[time_col].map(parse_time_to_index)
    out = pd.DataFrame({
        "time_idx": idx.astype("int16"),
        "time_label": idx.map(_data_label),
        "price": pd.to_numeric(df[price_col], errors="coerce"),
        "load_kwh": pd.to_numeric(df[load_col], errors="coerce") * DT_H,
        "pv_kwh": pd.to_numeric(df[pv_col], errors="coerce") * DT_H,
    }).sort_values("time_idx").reset_index(drop=True)
    return out


def load_wide_series_dataframe(df: pd.DataFrame, scale: float, source: str) -> pd.DataFrame:
    cols = list(df.columns)
    date_col = find_col(cols, ["日期", "date", "时间"])
    if date_col is None and len(cols) == N_PERIODS + 1:
        date_col = cols[0]
    if date_col is None:
        raise ValueError(f"{source} 未找到日期列；列: {cols}")

    time_cols = [c for c in cols if c != date_col]
    pairs = []
    for c in time_cols:
        try:
            pairs.append((col_to_time_idx(c), c))
        except ValueError as err:
            raise ValueError(f"{source} 列名无法映射: {c!r}: {err}")

    idx_series = pd.Series([p[0] for p in pairs])
    if idx_series.duplicated().any():
        raise ValueError(f"{source} 存在重复时段列")
    if len(pairs) != N_PERIODS or set(idx_series) != set(range(1, N_PERIODS + 1)):
        raise ValueError(f"{source} 时段列数量错误: {len(pairs)}，应为 {N_PERIODS}")

    out = pd.DataFrame({"date": _parse_dates(df[date_col])})
    for k, src in sorted(pairs, key=lambda p: p[0]):
        out[f"T{k:03d}"] = pd.to_numeric(df[src], errors="coerce") * scale
    return out.sort_values("date").reset_index(drop=True)


def load_wide_series(path: Path, scale: float) -> pd.DataFrame:
    df = read_csv_robust(path)
    return load_wide_series_dataframe(df, scale, path.name)


def _strip_kind(name: str, keywords) -> str:
    s = name
    for kw in keywords:
        s = s.replace(kw, "")
    return re.sub(r"[_\-\s\.\(\)]+", "", s)


def split_combined_att2(path: Path):
    df = read_csv_robust(path)
    cols = list(df.columns)
    date_col = find_col(cols, ["日期", "date", "时间"])
    if date_col is None and len(cols) >= 1:
        date_col = cols[0]
    if date_col is None:
        raise ValueError(f"{path.name} 未找到日期列")

    load_keys = ["负载", "负荷", "load", "Load"]
    pv_keys = ["光伏", "pv", "PV", "solar"]
    load_cols = [c for c in cols if c != date_col and any(k in str(c) for k in load_keys)]
    pv_cols = [c for c in cols if c != date_col and any(k in str(c) for k in pv_keys)]

    load_df = pv_df = None
    if len(load_cols) == N_PERIODS:
        rename = {c: _strip_kind(str(c), load_keys) for c in load_cols}
        load_df = df[[date_col] + load_cols].rename(columns=rename)
    if len(pv_cols) == N_PERIODS:
        rename = {c: _strip_kind(str(c), pv_keys) for c in pv_cols}
        pv_df = df[[date_col] + pv_cols].rename(columns=rename)

    if load_df is None and pv_df is None:
        raise ValueError(
            f"{path.name} 无法自动拆分负载/光伏（负载列 {len(load_cols)}，光伏列 {len(pv_cols)}）。"
            f"请将附件2 的两张表分别导出为 *_clean.csv。"
        )
    return load_df, pv_df


def load_fcst(path: Path) -> pd.DataFrame:
    df = read_csv_robust(path)
    cols = list(df.columns)
    date_col = find_col(cols, ["日期", "date"])
    issue_col = find_col(cols, ["预报时刻", "发布时刻", "时刻", "issue"], exclude=["日期"])
    fh_cols = [c for c in cols if re.search(r"(?:预报|预测|fh)[\s_]*(\d{1,2})", str(c))]

    if date_col is None or issue_col is None or len(fh_cols) != N_FORECAST_HORIZON:
        raise ValueError(
            f"{path.name} 结构不符: 日期列={date_col!r}, 预报时刻列={issue_col!r}, "
            f"预报列数={len(fh_cols)}（应为 {N_FORECAST_HORIZON}）。实际列: {cols}"
        )

    issue = []
    for v in df[issue_col]:
        s = str(v).strip()
        m = re.match(r"^(\d{1,2}):(\d{2})", s)
        if m:
            issue.append(int(m.group(1)))
        elif re.fullmatch(r"\d{1,2}", s):
            issue.append(int(s))
        else:
            raise ValueError(f"{path.name} 预报时刻无法解析: {v!r}")

    issue_series = pd.Series(issue, dtype="int16")
    if set(issue_series.unique()) != set(ISSUE_HOURS):
        raise ValueError(f"{path.name} 预报时刻集合错误: {sorted(issue_series.unique())}，应为 {list(ISSUE_HOURS)}")

    date_series = _parse_dates(df[date_col])
    block_id = (issue_series == ISSUE_HOURS[0]).cumsum()
    date_series = date_series.groupby(block_id).ffill()

    horizon_order = []
    for c in fh_cols:
        m = re.search(r"(\d{1,2})", str(c))
        horizon_order.append((int(m.group(1)), c))
    horizon_order.sort(key=lambda x: x[0])

    out = pd.DataFrame({"date": date_series, "issue_hour": issue_series})
    for k, (h, src) in enumerate(horizon_order, start=1):
        if h != k:
            raise ValueError(f"{path.name} 预报列顺序错误: 第 {k} 列实际步长为 {h}")
        out[f"fh_{k:02d}"] = pd.to_numeric(df[src], errors="coerce")
    return out.sort_values(["date", "issue_hour"]).reset_index(drop=True)


def discover_inputs(clean_dir: Path):
    csvs = sorted(p for p in clean_dir.glob("*.csv") if not p.name.startswith("_"))

    def _pick(keywords, exclude=()):
        for p in csvs:
            name = p.name.lower()
            if any(ex in name for ex in exclude):
                continue
            if any(kw in name for kw in keywords):
                return p
        return None

    p1 = _pick(["附件1", "附件一", "att1", "p1", "data1"])
    fcst = _pick(["附件3", "附件三", "att3", "fcst", "forecast"])
    price = _pick(["附件4", "附件四", "att4", "price", "电价", "购电"])
    load = _pick(["负载", "负荷", "load"])
    pv = _pick(["光伏", "pv", "solar"])
    combined = None
    if load is None or pv is None:
        combined = _pick(["附件2", "附件二", "att2", "data2"], exclude=["附件1", "附件3", "附件4"])
    return {"p1": p1, "load": load, "pv": pv, "fcst": fcst, "price": price, "att2_combined": combined}


def build_time_map() -> pd.DataFrame:
    rows = []
    for k in range(1, N_PERIODS + 1):
        rows.append({
            "time_idx": k,
            "period_start": _period_start(k),
            "period_end": _period_end(k),
            "interval_label": _interval_label(k),
            "data_label": _data_label(k),
            "template_col_label": template_col_label(k),
            "template_row_label": template_row_label(k),
        })
    return pd.DataFrame(rows)


TEMPLATE_LAYOUT = {
    "result1": {
        "sheets": [
            {"index": 1, "name": "计划购电量", "orientation": "vertical_144", "field": "购电量"},
            {"index": 2, "name": "充放电量", "orientation": "window_4h"},
        ],
    },
    "result2": {
        "sheets": [
            {"index": 1, "name": "计划购电量", "orientation": "wide_144", "field": "计划购电量"},
            {"index": 2, "name": "充放电量", "orientation": "window_4h"},
            {"index": 3, "name": "紧急购电量", "orientation": "event"},
        ],
    },
    "result3": {
        "sheets": [
            {"index": 1, "name": "计划购电量", "orientation": "wide_144", "field": "计划购电量"},
            {"index": 2, "name": "调整购电量", "orientation": "wide_144", "field": "调整购电量"},
            {"index": 3, "name": "充放电量", "orientation": "window_4h"},
            {"index": 4, "name": "紧急购电量", "orientation": "event"},
        ],
    },
    "result4-2": {
        "sheets": [
            {"index": 1, "name": "计划购电量", "orientation": "wide_144", "field": "计划购电量"},
            {"index": 2, "name": "充放电量", "orientation": "window_4h"},
            {"index": 3, "name": "紧急购电量", "orientation": "event"},
        ],
    },
    "result4-3": {
        "sheets": [
            {"index": 1, "name": "计划购电量", "orientation": "wide_144", "field": "计划购电量"},
            {"index": 2, "name": "调整购电量", "orientation": "wide_144", "field": "调整购电量"},
            {"index": 3, "name": "充放电量", "orientation": "window_4h"},
            {"index": 4, "name": "紧急购电量", "orientation": "event"},
        ],
    },
}

WINDOW_LABELS = ["0:00-4:00", "4:00-8:00", "8:00-12:00", "12:00-16:00", "16:00-20:00", "20:00-24:00"]
WIDE_DATA_ROWS = (2, 335)
VERTICAL_PERIOD_ROWS = (2, 1 + N_PERIODS)


def build_template_map() -> pd.DataFrame:
    rows = []
    for result, spec in TEMPLATE_LAYOUT.items():
        for sheet in spec["sheets"]:
            if sheet["orientation"] == "vertical_144":
                for k in range(1, N_PERIODS + 1):
                    rows.append({
                        "result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                        "field": sheet["field"], "kind": "period", "time_idx": k,
                        "label": template_row_label(k),
                        "row_start": 1 + k, "row_end": 1 + k,
                        "col_start": 2, "col_end": 2,
                        "note": "纵向模板：标签列 A 已填，值写入 B 列",
                    })
            elif sheet["orientation"] == "wide_144":
                for k in range(1, N_PERIODS + 1):
                    rows.append({
                        "result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                        "field": sheet["field"], "kind": "period", "time_idx": k,
                        "label": template_col_label(k),
                        "row_start": WIDE_DATA_ROWS[0], "row_end": WIDE_DATA_ROWS[1],
                        "col_start": 1 + k, "col_end": 1 + k,
                        "note": "横向模板：日期列 A，时段列 B..EO",
                    })
                rows.append({"result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                             "field": "日期", "kind": "date", "time_idx": "",
                             "label": "日期\\时间", "row_start": WIDE_DATA_ROWS[0], "row_end": WIDE_DATA_ROWS[1],
                             "col_start": 1, "col_end": 1, "note": "2025-02-01..2025-12-31，共 334 行"})
                rows.append({"result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                             "field": "全天购电量", "kind": "summary", "time_idx": "",
                             "label": "全天购电量", "row_start": WIDE_DATA_ROWS[0], "row_end": WIDE_DATA_ROWS[1],
                             "col_start": N_PERIODS + 2, "col_end": N_PERIODS + 2, "note": "第 146 列"})
                rows.append({"result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                             "field": "全天购电费", "kind": "summary", "time_idx": "",
                             "label": "全天购电费", "row_start": WIDE_DATA_ROWS[0], "row_end": WIDE_DATA_ROWS[1],
                             "col_start": N_PERIODS + 3, "col_end": N_PERIODS + 3, "note": "第 147 列"})
            elif sheet["orientation"] == "window_4h":
                has_date = result != "result1"
                for wi, label in enumerate(WINDOW_LABELS):
                    rows.append({
                        "result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                        "field": "时间段", "kind": "window", "time_idx": "",
                        "label": label,
                        "row_start": 2 + wi, "row_end": (2 + wi) if result == "result1" else "",
                        "col_start": 1 if result == "result1" else 2,
                        "col_end": 1 if result == "result1" else 2,
                        "note": "6 个 4 小时窗口" if result == "result1" else "每个日期 6 个窗口，按天扩展行",
                    })
                if has_date:
                    rows.append({"result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                                 "field": "日期", "kind": "date", "time_idx": "", "label": "日期",
                                 "row_start": 2, "row_end": "", "col_start": 1, "col_end": 1,
                                 "note": "每个日期 6 个窗口行"})
                rows.append({"result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                             "field": "充电量", "kind": "window", "time_idx": "", "label": "充电量",
                             "row_start": 2, "row_end": "", "col_start": 2 if result == "result1" else 3,
                             "col_end": 2 if result == "result1" else 3, "note": ""})
                rows.append({"result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                             "field": "放电量", "kind": "window", "time_idx": "", "label": "放电量",
                             "row_start": 2, "row_end": "", "col_start": 3 if result == "result1" else 4,
                             "col_end": 3 if result == "result1" else 4, "note": ""})
                rows.append({"result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                             "field": "时刻", "kind": "window", "time_idx": "", "label": "时刻",
                             "row_start": 2, "row_end": "", "col_start": 4 if result == "result1" else 5,
                             "col_end": 4 if result == "result1" else 5, "note": "窗口边界时刻"})
                rows.append({"result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                             "field": "储电量", "kind": "window", "time_idx": "", "label": "储电量",
                             "row_start": 2, "row_end": "", "col_start": 5 if result == "result1" else 6,
                             "col_end": 5 if result == "result1" else 6, "note": ""})
            elif sheet["orientation"] == "event":
                rows.append({"result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                             "field": "日期", "kind": "date", "time_idx": "", "label": "日期",
                             "row_start": 2, "row_end": "", "col_start": 1, "col_end": 1,
                             "note": "发生紧急购电的日期，按事件扩展行"})
                rows.append({"result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                             "field": "购电时间段", "kind": "event", "time_idx": "", "label": "购电时间段",
                             "row_start": 2, "row_end": "", "col_start": 2, "col_end": 2, "note": ""})
                rows.append({"result": result, "sheet_index": sheet["index"], "sheet": sheet["name"],
                             "field": "购电量", "kind": "event", "time_idx": "", "label": "购电量",
                             "row_start": 2, "row_end": "", "col_start": 3, "col_end": 3, "note": ""})
    return pd.DataFrame(rows)


def print_stats(name: str, df: pd.DataFrame, expected_rows: int, value_cols, time_cols=None):
    print(f"\n[{name}]")
    print(f"  行数 = {len(df)} (预期 {expected_rows}) -> {'OK' if len(df) == expected_rows else 'FAIL'}")
    vals = df[value_cols].astype("float64")
    stacked = vals.stack(dropna=True)
    if len(stacked):
        print(f"  min = {stacked.min():.6f}   max = {stacked.max():.6f}")
    else:
        print("  min/max 无法计算（无有效数值）")
    if time_cols is not None:
        missing = [c for c in time_cols if c not in df.columns]
        dup = [c for c in df.columns if list(df.columns).count(c) > 1]
        nan_cells = int(df[time_cols].isna().sum().sum())
        print(f"  时段列数 = {len([c for c in time_cols if c in df.columns])}/{len(time_cols)}"
              f"  缺列 = {missing}  重复列 = {dup}  空值 = {nan_cells}")
        print(f"  144 时段列完整性 -> {'OK' if (not missing and not dup and nan_cells == 0) else 'FAIL'}")


def validate_p1(df: pd.DataFrame) -> bool:
    print_stats("df_p1", df, N_PERIODS, ["price", "load_kwh", "pv_kwh"])
    idx = df["time_idx"]
    ok = len(idx) == N_PERIODS and set(idx) == set(range(1, N_PERIODS + 1)) and idx.is_monotonic_increasing
    ok &= df[["price", "load_kwh", "pv_kwh"]].isna().sum().sum() == 0
    print(f"  time_idx 1..144 无缺漏/无重复且有序 -> {'OK' if ok else 'FAIL'}")
    return bool(ok)


def validate_wide(df: pd.DataFrame) -> bool:
    ok = len(df) == N_DAYS
    ok &= df["date"].is_unique
    ok &= df[["date"] + T_COLS].notna().all().all()
    ok &= all(list(df.columns).count(c) == 1 for c in T_COLS)
    return bool(ok)


def validate_fcst(df: pd.DataFrame) -> bool:
    ok = len(df) == N_FCST_ROWS
    ok &= df["date"].nunique() == N_DAYS
    ok &= df[["date", "issue_hour"] + FH_COLS].notna().all().all()
    if ok:
        counts = df.groupby("date")["issue_hour"].agg(list)
        ok &= all(list(c) == list(ISSUE_HOURS) for c in counts)
    return bool(ok)


def _selfcheck() -> bool:
    checks = [
        parse_time_to_index("00:10") == 1,
        parse_time_to_index("00:10:00") == 1,
        parse_time_to_index("23:50:00") == 143,
        parse_time_to_index("0:00+1") == 144,
        parse_time_to_index("0:00(+1)") == 144,
        parse_time_to_index("24:00") == 144,
        parse_time_to_index(1.0) == 144,
        parse_time_to_index(0.006944444444444444) == 1,
        parse_time_to_index("T042") == 42,
        col_to_time_idx("0:20:00") == 2,
        col_to_time_idx("T144") == 144,
        _data_label(1) == "0:10",
        _data_label(144) == "0:00+1",
        _interval_label(1) == "0:00-0:10",
        _interval_label(144) == "23:50-24:00",
        template_col_label(1) == "0:10-0:20",
        template_col_label(42) == "7:0-7:10",
        template_col_label(143) == "23:50-0:00+1",
        template_col_label(144) == "0:00-0:10+1",
        template_row_label(1) == "0:10-0:20",
        template_row_label(42) == "7:00-7:10",
        template_row_label(143) == "23:50-0:00+1",
        template_row_label(144) == "0:00+1-0:10+1",
    ]
    ok = all(checks)
    print("selfcheck:", "OK" if ok else "FAIL")
    if not ok:
        for i, chk in enumerate(checks):
            if not chk:
                print(f"  check #{i} failed")
    return ok


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="2026 CUMCM C 题 数据转换")
    script_dir = Path(__file__).resolve().parent
    parser.add_argument("--clean-dir", default=str(script_dir.parent / "Data_clean"))
    parser.add_argument("--out-dir", default=str(script_dir))
    parser.add_argument("--selfcheck", action="store_true", help="只校验时间映射逻辑后退出")
    args = parser.parse_args(argv)

    if args.selfcheck:
        return 0 if _selfcheck() else 1

    clean_dir = Path(args.clean_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("02_global_transform.py")
    print(f"  clean_dir = {clean_dir}")
    print(f"  out_dir   = {out_dir}")
    print("=" * 70)

    time_map = build_time_map()
    time_map.to_csv(out_dir / "time_map.csv", index=False, encoding="utf-8-sig")
    print("已写出 time_map.csv (144 行)")

    template_map = build_template_map()
    template_map.to_csv(out_dir / "template_map.csv", index=False, encoding="utf-8-sig")
    print(f"已写出 template_map.csv ({len(template_map)} 行)")
    print("  注：模板映射按官方 result1~result4 布局的确定性位置生成；写入结果前请再核对实际模板表头。")

    discovered = [p.name for p in clean_dir.glob("*.csv")] if clean_dir.exists() else []
    print(f"\n发现 clean csv: {discovered}")

    inputs = discover_inputs(clean_dir) if clean_dir.exists() else {}
    errors = []

    def _run(name, fn):
        try:
            return fn()
        except Exception as err:
            errors.append(f"{name}: {err}")
            return None

    if inputs.get("p1") is not None:
        p1 = _run("p1 (附件1)", lambda: load_p1(inputs["p1"]))
        if p1 is not None:
            validate_p1(p1)
            p1.to_parquet(out_dir / "df_p1.parquet", index=False)
            print(f"  写出 df_p1.parquet <- {inputs['p1'].name}")
    else:
        errors.append("p1 (附件1) 输入缺失")

    load_df = pv_df = None
    if inputs.get("load") is not None:
        load_df = _run("load (附件2 负载)", lambda: load_wide_series(inputs["load"], DT_H))
    if inputs.get("pv") is not None:
        pv_df = _run("pv (附件2 光伏)", lambda: load_wide_series(inputs["pv"], DT_H))
    if (load_df is None or pv_df is None) and inputs.get("att2_combined") is not None:
        try:
            ldf, pdf = split_combined_att2(inputs["att2_combined"])
            if load_df is None and ldf is not None:
                load_df = load_wide_series_dataframe(ldf, DT_H, inputs["att2_combined"].name)
            if pv_df is None and pdf is not None:
                pv_df = load_wide_series_dataframe(pdf, DT_H, inputs["att2_combined"].name)
        except Exception as err:
            errors.append(f"att2 拆分: {err}")

    if load_df is not None:
        print_stats("df_load", load_df, N_DAYS, T_COLS, T_COLS)
        validate_wide(load_df)
        load_df.to_parquet(out_dir / "df_load.parquet", index=False)
        print("  写出 df_load.parquet")
    else:
        errors.append("load (附件2 负载) 输入缺失或无法生成")

    if pv_df is not None:
        print_stats("df_pv", pv_df, N_DAYS, T_COLS, T_COLS)
        validate_wide(pv_df)
        pv_df.to_parquet(out_dir / "df_pv.parquet", index=False)
        print("  写出 df_pv.parquet")
    else:
        errors.append("pv (附件2 光伏) 输入缺失或无法生成")

    if inputs.get("fcst") is not None:
        fcst = _run("fcst (附件3)", lambda: load_fcst(inputs["fcst"]))
        if fcst is not None:
            print_stats("df_fcst", fcst, N_FCST_ROWS, FH_COLS)
            validate_fcst(fcst)
            fcst.to_parquet(out_dir / "df_fcst.parquet", index=False)
            print(f"  写出 df_fcst.parquet <- {inputs['fcst'].name} (预报保持 kW 小时结构)")
    else:
        errors.append("fcst (附件3) 输入缺失")

    if inputs.get("price") is not None:
        price = _run("price (附件4)", lambda: load_wide_series(inputs["price"], 1.0))
        if price is not None:
            print_stats("df_price", price, N_DAYS, T_COLS, T_COLS)
            validate_wide(price)
            price.to_parquet(out_dir / "df_price.parquet", index=False)
            print(f"  写出 df_price.parquet <- {inputs['price'].name}")
    else:
        errors.append("price (附件4) 输入缺失")

    print("\n" + "=" * 70)
    if errors:
        print("存在未完成项，请修复后重跑：")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("转换完成，所有校验通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
