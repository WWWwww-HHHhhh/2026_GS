# -*- coding: utf-8 -*-
"""优化版 Q2 场景生成：净负荷残差整日块 bootstrap，季节分层加权。"""
import os, pickle
import numpy as np
from paths import Q2_DATA_PROCESSING

T = 144
D = 365
SEED = 20260101
RECENT_HALF_LIFE_DAYS = 60  # 近期权重，用于提高当前季节相似场景的覆盖率


class NetScenarioEngine:
    def __init__(self, N, Nhat, dates, seed=SEED):
        self.N = N
        self.Nhat = Nhat
        self.dates = list(dates)
        self.seed = seed

    def _weights(self, current_day, blocks):
        if not blocks:
            return np.ones(0)
        # 按“距离当前日”给近期更高权重，同时保留等概率抽样的稳定性
        dist = np.array([current_day - b["day"] for b in blocks], dtype=float)
        w = np.exp(-dist / RECENT_HALF_LIFE_DAYS)
        w = np.clip(w, 0.05, None)
        return w / np.sum(w)

    def generate_day(self, i, M, blocks):
        avail = [b for b in blocks if 1 <= b["day"] < i]
        if not avail:
            return np.tile(self.Nhat[:, i], (M, 1))
        rng = np.random.default_rng(self.seed * 1000 + i)
        w = self._weights(i, avail)
        idx = rng.choice(len(avail), size=M, replace=True, p=w)
        res = np.vstack([avail[j]["res"] for j in idx])
        scen = self.Nhat[:, i][None, :] + res
        return scen

    def generate_all(self, M):
        blocks = []
        N_all = np.zeros((D, M, T))
        for i in range(D):
            N_all[i] = self.generate_day(i, M, blocks)
            if i >= 1:
                blocks.append({"day": i, "res": self.N[:, i] - self.Nhat[:, i]})
        return N_all


def run_scenarios(M=20):
    with open(os.path.join(Q2_DATA_PROCESSING, "q2_dataset.pkl"), "rb") as fh:
        ds = pickle.load(fh)
    with open(os.path.join(Q2_DATA_PROCESSING, "net_forecasts.pkl"), "rb") as fh:
        fc = pickle.load(fh)
    eng = NetScenarioEngine(fc["N"], fc["Nhat"], fc["dates"])
    N_all = eng.generate_all(M)
    out = {"M": M, "N_all": N_all}
    with open(os.path.join(Q2_DATA_PROCESSING, f"net_scenarios_M{M}.pkl"), "wb") as fh:
        pickle.dump(out, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"[opt scenarios] net-load scenarios M={M} shape={N_all.shape}")
    return out

if __name__ == "__main__":
    import sys
    M = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    run_scenarios(M)
