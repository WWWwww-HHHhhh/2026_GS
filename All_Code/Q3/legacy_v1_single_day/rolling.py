from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from config import OFFICIAL_UPDATE_SLOTS, STRATEGY_UPDATES, T, ModelConfig
from data import Q3Dataset
from forecast import causal_load_point, pv_point_from_official_forecast
from optimizer import piecewise_adjustment_charge, solve_window
from scenarios import ScenarioBundle, build_joint_residual_scenarios


@dataclass
class DaySimulation:
    date: str
    strategy: str
    intervals: pd.DataFrame
    updates: pd.DataFrame
    summary: dict[str, float | int | str]


def _clock_label(slot: int) -> str:
    start_minutes = slot * 10
    end_minutes = (slot + 1) * 10

    def label(total: int) -> str:
        if total == 1440:
            return "24:00"
        return f"{total // 60:02d}:{total % 60:02d}"

    return f"({label(start_minutes)},{label(end_minutes)}]"


def _seed_for(date: pd.Timestamp, issue_hour: int, base_seed: int) -> int:
    return int((date.toordinal() * 101 + issue_hour * 1009 + base_seed) % (2**32 - 1))


def _forecast_scenarios(
    dataset: Q3Dataset,
    day_idx: int,
    issue_hour: int,
    scenario_count: int,
    base_seed: int,
) -> tuple[np.ndarray, np.ndarray, ScenarioBundle]:
    load_point = causal_load_point(dataset, day_idx, issue_hour)
    pv_point = pv_point_from_official_forecast(dataset, day_idx, issue_hour)
    bundle = build_joint_residual_scenarios(
        dataset=dataset,
        day_idx=day_idx,
        issue_hour=issue_hour,
        load_point_kwh=load_point,
        pv_point_kwh=pv_point,
        scenario_count=scenario_count,
        seed=_seed_for(dataset.dates[day_idx], issue_hour, base_seed),
    )
    return load_point, pv_point, bundle


def _remove_simultaneous_charge_discharge(
    charge_kwh: float,
    discharge_kwh: float,
    config: ModelConfig,
) -> tuple[float, float]:
    """保持计划 SOC 增量不变，消除数值退化造成的同时充放电。"""
    if charge_kwh <= 1.0e-8 or discharge_kwh <= 1.0e-8:
        return charge_kwh, discharge_kwh
    delta_soc = (
        config.eta_charge * charge_kwh
        - discharge_kwh / config.eta_discharge
    )
    if delta_soc >= 0.0:
        return delta_soc / config.eta_charge, 0.0
    return 0.0, -delta_soc * config.eta_discharge


def settle_interval(
    planned_purchase_kwh: float,
    actual_load_kwh: float,
    actual_pv_kwh: float,
    recommended_charge_kwh: float,
    recommended_discharge_kwh: float,
    current_soc_kwh: float,
    config: ModelConfig,
) -> dict[str, float]:
    """执行一个区间的物理调度并按 y 不大于 q 结算。

    安全裁剪只用于保证实测场景下的设备可行性，不进入目标函数，也不产生
    任何虚构费用。裁剪量会单独导出，便于检查场景覆盖是否不足。
    """
    c_rec, r_rec = _remove_simultaneous_charge_discharge(
        max(float(recommended_charge_kwh), 0.0),
        max(float(recommended_discharge_kwh), 0.0),
        config,
    )
    charge = min(
        c_rec,
        config.storage_power_kwh,
        max((config.storage_max_kwh - current_soc_kwh) / config.eta_charge, 0.0),
    )
    discharge = min(
        r_rec,
        config.storage_power_kwh,
        max((current_soc_kwh - config.storage_min_kwh) * config.eta_discharge, 0.0),
    )
    discharge = min(discharge, max(actual_load_kwh + charge, 0.0))

    residual_demand = max(actual_load_kwh + charge - discharge, 0.0)
    used_pv = min(actual_pv_kwh, residual_demand)
    planned_grid = min(planned_purchase_kwh, residual_demand - used_pv)
    emergency = max(residual_demand - used_pv - planned_grid, 0.0)
    curtailment = max(actual_pv_kwh - used_pv, 0.0)
    next_soc = (
        current_soc_kwh
        + config.eta_charge * charge
        - discharge / config.eta_discharge
    )
    return {
        "charge_kwh": float(charge),
        "discharge_kwh": float(discharge),
        "planned_grid_kwh": float(planned_grid),
        "emergency_kwh": float(emergency),
        "used_pv_kwh": float(used_pv),
        "curtailment_kwh": float(curtailment),
        "next_soc_kwh": float(next_soc),
        "charge_clip_kwh": float(max(c_rec - charge, 0.0)),
        "discharge_clip_kwh": float(max(r_rec - discharge, 0.0)),
    }


def simulate_day(
    dataset: Q3Dataset,
    date: str | pd.Timestamp,
    strategy: str = "Sall",
    scenario_count: int = 30,
    storage_reopt_every: int = 1,
    initial_soc_kwh: float | None = None,
    config: ModelConfig | None = None,
    seed: int = 2026,
) -> DaySimulation:
    """运行一天的购电更新与储能滚动闭环。"""
    if strategy not in STRATEGY_UPDATES:
        raise ValueError(f"未知策略 {strategy}，可选值为 {tuple(STRATEGY_UPDATES)}")
    if storage_reopt_every < 1:
        raise ValueError("storage_reopt_every 必须为正整数")
    config = config or ModelConfig()
    day_idx = dataset.day_index(date)
    date_value = dataset.dates[day_idx]
    price = dataset.price_cny_per_kwh
    actual_load = dataset.load_energy_kwh[day_idx]
    actual_pv = dataset.pv_energy_kwh[day_idx]
    soc = float(config.initial_soc_kwh if initial_soc_kwh is None else initial_soc_kwh)
    if not config.storage_min_kwh <= soc <= config.storage_max_kwh:
        raise ValueError("初始 SOC 超出容量范围")

    _, _, scenario_bundle = _forecast_scenarios(
        dataset, day_idx, 0, scenario_count, seed
    )
    initial_solution = solve_window(
        load_scenarios_kwh=scenario_bundle.load_kwh,
        pv_scenarios_kwh=scenario_bundle.pv_kwh,
        price_cny_per_kwh=price,
        current_soc_kwh=soc,
        config=config,
        initial_plan=True,
    )
    zero_plan = initial_solution.q_kwh.copy()
    active_plan = zero_plan.copy()
    recommended_charge = initial_solution.charge_kwh.copy()
    recommended_discharge = initial_solution.discharge_kwh.copy()
    scenario_start = 0
    current_bundle = scenario_bundle

    update_hours = set(STRATEGY_UPDATES[strategy])
    update_records: list[dict[str, float | int | str]] = [
        {
            "时点": 0,
            "是否调整购电计划": "零点初始计划",
            "剩余区间数": T,
            "计划改变量绝对值_kWh": 0.0,
            "预计均值成本_元": initial_solution.expected_cost_cny,
            "预计CVaR成本_元": initial_solution.cvar_cost_cny,
            "场景数": scenario_count,
        }
    ]
    interval_records: list[dict[str, float | int | str]] = []

    for t in range(T):
        solved_now = t == 0
        if t in OFFICIAL_UPDATE_SLOTS and t > 0:
            issue_hour = t // 6
            _, _, current_bundle = _forecast_scenarios(
                dataset, day_idx, issue_hour, scenario_count, seed
            )
            scenario_start = t
            allow_plan_update = issue_hour in update_hours
            old_plan = active_plan[t:].copy()
            official_solution = solve_window(
                load_scenarios_kwh=current_bundle.load_kwh,
                pv_scenarios_kwh=current_bundle.pv_kwh,
                price_cny_per_kwh=price[t:],
                current_soc_kwh=soc,
                config=config,
                zero_hour_plan_kwh=zero_plan[t:],
                fixed_plan_kwh=None if allow_plan_update else active_plan[t:],
                initial_plan=False,
            )
            if allow_plan_update:
                active_plan[t:] = official_solution.q_kwh
            recommended_charge[t:] = official_solution.charge_kwh
            recommended_discharge[t:] = official_solution.discharge_kwh
            update_records.append(
                {
                    "时点": issue_hour,
                    "是否调整购电计划": "是" if allow_plan_update else "否，仅更新储能策略",
                    "剩余区间数": T - t,
                    "计划改变量绝对值_kWh": float(
                        np.abs(active_plan[t:] - old_plan).sum()
                    ),
                    "预计均值成本_元": official_solution.expected_cost_cny,
                    "预计CVaR成本_元": official_solution.cvar_cost_cny,
                    "场景数": scenario_count,
                }
            )
            solved_now = True

        if not solved_now and t % storage_reopt_every == 0:
            offset = t - scenario_start
            rolling_solution = solve_window(
                load_scenarios_kwh=current_bundle.load_kwh[:, offset:],
                pv_scenarios_kwh=current_bundle.pv_kwh[:, offset:],
                price_cny_per_kwh=price[t:],
                current_soc_kwh=soc,
                config=config,
                zero_hour_plan_kwh=zero_plan[t:],
                fixed_plan_kwh=active_plan[t:],
                initial_plan=False,
            )
            recommended_charge[t:] = rolling_solution.charge_kwh
            recommended_discharge[t:] = rolling_solution.discharge_kwh

        soc_before = soc
        actual = settle_interval(
            planned_purchase_kwh=active_plan[t],
            actual_load_kwh=actual_load[t],
            actual_pv_kwh=actual_pv[t],
            recommended_charge_kwh=recommended_charge[t],
            recommended_discharge_kwh=recommended_discharge[t],
            current_soc_kwh=soc,
            config=config,
        )
        soc = actual["next_soc_kwh"]
        interval_records.append(
            {
                "日期": str(date_value.date()),
                "区间序号": t + 1,
                "真实区间": _clock_label(t),
                "电价_元每kWh": price[t],
                "负荷实测_kWh": actual_load[t],
                "光伏实测_kWh": actual_pv[t],
                "零点计划_kWh": zero_plan[t],
                "最终计划_kWh": active_plan[t],
                "建议充电_kWh": recommended_charge[t],
                "建议放电_kWh": recommended_discharge[t],
                "执行充电_kWh": actual["charge_kwh"],
                "执行放电_kWh": actual["discharge_kwh"],
                "计划电实际提取_kWh": actual["planned_grid_kwh"],
                "紧急购电_kWh": actual["emergency_kwh"],
                "光伏消纳_kWh": actual["used_pv_kwh"],
                "弃光_kWh": actual["curtailment_kwh"],
                "区间初SOC_kWh": soc_before,
                "区间末SOC_kWh": soc,
                "充电安全裁剪_kWh": actual["charge_clip_kwh"],
                "放电安全裁剪_kWh": actual["discharge_clip_kwh"],
            }
        )

    intervals = pd.DataFrame(interval_records)
    updates = pd.DataFrame(update_records)
    market_charge = piecewise_adjustment_charge(active_plan, zero_plan, price)
    emergency_charge = (
        config.emergency_multiplier
        * price
        * intervals["紧急购电_kWh"].to_numpy(dtype=float)
    )
    intervals["计划购电结算_元"] = market_charge
    intervals["紧急购电结算_元"] = emergency_charge
    intervals["总结算_元"] = market_charge + emergency_charge

    summary: dict[str, float | int | str] = {
        "日期": str(date_value.date()),
        "策略": strategy,
        "场景数": scenario_count,
        "储能重算步长_区间": storage_reopt_every,
        "零点计划总量_kWh": float(zero_plan.sum()),
        "最终计划总量_kWh": float(active_plan.sum()),
        "实际提取计划电量_kWh": float(intervals["计划电实际提取_kWh"].sum()),
        "紧急购电量_kWh": float(intervals["紧急购电_kWh"].sum()),
        "弃光量_kWh": float(intervals["弃光_kWh"].sum()),
        "计划购电结算_元": float(market_charge.sum()),
        "紧急购电结算_元": float(emergency_charge.sum()),
        "总费用_元": float((market_charge + emergency_charge).sum()),
        "日初SOC_kWh": float(intervals.iloc[0]["区间初SOC_kWh"]),
        "日末SOC_kWh": float(soc),
        "终端偏差_kWh": float(abs(soc - config.terminal_target_kwh)),
        "计划调整绝对量_kWh": float(updates["计划改变量绝对值_kWh"].sum()),
        "发生购电调整的时点数": int((updates["是否调整购电计划"] == "是").sum()),
        "充电安全裁剪_kWh": float(intervals["充电安全裁剪_kWh"].sum()),
        "放电安全裁剪_kWh": float(intervals["放电安全裁剪_kWh"].sum()),
        "口径": "最终计划相对零点计划一次结算",
    }
    return DaySimulation(
        date=str(date_value.date()),
        strategy=strategy,
        intervals=intervals,
        updates=updates,
        summary=summary,
    )
