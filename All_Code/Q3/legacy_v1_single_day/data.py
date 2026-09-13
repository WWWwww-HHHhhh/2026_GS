from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from config import DT_HOURS, T, ProjectPaths


@dataclass
class Q3Dataset:
    dates: pd.DatetimeIndex
    price_cny_per_kwh: np.ndarray
    load_power_kw: np.ndarray
    pv_power_kw: np.ndarray
    pv_forecast: pd.DataFrame

    @property
    def load_energy_kwh(self) -> np.ndarray:
        return self.load_power_kw * DT_HOURS

    @property
    def pv_energy_kwh(self) -> np.ndarray:
        return self.pv_power_kw * DT_HOURS

    def day_index(self, date: str | pd.Timestamp) -> int:
        target = pd.Timestamp(date).normalize()
        matches = np.flatnonzero(self.dates == target)
        if len(matches) != 1:
            raise KeyError(f"数据中找不到唯一日期 {target.date()}")
        return int(matches[0])


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _numeric_matrix(frame: pd.DataFrame, expected_rows: int | None = None) -> np.ndarray:
    matrix = frame.iloc[:, 1:].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    if matrix.shape[1] != T:
        raise ValueError(f"预期每行 {T} 个区间，实际为 {matrix.shape[1]}")
    if expected_rows is not None and matrix.shape[0] != expected_rows:
        raise ValueError(f"预期 {expected_rows} 行，实际为 {matrix.shape[0]}")
    if not np.isfinite(matrix).all() or (matrix < 0).any():
        raise ValueError("负荷或光伏实测数据包含负数或非有限值")
    return matrix


def load_dataset(paths: ProjectPaths | None = None) -> Q3Dataset:
    paths = paths or ProjectPaths.discover()
    price_frame = _read_csv(paths.clean_data / "附件1_clean.csv")
    load_frame = _read_csv(paths.clean_data / "附件2_load_clean.csv")
    pv_frame = _read_csv(paths.clean_data / "附件2_pv_clean.csv")
    forecast_frame = _read_csv(paths.clean_data / "附件3_clean.csv")

    price = pd.to_numeric(price_frame["电价"], errors="raise").to_numpy(dtype=float)
    if price.shape != (T,) or not np.isfinite(price).all() or (price < 0).any():
        raise ValueError("附件1电价必须是 144 个非负有限值")

    load_dates = pd.DatetimeIndex(pd.to_datetime(load_frame.iloc[:, 0])).normalize()
    pv_dates = pd.DatetimeIndex(pd.to_datetime(pv_frame.iloc[:, 0])).normalize()
    if not load_dates.equals(pv_dates):
        raise ValueError("负荷日期与光伏日期没有逐日对齐")

    load_power = _numeric_matrix(load_frame)
    pv_power = _numeric_matrix(pv_frame, expected_rows=load_power.shape[0])

    forecast_frame = forecast_frame.copy()
    forecast_frame["日期"] = pd.to_datetime(forecast_frame["日期"]).dt.normalize()
    issue_text = forecast_frame["预报时刻"].astype(str).str.strip()
    issue_hour = issue_text.str.extract(r"^(\d{1,2})(?::\d{2})?$", expand=False)
    if issue_hour.isna().any():
        bad = issue_text[issue_hour.isna()].head(3).tolist()
        raise ValueError(f"附件3预报时刻格式无法识别，示例为 {bad}")
    forecast_frame["预报时刻"] = pd.to_numeric(issue_hour, errors="raise").astype(int)
    hour_columns = [f"预报{i}小时" for i in range(1, 25)]
    missing = [name for name in hour_columns if name not in forecast_frame.columns]
    if missing:
        raise ValueError(f"附件3缺少列 {missing}")
    forecast_frame[hour_columns] = forecast_frame[hour_columns].apply(
        pd.to_numeric, errors="raise"
    )
    values = forecast_frame[hour_columns].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("附件3光伏预报包含负数或非有限值")

    return Q3Dataset(
        dates=load_dates,
        price_cny_per_kwh=price,
        load_power_kw=load_power,
        pv_power_kw=pv_power,
        pv_forecast=forecast_frame,
    )
