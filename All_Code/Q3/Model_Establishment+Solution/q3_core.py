"""CUMCM 2026 C Q3, strictly causal rolling stochastic linear program.

All optimization quantities are 10-minute energy in kWh. This module reads
official attachments and frozen Q2_yy caches but never modifies them.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import pickle

import numpy as np
import pandas as pd
import pandas.core.internals.blocks as pandas_blocks
from pandas._libs.internals import BlockPlacement
from scipy.optimize import linprog
from scipy.sparse import coo_matrix


REPO = Path(os.environ.get("CUMCM_REPO_ROOT", r"D:\MathModel\2026_GS"))
Q2 = REPO / "All_Code" / "Q2_yy"
ATTACH = REPO / "Data" / "附件"
T = 144
ISSUES = (0, 36, 72, 108)
STRATEGIES = {
    "S0": (),
    "S6": (36,),
    "S12": (72,),
    "S18": (108,),
    "S6_12": (36, 72),
    "Sall": (36, 72, 108),
}
ETA_C = ETA_D = 0.9
SOC_MIN, SOC_MAX = 1200.0, 10800.0
CAP = 5000.0 / 6.0
ALPHA, BETA, KAPPA, EPS = 0.9, 0.2, 0.5316666666666666, 1e-4
M = 30
SEED = 20260101
TOL = 1e-5


def load_q2_pickle(path: Path):
    """Read Q2's older pandas pickle under pandas 3 without changing its data."""
    original = pandas_blocks.new_block

    def compatible_new_block(values, placement, **kwargs):
        if isinstance(placement, slice):
            placement = BlockPlacement(placement)
        return original(values, placement, **kwargs)

    pandas_blocks.new_block = compatible_new_block
    try:
        with path.open("rb") as fh:
            return pickle.load(fh)
    finally:
        pandas_blocks.new_block = original


@dataclass
class SourceData:
    dates: list[str]
    price: np.ndarray      # (T,D)
    load: np.ndarray       # (T,D)
    pv: np.ndarray         # (T,D)
    load_hat: np.ndarray   # (T,D)
    pv_hourly: dict[tuple[int, int], np.ndarray]

    @classmethod
    def load_verified(cls) -> "SourceData":
        ds = load_q2_pickle(Q2 / "Data_processing" / "q2_dataset.pkl")
        fc = load_q2_pickle(Q2 / "Data_processing" / "forecasts.pkl")
        raw = pd.read_excel(ATTACH / "附件3.xlsx", sheet_name=0)
        raw.iloc[:, 0] = raw.iloc[:, 0].replace("", np.nan).ffill()
        raw_dates = pd.to_datetime(raw.iloc[:, 0]).dt.strftime("%Y-%m-%d")
        raw_issues = raw.iloc[:, 1].astype(str).str.split(":").str[0].astype(int)
        raw_values = raw.iloc[:, 2:26].to_numpy(dtype=float)
        date_strings = [str(x) for x in ds["date_str"]]
        date_index = {day: i for i, day in enumerate(date_strings)}
        hourly = {}
        for row, (day, hour) in enumerate(zip(raw_dates, raw_issues)):
            key = (date_index[day], hour * 6)
            if key in hourly:
                raise ValueError(f"duplicate PV forecast {key}")
            hourly[key] = raw_values[row]
        if len(hourly) != 365 * 4:
            raise ValueError(f"incomplete attachment 3: {len(hourly)} rows")
        price = np.asarray(ds["price"], dtype=float)
        load = np.asarray(ds["load"], dtype=float)
        pv = np.asarray(ds["pv"], dtype=float)
        load_hat = np.asarray(fc["Lhat"], dtype=float)
        for name, arr in (("price", price), ("load", load), ("pv", pv), ("load_hat", load_hat)):
            if arr.shape != (T, 365) or not np.isfinite(arr).all():
                raise ValueError(f"invalid {name}: {arr.shape}")
        if (price <= 0).any() or (load < 0).any() or (pv < 0).any() or (load_hat < 0).any():
            raise ValueError("negative or zero values in official/Q2 input")
        if not np.isfinite(raw_values).all() or (raw_values < 0).any():
            raise ValueError("invalid attachment 3 forecast")
        return cls(date_strings, price, load, pv, load_hat, hourly)


class PVForecast:
    def __init__(self, data: SourceData, method: str = "linear_endpoint") -> None:
        if method not in ("linear_endpoint", "step"):
            raise ValueError(method)
        self.data = data
        self.method = method

    @lru_cache(maxsize=None)
    def get(self, day: int, issue: int) -> np.ndarray:
        """Forecast only for slots after issue. Known issue-time PV is the anchor."""
        hourly = self.data.pv_hourly[(day, issue)].astype(float)
        h = T - issue
        if self.method == "step":
            kw = np.repeat(hourly, 6)[:h]
        else:
            anchor_kw = 0.0 if issue == 0 else 6.0 * self.data.pv[issue - 1, day]
            nodes = np.concatenate(([anchor_kw], hourly))
            kw = np.interp(np.arange(1, h + 1) * 10.0, np.arange(25) * 60.0, nodes)
        return np.maximum(kw, 0.0) / 6.0


@dataclass
class ScenarioBundle:
    load: np.ndarray
    pv: np.ndarray
    sources: np.ndarray
    clipped_load: int
    clipped_pv: int


def scenarios(data: SourceData, pv_forecast: PVForecast, day: int, issue: int) -> ScenarioBundle:
    """Same historical day is drawn for load and issue-specific PV residuals."""
    if day < 31:
        raise ValueError("formal Q3 backtest starts 2025-02-01")
    pool = np.arange(max(1, day - 30), day, dtype=int)
    if len(pool) == 0 or np.max(pool) >= day:
        raise ValueError("historical residual availability violated")
    issue_number = ISSUES.index(issue)
    draw = np.random.default_rng(SEED * 1000 + day * 4 + issue_number).choice(pool, M, replace=True)
    current_l = data.load_hat[issue:, day]
    current_g = pv_forecast.get(day, issue)
    residual_l = np.stack([data.load[issue:, j] - data.load_hat[issue:, j] for j in draw])
    residual_g = np.stack([data.pv[issue:, j] - pv_forecast.get(int(j), issue) for j in draw])
    raw_l = current_l[None, :] + residual_l
    raw_g = current_g[None, :] + residual_g
    return ScenarioBundle(
        np.maximum(raw_l, 0.0), np.maximum(raw_g, 0.0), draw,
        int(np.sum(raw_l < 0.0)), int(np.sum(raw_g < 0.0)),
    )


class Rows:
    def __init__(self) -> None:
        self.ri: list[int] = []
        self.ci: list[int] = []
        self.val: list[float] = []
        self.rhs: list[float] = []

    def add(self, terms, rhs: float) -> None:
        row = len(self.rhs)
        for col, value in terms:
            if value:
                self.ri.append(row)
                self.ci.append(col)
                self.val.append(float(value))
        self.rhs.append(float(rhs))

    def matrix(self, n: int):
        return coo_matrix((self.val, (self.ri, self.ci)), shape=(len(self.rhs), n)).tocsr(), np.asarray(self.rhs)


@dataclass
class Solution:
    q: np.ndarray
    c: np.ndarray
    r: np.ndarray
    s: np.ndarray
    expected_cost: float
    cvar_cost: float
    objective: float
    eq_residual: float
    ub_violation: float
    both_count: int


def market_cost(price: np.ndarray, zero_plan: np.ndarray, final_plan: np.ndarray) -> np.ndarray:
    return np.maximum(0.5 * price * (zero_plan + final_plan),
                      1.5 * price * final_plan - 0.5 * price * zero_plan)


def market_cost_alternative(price: np.ndarray, zero_plan: np.ndarray, final_plan: np.ndarray) -> np.ndarray:
    """Sensitivity only: planned fee remains fully paid plus cancellation penalty."""
    return price * zero_plan + 0.5 * price * np.maximum(zero_plan - final_plan, 0.0) + 1.5 * price * np.maximum(final_plan - zero_plan, 0.0)


def solve_window(price: np.ndarray, bundle: ScenarioBundle, soc0: float, terminal_target: float,
                 zero_plan: np.ndarray | None = None, hard_terminal: bool = False) -> Solution:
    """One nonanticipative stochastic LP over the remaining natural-day slots."""
    l, g = bundle.load, bundle.pv
    m, h = l.shape
    price = np.asarray(price, dtype=float)
    if m != M or g.shape != (m, h) or price.shape != (h,):
        raise ValueError("window array shape mismatch")
    if zero_plan is not None and np.asarray(zero_plan).shape != (h,):
        raise ValueError("zero-hour plan shape mismatch")
    initial = zero_plan is None
    # First stage: q,c,r,s,f,xi+,xi-,zeta. Recourse per scenario: y,e,g,w,v,z.
    q0 = 0
    c0 = h
    r0 = 2 * h
    s0 = 3 * h
    f0 = s0 + h + 1
    xi_p, xi_m, zeta = f0 + h, f0 + h + 1, f0 + h + 2
    base = zeta + 1
    block = 5 * h + 1
    n = base + m * block

    def scen(j: int, kind: str, t: int = 0) -> int:
        offset = {"y": 0, "e": h, "g": 2 * h, "w": 3 * h, "v": 4 * h, "z": 5 * h}[kind]
        return base + j * block + offset + (0 if kind == "z" else t)

    obj = np.zeros(n)
    obj[f0:f0+h] = 1.0 - BETA
    obj[c0:c0+h] = EPS
    obj[r0:r0+h] = EPS
    obj[xi_p] = KAPPA
    obj[xi_m] = KAPPA
    obj[zeta] = BETA
    for j in range(m):
        obj[scen(j, "e"):scen(j, "e")+h] = (1.0 - BETA) * 5.0 * price / m
        obj[scen(j, "z")] = BETA / ((1.0 - ALPHA) * m)

    eq, ub = Rows(), Rows()
    eq.add([(s0, 1.0)], soc0)
    for t in range(h):
        eq.add([(s0+t+1, 1), (s0+t, -1), (c0+t, -ETA_C), (r0+t, 1/ETA_D)], 0)
    eq.add([(s0+h, 1), (xi_p, -1), (xi_m, 1)], terminal_target)
    for t in range(h):
        if initial:
            eq.add([(f0+t, 1), (q0+t, -price[t])], 0)
        else:
            x = float(zero_plan[t])
            ub.add([(q0+t, 0.5*price[t]), (f0+t, -1)], -0.5*price[t]*x)
            ub.add([(q0+t, 1.5*price[t]), (f0+t, -1)], 0.5*price[t]*x)
    for j in range(m):
        for t in range(h):
            eq.add([(scen(j, "y", t), 1), (scen(j, "e", t), 1),
                    (scen(j, "g", t), 1), (r0+t, 1), (c0+t, -1),
                    (scen(j, "v", t), -1)], l[j, t])
            eq.add([(scen(j, "g", t), 1), (scen(j, "w", t), 1)], g[j, t])
            ub.add([(scen(j, "y", t), 1), (q0+t, -1)], 0)
        risk_terms = [(zeta, -1), (scen(j, "z"), -1)]
        risk_terms += [(f0+t, 1) for t in range(h)]
        risk_terms += [(scen(j, "e", t), 5*price[t]) for t in range(h)]
        ub.add(risk_terms, 0)

    aeq, beq = eq.matrix(n)
    aub, bub = ub.matrix(n)
    bounds = [(0.0, None)] * n
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
            bounds[scen(j, "g", t)] = (0.0, float(g[j, t]))

    result = linprog(obj, A_ub=aub, b_ub=bub, A_eq=aeq, b_eq=beq,
                     bounds=bounds, method="highs")
    if not result.success:
        raise RuntimeError(f"Q3 LP failed: {result.status} {result.message}")
    vec = result.x
    eq_resid = float(np.max(np.abs(aeq @ vec - beq)))
    ub_viol = float(np.max(np.maximum(aub @ vec - bub, 0.0)))
    if not np.isfinite(vec).all() or eq_resid > TOL or ub_viol > TOL:
        raise RuntimeError(f"Q3 LP residuals invalid: eq={eq_resid} ub={ub_viol}")
    market = vec[f0:f0+h].sum()
    costs = np.array([market + 5 * np.dot(price, vec[scen(j, "e"):scen(j, "e")+h]) for j in range(m)])
    cvar = float(vec[zeta] + np.sum([vec[scen(j, "z")] for j in range(m)]) / ((1-ALPHA)*m))
    c = vec[c0:c0+h].copy()
    r = vec[r0:r0+h].copy()
    return Solution(vec[q0:q0+h].copy(), c, r, vec[s0:s0+h+1].copy(),
                    float(np.mean(costs)), cvar, float(result.fun), eq_resid,
                    ub_viol, int(np.sum((c > TOL) & (r > TOL))))


def execute_slot(q: float, c: float, r: float, soc: float, load: float, pv: float) -> dict[str, float]:
    """Exactly execute planned storage, then settle current realized slot PV first."""
    if not (-TOL <= c <= CAP + TOL and -TOL <= r <= CAP + TOL and q >= -TOL):
        raise ValueError(f"planned slot outside bounds: q={q} c={c} r={r} cap={CAP}")
    demand = load + c - r
    spill = max(0.0, -demand)
    served = max(0.0, demand)
    used_pv = min(pv, served)
    used_plan = min(q, max(0.0, served - used_pv))
    emergency = max(0.0, served - used_pv - used_plan)
    curtail = max(0.0, pv - used_pv)
    next_soc = soc + ETA_C*c - r/ETA_D
    if next_soc < SOC_MIN - TOL or next_soc > SOC_MAX + TOL:
        raise RuntimeError(f"SOC violated: {soc} -> {next_soc}")
    balance = used_plan + emergency + used_pv + r - load - c - spill
    if abs(balance) > TOL:
        raise RuntimeError(f"actual balance violated: {balance}")
    return {"y": used_plan, "e": emergency, "g": used_pv,
            "w": curtail, "v": spill, "soc_next": next_soc,
            "balance_residual": balance}
