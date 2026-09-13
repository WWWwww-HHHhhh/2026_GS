from __future__ import annotations

import sys
from pathlib import Path


Q3_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DEPS = Q3_ROOT / ".deps"
MODEL_DIR = Q3_ROOT / "Model_Establishment+Solution"
for path in (LOCAL_DEPS, MODEL_DIR):
    if path.exists():
        sys.path.insert(0, str(path))

import numpy as np

from config import ModelConfig
from optimizer import piecewise_adjustment_charge, solve_window
from rolling import settle_interval


def run_tests() -> None:
    price = np.array([0.4, 0.4, 0.8, 0.8, 1.2, 1.2])
    load = np.array(
        [
            [600, 600, 650, 700, 800, 850],
            [620, 590, 670, 720, 820, 830],
            [580, 610, 640, 690, 780, 870],
        ],
        dtype=float,
    )
    pv = np.array(
        [
            [0, 100, 300, 250, 50, 0],
            [0, 80, 260, 280, 60, 0],
            [0, 120, 330, 220, 40, 0],
        ],
        dtype=float,
    )
    config = ModelConfig(
        storage_min_kwh=0.0,
        storage_max_kwh=3000.0,
        initial_soc_kwh=1500.0,
        terminal_target_kwh=1500.0,
        storage_power_kwh=500.0,
    )
    solution = solve_window(load, pv, price, 1500.0, config, initial_plan=True)
    assert solution.success
    assert np.max(np.abs(solution.soc_kwh[1:] - solution.soc_kwh[:-1] - 0.9 * solution.charge_kwh + solution.discharge_kwh / 0.9)) < 1.0e-7
    assert (solution.planned_grid_kwh <= solution.q_kwh[None, :] + 1.0e-7).all()

    risk_config = ModelConfig(
        storage_min_kwh=0.0,
        storage_max_kwh=3000.0,
        initial_soc_kwh=1500.0,
        terminal_target_kwh=1500.0,
        storage_power_kwh=500.0,
        cvar_weight=0.25,
    )
    risk_solution = solve_window(
        load, pv, price, 1500.0, risk_config, initial_plan=True
    )
    assert risk_solution.success
    assert risk_solution.cvar_cost_cny + 1.0e-7 >= risk_solution.expected_cost_cny

    charge = piecewise_adjustment_charge(
        np.array([5.0, 10.0, 15.0]),
        np.array([10.0, 10.0, 10.0]),
        np.ones(3),
    )
    assert np.allclose(charge, [7.5, 10.0, 17.5])

    actual = settle_interval(10.0, 20.0, 5.0, 0.0, 0.0, 1500.0, config)
    assert abs(actual["planned_grid_kwh"] - 10.0) < 1.0e-9
    assert abs(actual["emergency_kwh"] - 5.0) < 1.0e-9
    assert abs(
        actual["planned_grid_kwh"]
        + actual["emergency_kwh"]
        + actual["used_pv_kwh"]
        + actual["discharge_kwh"]
        - 20.0
        - actual["charge_kwh"]
    ) < 1.0e-9
    print("Q3 core tests passed")


if __name__ == "__main__":
    run_tests()
