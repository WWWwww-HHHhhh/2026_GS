from __future__ import annotations

import numpy as np

from config import ModelConfig
from rolling import DaySimulation


def validate_day(simulation: DaySimulation, config: ModelConfig | None = None) -> dict[str, float | int | bool]:
    config = config or ModelConfig()
    data = simulation.intervals
    balance = (
        data["计划电实际提取_kWh"].to_numpy(dtype=float)
        + data["紧急购电_kWh"].to_numpy(dtype=float)
        + data["光伏消纳_kWh"].to_numpy(dtype=float)
        + data["执行放电_kWh"].to_numpy(dtype=float)
        - data["负荷实测_kWh"].to_numpy(dtype=float)
        - data["执行充电_kWh"].to_numpy(dtype=float)
    )
    soc_recursion = (
        data["区间末SOC_kWh"].to_numpy(dtype=float)
        - data["区间初SOC_kWh"].to_numpy(dtype=float)
        - config.eta_charge * data["执行充电_kWh"].to_numpy(dtype=float)
        + data["执行放电_kWh"].to_numpy(dtype=float) / config.eta_discharge
    )
    planned_grid_violation = np.maximum(
        data["计划电实际提取_kWh"].to_numpy(dtype=float)
        - data["最终计划_kWh"].to_numpy(dtype=float),
        0.0,
    )
    soc_values = np.concatenate(
        (
            data["区间初SOC_kWh"].to_numpy(dtype=float),
            data["区间末SOC_kWh"].tail(1).to_numpy(dtype=float),
        )
    )
    report = {
        "balance_max_abs_kwh": float(np.abs(balance).max()),
        "soc_recursion_max_abs_kwh": float(np.abs(soc_recursion).max()),
        "planned_grid_violation_max_kwh": float(planned_grid_violation.max()),
        "soc_lower_violation_max_kwh": float(
            np.maximum(config.storage_min_kwh - soc_values, 0.0).max()
        ),
        "soc_upper_violation_max_kwh": float(
            np.maximum(soc_values - config.storage_max_kwh, 0.0).max()
        ),
        "negative_value_count": int(
            (data.select_dtypes(include=["number"]).to_numpy() < -1.0e-8).sum()
        ),
    }
    report["passed"] = bool(
        report["balance_max_abs_kwh"] <= 1.0e-6
        and report["soc_recursion_max_abs_kwh"] <= 1.0e-6
        and report["planned_grid_violation_max_kwh"] <= 1.0e-6
        and report["soc_lower_violation_max_kwh"] <= 1.0e-6
        and report["soc_upper_violation_max_kwh"] <= 1.0e-6
    )
    return report
