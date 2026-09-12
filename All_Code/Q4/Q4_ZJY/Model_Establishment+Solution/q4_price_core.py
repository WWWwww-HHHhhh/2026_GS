"""Q4-3 causal price scenarios and stochastic receding-horizon LP.

The price observed after an issue time is used only for realized settlement.
Optimization sees a zero-hour price forecast plus residual blocks from days
strictly before the target day. Load and PV use the existing Q3 issue-specific
scenario generator, and all three residuals share its sampled source days.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from q3_core import (
    ALPHA, BETA, CAP, EPS, ETA_C, ETA_D, KAPPA, M, SOC_MAX, SOC_MIN,
    TOL, PVForecast, Rows, ScenarioBundle, Solution, SourceData, scenarios,
)

PRICE_FLOOR = 1e-6  # A fixed numerical positivity guard, not a future-data statistic.


@dataclass
class JointBundle:
    load: np.ndarray
    pv: np.ndarray
    price: np.ndarray
    sources: np.ndarray
    clipped_load: int
    clipped_pv: int
    clipped_price: int


def prices_for_sources(actual_price: np.ndarray, forecast_price: np.ndarray,
                       sources: np.ndarray, day: int, issue: int) -> np.ndarray:
    """Build future-price paths without reading the target day's actual prices."""
    actual_price = np.asarray(actual_price, dtype=float)
    forecast_price = np.asarray(forecast_price, dtype=float)
    sources = np.asarray(sources, dtype=int)
    if actual_price.shape != forecast_price.shape or actual_price.shape[0] != 144:
        raise ValueError("price matrices must share shape (144, number_of_days)")
    if not 0 <= issue < 144 or not 0 <= day < actual_price.shape[1]:
        raise ValueError("invalid day or issue")
    if sources.shape != (M,) or np.any(sources < 0) or np.any(sources >= day):
        raise ValueError("price scenario source is not strictly historical")
    center = forecast_price[issue:, day]
    residual = (actual_price[issue:, sources] - forecast_price[issue:, sources]).T
    return np.maximum(center[None, :] + residual, PRICE_FLOOR)


def joint_scenarios(data: SourceData, pv_forecast: PVForecast,
                    price_hat: np.ndarray, day: int, issue: int) -> JointBundle:
    base: ScenarioBundle = scenarios(data, pv_forecast, day, issue)
    raw = price_hat[issue:, day][None, :] + (
        data.price[issue:, base.sources] - price_hat[issue:, base.sources]
    ).T
    price = prices_for_sources(data.price, price_hat, base.sources, day, issue)
    return JointBundle(base.load, base.pv, price, base.sources,
                       base.clipped_load, base.clipped_pv,
                       int(np.sum(raw < PRICE_FLOOR)))


def solve_window(bundle: JointBundle, soc0: float, terminal_target: float,
                 zero_plan: np.ndarray | None = None, hard_terminal: bool = False,
                 settlement: str = "net") -> Solution:
    """One nonanticipative LP with scenario-dependent price and CVaR cost.

    The common ``tariff_energy`` variable is measured in kWh equivalents.
    Scenario m pays price[m,t] * tariff_energy[t], so one shared convex
    piecewise settlement model suffices for every positive price scenario.
    """
    if settlement not in ("net", "gross"):
        raise ValueError(settlement)
    load, pv, price = bundle.load, bundle.pv, bundle.price
    m, h = load.shape
    if m != M or pv.shape != (m, h) or price.shape != (m, h):
        raise ValueError("joint scenario shapes do not match")
    if not np.isfinite(price).all() or np.any(price <= 0):
        raise ValueError("scenario prices must be finite and positive")
    if zero_plan is not None and np.asarray(zero_plan).shape != (h,):
        raise ValueError("zero-hour plan shape mismatch")
    initial = zero_plan is None

    q0, c0, r0, s0 = 0, h, 2*h, 3*h
    f0 = s0 + h + 1
    xi_p, xi_m, zeta = f0+h, f0+h+1, f0+h+2
    if settlement == "gross":
        dm0, dp0 = zeta+1, zeta+1+h
        base = dp0+h
    else:
        base = zeta+1
    block = 5*h+1
    n = base+m*block

    def scen(j: int, kind: str, t: int = 0) -> int:
        offset = {"y": 0, "e": h, "g": 2*h, "w": 3*h, "v": 4*h, "z": 5*h}[kind]
        return base+j*block+offset+(0 if kind == "z" else t)

    obj = np.zeros(n)
    obj[f0:f0+h] = (1-BETA)*price.mean(axis=0)
    obj[c0:c0+h] = EPS
    obj[r0:r0+h] = EPS
    obj[xi_p] = KAPPA
    obj[xi_m] = KAPPA
    obj[zeta] = BETA
    for j in range(m):
        obj[scen(j, "e"):scen(j, "e")+h] = (1-BETA)*5*price[j]/m
        obj[scen(j, "z")] = BETA/((1-ALPHA)*m)

    eq, ub = Rows(), Rows()
    eq.add([(s0, 1)], soc0)
    for t in range(h):
        eq.add([(s0+t+1, 1), (s0+t, -1), (c0+t, -ETA_C), (r0+t, 1/ETA_D)], 0)
    eq.add([(s0+h, 1), (xi_p, -1), (xi_m, 1)], terminal_target)
    for t in range(h):
        if initial:
            eq.add([(f0+t, 1), (q0+t, -1)], 0)
        elif settlement == "gross":
            x = float(zero_plan[t])
            eq.add([(q0+t, 1), (dp0+t, -1), (dm0+t, 1)], x)
            eq.add([(f0+t, 1), (dm0+t, -0.5), (dp0+t, -1.5)], x)
        else:
            x = float(zero_plan[t])
            ub.add([(q0+t, 0.5), (f0+t, -1)], -0.5*x)
            ub.add([(q0+t, 1.5), (f0+t, -1)], 0.5*x)
    for j in range(m):
        for t in range(h):
            eq.add([(scen(j, "y", t), 1), (scen(j, "e", t), 1),
                    (scen(j, "g", t), 1), (r0+t, 1), (c0+t, -1),
                    (scen(j, "v", t), -1)], load[j, t])
            eq.add([(scen(j, "g", t), 1), (scen(j, "w", t), 1)], pv[j, t])
            ub.add([(scen(j, "y", t), 1), (q0+t, -1)], 0)
        risk = [(zeta, -1), (scen(j, "z"), -1)]
        risk += [(f0+t, price[j, t]) for t in range(h)]
        risk += [(scen(j, "e", t), 5*price[j, t]) for t in range(h)]
        ub.add(risk, 0)

    aeq, beq = eq.matrix(n)
    aub, bub = ub.matrix(n)
    bounds = [(0.0, None)]*n
    for t in range(h):
        bounds[c0+t] = (0.0, CAP)
        bounds[r0+t] = (0.0, CAP)
    for t in range(h+1):
        bounds[s0+t] = (SOC_MIN, SOC_MAX)
    bounds[s0] = (soc0, soc0)
    bounds[zeta] = (None, None)
    if hard_terminal:
        bounds[s0+h] = (terminal_target, terminal_target)
        bounds[xi_p] = (0.0, 0.0)
        bounds[xi_m] = (0.0, 0.0)
    for j in range(m):
        for t in range(h):
            bounds[scen(j, "g", t)] = (0.0, float(pv[j, t]))

    result = linprog(obj, A_ub=aub, b_ub=bub, A_eq=aeq, b_eq=beq,
                     bounds=bounds, method="highs")
    if not result.success:
        raise RuntimeError(f"Q4-3 LP failed: {result.status} {result.message}")
    vec = result.x
    eq_resid = float(np.max(np.abs(aeq @ vec-beq)))
    ub_viol = float(np.max(np.maximum(aub @ vec-bub, 0)))
    if not np.isfinite(vec).all() or eq_resid > TOL or ub_viol > TOL:
        raise RuntimeError(f"Q4-3 LP residuals invalid: eq={eq_resid} ub={ub_viol}")
    tariff_energy = vec[f0:f0+h]
    costs = np.array([
        float(np.dot(price[j], tariff_energy)
              + 5*np.dot(price[j], vec[scen(j, "e"):scen(j, "e")+h]))
        for j in range(m)
    ])
    cvar = float(vec[zeta] + sum(vec[scen(j, "z")] for j in range(m))/((1-ALPHA)*m))
    c = vec[c0:c0+h].copy()
    r = vec[r0:r0+h].copy()
    return Solution(vec[q0:q0+h].copy(), c, r, vec[s0:s0+h+1].copy(),
                    float(np.mean(costs)), cvar, float(result.fun), eq_resid,
                    ub_viol, int(np.sum((c > TOL) & (r > TOL))))
