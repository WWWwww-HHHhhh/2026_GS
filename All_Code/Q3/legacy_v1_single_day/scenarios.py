"""用历史整日联合残差块生成负荷和光伏场景。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from data import Q3Dataset
from forecast import causal_load_point, pv_point_from_official_forecast


@dataclass
class ScenarioBundle:
    load_kwh: np.ndarray
    pv_kwh: np.ndarray
    source_day_indices: np.ndarray


def build_joint_residual_scenarios(
    dataset: Q3Dataset,
    day_idx: int,
    issue_hour: int,
    load_point_kwh: np.ndarray,
    pv_point_kwh: np.ndarray,
    scenario_count: int,
    seed: int,
    history_days: int = 60,
) -> ScenarioBundle:
    """只从当前日期之前抽取同一发布时点的联合残差块。"""
    if scenario_count < 1:
        raise ValueError("scenario_count 必须为正整数")
    start_slot = issue_hour * 6
    pool = np.arange(max(1, day_idx - history_days), day_idx, dtype=int)
    horizon = 144 - start_slot

    if len(pool) == 0:
        load = np.repeat(load_point_kwh[None, start_slot:], scenario_count, axis=0)
        pv = np.repeat(pv_point_kwh[None, start_slot:], scenario_count, axis=0)
        return ScenarioBundle(load, pv, np.full(scenario_count, -1, dtype=int))

    load_residuals = []
    pv_residuals = []
    valid_days = []
    for hist_idx in pool:
        try:
            hist_load_point = causal_load_point(dataset, int(hist_idx), issue_hour)
            hist_pv_point = pv_point_from_official_forecast(
                dataset, int(hist_idx), issue_hour
            )
        except ValueError:
            continue
        load_residuals.append(
            dataset.load_energy_kwh[hist_idx, start_slot:] - hist_load_point[start_slot:]
        )
        pv_residuals.append(
            dataset.pv_energy_kwh[hist_idx, start_slot:] - hist_pv_point[start_slot:]
        )
        valid_days.append(hist_idx)

    if not valid_days:
        load = np.repeat(load_point_kwh[None, start_slot:], scenario_count, axis=0)
        pv = np.repeat(pv_point_kwh[None, start_slot:], scenario_count, axis=0)
        return ScenarioBundle(load, pv, np.full(scenario_count, -1, dtype=int))

    rng = np.random.default_rng(seed)
    draw = rng.integers(0, len(valid_days), size=scenario_count)
    load_residuals = np.asarray(load_residuals, dtype=float)
    pv_residuals = np.asarray(pv_residuals, dtype=float)
    point_load = load_point_kwh[start_slot:]
    point_pv = pv_point_kwh[start_slot:]
    load_scenarios = np.maximum(point_load[None, :] + load_residuals[draw], 0.0)
    pv_scenarios = np.maximum(point_pv[None, :] + pv_residuals[draw], 0.0)

    load_scenarios[0] = point_load
    pv_scenarios[0] = point_pv
    source_days = np.asarray(valid_days, dtype=int)[draw]
    source_days[0] = -1
    if load_scenarios.shape != (scenario_count, horizon):
        raise AssertionError("场景维度异常")
    return ScenarioBundle(load_scenarios, pv_scenarios, source_days)
