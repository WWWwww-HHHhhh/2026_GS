# -*- coding: utf-8 -*-
"""Q2'' 经验场景生成：近期窗口联合残差自助抽样（因果，无未来信息）。"""
import os, pickle
import numpy as np

GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q2P = os.path.join(GS, "Q2''")
DATA_PROC = os.path.join(Q2P, "Data_processing")
T, D = 144, 365
SEED = 20260101

def build_scenarios(Lhat, Ghat, load, pv, window=30, M=20, seed=SEED):
    L_all = np.zeros((D, M, T)); G_all = np.zeros((D, M, T)); blocks = []
    for i in range(D):
        avail = [b for b in blocks if b[0] >= max(1, i - window)]
        if len(avail) == 0:
            L_scen = np.tile(np.clip(Lhat[:, i], 0, None), (M, 1))
            G_scen = np.tile(np.clip(Ghat[:, i], 0, None), (M, 1))
        else:
            rng = np.random.default_rng(seed * 1000 + i)
            idx = rng.integers(0, len(avail), size=M)
            L_res = np.vstack([avail[j][1] for j in idx])
            G_res = np.vstack([avail[j][2] for j in idx])
            L_scen = np.clip(Lhat[:, i][None, :] + L_res, 0, None)
            G_scen = np.clip(Ghat[:, i][None, :] + G_res, 0, None)
        L_all[i] = L_scen; G_all[i] = G_scen
        if i >= 1:
            blocks.append((i, load[:, i] - Lhat[:, i], pv[:, i] - Ghat[:, i]))
    return L_all, G_all

def run_scenarios(window=30, M=20):
    ds = pickle.load(open(os.path.join(DATA_PROC, "q2_dataset.pkl"), "rb"))
    fc = pickle.load(open(os.path.join(DATA_PROC, "forecasts.pkl"), "rb"))
    L_all, G_all = build_scenarios(fc["Lhat"], fc["Ghat"], ds["load"], ds["pv"], window=window, M=M)
    cache = {"window": window, "M": M, "L_all": L_all, "G_all": G_all}
    path = os.path.join(DATA_PROC, f"scenarios_w{window}_M{M}.pkl")
    with open(path, "wb") as f:
        pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"saved {path}: L={L_all.shape}, G={G_all.shape}")
    return cache

if __name__ == "__main__":
    import sys
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    m = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    run_scenarios(w, m)
