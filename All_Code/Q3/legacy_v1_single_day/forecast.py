"""Q3 的因果点预测接口。

负荷部分是可运行的因果基线，只使用决策日前的历史日，并在日内更新时
使用已经观测到的当日负荷做比例校正。光伏部分直接读取附件3在 0、6、12、18
点发布的 24 小时预报，再插值到 10 分钟区间。
"""

from __future__ import annotations

import numpy as np

from config import DT_HOURS, T
from data import Q3Dataset


def causal_load_point(
    dataset: Q3Dataset,
    day_idx: int,
    issue_hour: int,
    same_weekday_days: int = 8,
) -> np.ndarray:
    """返回整日负荷电量预测，任何位置都不读取当前时刻之后的实测值。"""
    if day_idx <= 0:
        return np.zeros(T, dtype=float)

    weekday = dataset.dates[day_idx].weekday()
    candidates = [
        idx
        for idx in range(day_idx - 1, -1, -1)
        if dataset.dates[idx].weekday() == weekday
    ][:same_weekday_days]
    if not candidates:
        candidates = list(range(max(0, day_idx - 7), day_idx))

    point_kw = np.median(dataset.load_power_kw[candidates], axis=0)
    issue_slot = issue_hour * 6
    if issue_slot > 0:
        observed = dataset.load_power_kw[day_idx, :issue_slot]
        baseline = point_kw[:issue_slot]
        valid = baseline > 1.0e-6
        if valid.any():
            ratio = float(np.median(observed[valid] / baseline[valid]))
            ratio = float(np.clip(ratio, 0.70, 1.30))
            point_kw = point_kw.copy()
            point_kw[issue_slot:] *= ratio
            point_kw[:issue_slot] = observed
    return np.maximum(point_kw, 0.0) * DT_HOURS


def _forecast_row(dataset: Q3Dataset, day_idx: int, issue_hour: int) -> np.ndarray:
    date = dataset.dates[day_idx]
    mask = (
        (dataset.pv_forecast["日期"] == date)
        & (dataset.pv_forecast["预报时刻"] == issue_hour)
    )
    rows = dataset.pv_forecast.loc[mask, [f"预报{i}小时" for i in range(1, 25)]]
    if len(rows) != 1:
        raise ValueError(f"{date.date()} {issue_hour}:00 的光伏预报不是唯一一行")
    return rows.iloc[0].to_numpy(dtype=float)


def pv_point_from_official_forecast(
    dataset: Q3Dataset,
    day_idx: int,
    issue_hour: int,
) -> np.ndarray:
    """把附件3的小时功率预报插值成整日 10 分钟电量。

    issue_hour 之前的位置填入已实现值，只是为了形成整日向量。优化器只会读取
    issue_hour 之后的部分，因此不会发生未来信息泄露。
    """
    issue_slot = issue_hour * 6
    official_kw = _forecast_row(dataset, day_idx, issue_hour)
    if issue_slot == 0:
        anchor_kw = 0.0
    else:
        anchor_kw = float(dataset.pv_power_kw[day_idx, issue_slot - 1])

    minute_grid = np.arange(0, 24 * 60 + 1, 60, dtype=float)
    power_grid = np.concatenate(([anchor_kw], official_kw))
    future_count = T - issue_slot
    interval_end_minutes = np.arange(1, future_count + 1, dtype=float) * 10.0
    future_power_kw = np.interp(interval_end_minutes, minute_grid, power_grid)

    result = np.zeros(T, dtype=float)
    if issue_slot:
        result[:issue_slot] = dataset.pv_energy_kwh[day_idx, :issue_slot]
    result[issue_slot:] = np.maximum(future_power_kw, 0.0) * DT_HOURS
    return result
