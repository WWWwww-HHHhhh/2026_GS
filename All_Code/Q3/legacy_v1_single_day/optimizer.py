from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from config import ModelConfig


@dataclass
class WindowSolution:
    success: bool
    message: str
    q_kwh: np.ndarray
    charge_kwh: np.ndarray
    discharge_kwh: np.ndarray
    soc_kwh: np.ndarray
    planned_pv_kwh: np.ndarray
    planned_grid_kwh: np.ndarray
    emergency_kwh: np.ndarray
    curtailment_kwh: np.ndarray
    market_charge_cny: np.ndarray
    scenario_cost_cny: np.ndarray
    expected_cost_cny: float
    cvar_cost_cny: float
    terminal_deviation_kwh: float
    raw_objective: float


@dataclass(frozen=True)
class _Index:
    q: slice
    c: slice
    r: slice
    s: slice
    z: slice
    y: slice
    e: slice
    g: slice
    w: slice
    u: slice
    zeta: int
    xi_plus: int
    xi_minus: int
    n_vars: int
    h: int
    m: int

    @classmethod
    def build(cls, h: int, m: int) -> "_Index":
        cursor = 0

        def take(length: int) -> slice:
            nonlocal cursor
            result = slice(cursor, cursor + length)
            cursor += length
            return result

        q = take(h)
        c = take(h)
        r = take(h)
        s = take(h + 1)
        z = take(h)
        y = take(m * h)
        e = take(m * h)
        g = take(m * h)
        w = take(m * h)
        u = take(m)
        zeta = cursor
        cursor += 1
        xi_plus = cursor
        cursor += 1
        xi_minus = cursor
        cursor += 1
        return cls(q, c, r, s, z, y, e, g, w, u, zeta, xi_plus, xi_minus, cursor, h, m)

    def scenario_var(self, block: slice, scenario: int, t: int) -> int:
        return block.start + scenario * self.h + t


class _Rows:
    def __init__(self) -> None:
        self.row: list[int] = []
        self.col: list[int] = []
        self.value: list[float] = []
        self.rhs: list[float] = []

    def add(self, terms: list[tuple[int, float]], rhs: float) -> None:
        row_id = len(self.rhs)
        for column, coefficient in terms:
            if coefficient != 0.0:
                self.row.append(row_id)
                self.col.append(column)
                self.value.append(float(coefficient))
        self.rhs.append(float(rhs))

    def matrix(self, n_vars: int):
        return coo_matrix(
            (self.value, (self.row, self.col)),
            shape=(len(self.rhs), n_vars),
        ).tocsr(), np.asarray(self.rhs, dtype=float)


def piecewise_adjustment_charge(
    final_plan_kwh: np.ndarray,
    zero_hour_plan_kwh: np.ndarray,
    price_cny_per_kwh: np.ndarray,
) -> np.ndarray:
    """题目分段结算函数，按最终计划相对零点计划一次结算。"""
    q = np.asarray(final_plan_kwh, dtype=float)
    x0 = np.asarray(zero_hour_plan_kwh, dtype=float)
    price = np.asarray(price_cny_per_kwh, dtype=float)
    return np.where(
        q <= x0,
        0.5 * price * (q + x0),
        1.5 * price * q - 0.5 * price * x0,
    )


def empirical_cvar(costs: np.ndarray, alpha: float) -> float:
    costs = np.asarray(costs, dtype=float)
    if len(costs) == 0:
        return float("nan")
    zeta = float(np.quantile(costs, alpha, method="higher"))
    return zeta + float(np.maximum(costs - zeta, 0.0).mean()) / (1.0 - alpha)


def solve_window(
    load_scenarios_kwh: np.ndarray,
    pv_scenarios_kwh: np.ndarray,
    price_cny_per_kwh: np.ndarray,
    current_soc_kwh: float,
    config: ModelConfig,
    zero_hour_plan_kwh: np.ndarray | None = None,
    fixed_plan_kwh: np.ndarray | None = None,
    initial_plan: bool = False,
) -> WindowSolution:
    """求解一个剩余日窗口。

    initial_plan 为真时，q 是零点计划并按普通电价计费。
    其余官方更新使用相对 zero_hour_plan_kwh 的分段调整费。
    fixed_plan_kwh 非空时只滚动储能，不允许购电计划改变。
    """
    load = np.asarray(load_scenarios_kwh, dtype=float)
    pv = np.asarray(pv_scenarios_kwh, dtype=float)
    price = np.asarray(price_cny_per_kwh, dtype=float)
    if load.ndim != 2 or pv.shape != load.shape:
        raise ValueError("负荷与光伏场景必须是同形二维数组")
    m, h = load.shape
    if price.shape != (h,):
        raise ValueError("电价长度必须等于窗口长度")
    if (load < 0).any() or (pv < 0).any() or (price < 0).any():
        raise ValueError("场景和电价不允许为负")
    if not initial_plan:
        if zero_hour_plan_kwh is None:
            raise ValueError("调整阶段必须提供零点购电计划")
        x0 = np.asarray(zero_hour_plan_kwh, dtype=float)
        if x0.shape != (h,):
            raise ValueError("零点购电计划长度错误")
    else:
        x0 = np.zeros(h, dtype=float)
    if fixed_plan_kwh is not None:
        fixed_q = np.asarray(fixed_plan_kwh, dtype=float)
        if fixed_q.shape != (h,) or (fixed_q < 0).any():
            raise ValueError("固定购电计划长度错误或包含负数")
    else:
        fixed_q = None

    idx = _Index.build(h, m)
    objective = np.zeros(idx.n_vars, dtype=float)
    beta = config.cvar_weight
    if not 0.0 <= beta <= 1.0:
        raise ValueError("cvar_weight 必须位于 0 到 1")
    if not 0.0 < config.cvar_alpha < 1.0:
        raise ValueError("cvar_alpha 必须位于 0 到 1")

    market_block = idx.q if initial_plan else idx.z
    if initial_plan:
        objective[market_block] += (1.0 - beta) * price
    else:
        objective[market_block] += 1.0 - beta
    for scenario in range(m):
        e_start = idx.e.start + scenario * h
        objective[e_start : e_start + h] += (
            (1.0 - beta) * config.emergency_multiplier * price / m
        )
    if beta > 0.0:
        objective[idx.zeta] = beta
        objective[idx.u] = beta / ((1.0 - config.cvar_alpha) * m)
    objective[idx.xi_plus] = config.terminal_penalty_cny_per_kwh
    objective[idx.xi_minus] = config.terminal_penalty_cny_per_kwh
    objective[idx.c] += config.numerical_tie_breaker
    objective[idx.r] += config.numerical_tie_breaker

    equalities = _Rows()
    inequalities = _Rows()
    equalities.add([(idx.s.start, 1.0)], current_soc_kwh)
    for t in range(h):
        equalities.add(
            [
                (idx.s.start + t + 1, 1.0),
                (idx.s.start + t, -1.0),
                (idx.c.start + t, -config.eta_charge),
                (idx.r.start + t, 1.0 / config.eta_discharge),
            ],
            0.0,
        )
    equalities.add(
        [
            (idx.s.stop - 1, 1.0),
            (idx.xi_plus, -1.0),
            (idx.xi_minus, 1.0),
        ],
        config.terminal_target_kwh,
    )

    if initial_plan:
        for t in range(h):
            equalities.add([(idx.z.start + t, 1.0)], 0.0)
    else:
        for t in range(h):
            inequalities.add(
                [
                    (idx.q.start + t, 0.5 * price[t]),
                    (idx.z.start + t, -1.0),
                ],
                -0.5 * price[t] * x0[t],
            )
            inequalities.add(
                [
                    (idx.q.start + t, 1.5 * price[t]),
                    (idx.z.start + t, -1.0),
                ],
                0.5 * price[t] * x0[t],
            )

    for scenario in range(m):
        for t in range(h):
            y = idx.scenario_var(idx.y, scenario, t)
            e = idx.scenario_var(idx.e, scenario, t)
            g = idx.scenario_var(idx.g, scenario, t)
            w = idx.scenario_var(idx.w, scenario, t)
            equalities.add(
                [
                    (y, 1.0),
                    (e, 1.0),
                    (g, 1.0),
                    (idx.r.start + t, 1.0),
                    (idx.c.start + t, -1.0),
                ],
                load[scenario, t],
            )
            equalities.add([(g, 1.0), (w, 1.0)], pv[scenario, t])
            inequalities.add([(y, 1.0), (idx.q.start + t, -1.0)], 0.0)

    if beta > 0.0:
        for scenario in range(m):
            terms = [(idx.zeta, -1.0), (idx.u.start + scenario, -1.0)]
            for t in range(h):
                market_coefficient = price[t] if initial_plan else 1.0
                terms.append((market_block.start + t, market_coefficient))
                terms.append(
                    (
                        idx.scenario_var(idx.e, scenario, t),
                        config.emergency_multiplier * price[t],
                    )
                )
            inequalities.add(terms, 0.0)

    a_eq, b_eq = equalities.matrix(idx.n_vars)
    a_ub, b_ub = inequalities.matrix(idx.n_vars)

    bounds: list[tuple[float | None, float | None]] = [(0.0, None)] * idx.n_vars
    if fixed_q is not None:
        for t, value in enumerate(fixed_q):
            bounds[idx.q.start + t] = (float(value), float(value))
    for t in range(h):
        bounds[idx.c.start + t] = (0.0, config.storage_power_kwh)
        bounds[idx.r.start + t] = (0.0, config.storage_power_kwh)
    for t in range(h + 1):
        bounds[idx.s.start + t] = (config.storage_min_kwh, config.storage_max_kwh)
    if beta == 0.0:
        for scenario in range(m):
            bounds[idx.u.start + scenario] = (0.0, 0.0)
        bounds[idx.zeta] = (0.0, 0.0)

    result = linprog(
        objective,
        A_ub=a_ub,
        b_ub=b_ub,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
        options={"presolve": True},
    )
    if not result.success:
        raise RuntimeError(f"窗口 LP 求解失败，{result.message}")

    vector = result.x
    q = vector[idx.q]
    charge = vector[idx.c]
    discharge = vector[idx.r]
    soc = vector[idx.s]
    y = vector[idx.y].reshape(m, h)
    emergency = vector[idx.e].reshape(m, h)
    used_pv = vector[idx.g].reshape(m, h)
    curtailment = vector[idx.w].reshape(m, h)
    if initial_plan:
        market_charge = price * q
    else:
        market_charge = piecewise_adjustment_charge(q, x0, price)
    scenario_cost = market_charge.sum() + (
        config.emergency_multiplier * emergency * price[None, :]
    ).sum(axis=1)
    terminal_deviation = abs(soc[-1] - config.terminal_target_kwh)

    return WindowSolution(
        success=True,
        message=result.message,
        q_kwh=q,
        charge_kwh=charge,
        discharge_kwh=discharge,
        soc_kwh=soc,
        planned_pv_kwh=used_pv,
        planned_grid_kwh=y,
        emergency_kwh=emergency,
        curtailment_kwh=curtailment,
        market_charge_cny=market_charge,
        scenario_cost_cny=scenario_cost,
        expected_cost_cny=float(scenario_cost.mean()),
        cvar_cost_cny=empirical_cvar(scenario_cost, config.cvar_alpha),
        terminal_deviation_kwh=float(terminal_deviation),
        raw_objective=float(result.fun),
    )
