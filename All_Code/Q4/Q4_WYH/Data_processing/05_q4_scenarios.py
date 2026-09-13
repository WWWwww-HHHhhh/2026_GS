from __future__ import annotations

import argparse
import pickle
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q4_common import D, HISTORY_WINDOW, OUT_DATA, SEED, T, TABLES, load_dataset, load_pickle_compat  # noqa: E402

PRICE_FLOOR = 0.0076
DEMO_DATE = "2025-07-15"


def build(M: int, pv_source: str) -> dict:
    ds = load_dataset()
    load = np.asarray(ds["load"], dtype=float)      # (T,D) kWh
    pv = np.asarray(ds["pv"], dtype=float)
    price = np.asarray(ds["price"], dtype=float)    # (T,D) 元/kWh
    Lhat = np.asarray(ds["Lhat"], dtype=float)
    Ghat = np.asarray(ds["Ghat"], dtype=float)
    Ghat_off = np.asarray(ds["Ghat_official"], dtype=float)
    dates = list(ds["dates"])

    pf = load_pickle_compat(OUT_DATA / "price_forecast.pkl")
    Phat = np.asarray(pf["price_hat"], dtype=float)
    if Phat.shape != (T, D):
        raise ValueError(f"price_hat 形状异常 {Phat.shape}")

    G_center = Ghat if pv_source == "q2" else Ghat_off
    if G_center.shape != (T, D):
        raise ValueError(f"光伏预测中心形状异常 {G_center.shape}")

    # 残差块库（同日三维联合）
    res_l = load - Lhat
    res_g = pv - G_center
    res_p = price - Phat

    rng_seed = SEED
    L_all = np.zeros((D, M, T))
    G_all = np.zeros((D, M, T))
    P_all = np.zeros((D, M, T))
    rows = []
    trunc_l = trunc_g = trunc_p = 0
    avail_counts = []

    for i in range(D):
        lo = max(1, i - HISTORY_WINDOW)
        pool = np.arange(lo, i, dtype=int)
        avail_counts.append(int(pool.size))
        if pool.size == 0:
            # 冷启动（1 月 1 日）：场景退化为点预测，并明确记录
            L_all[i] = np.tile(Lhat[:, i], (M, 1))
            G_all[i] = np.tile(G_center[:, i], (M, 1))
            P_all[i] = np.tile(Phat[:, i], (M, 1))
            rows.append({"date": dates[i].strftime("%Y-%m-%d"), "i": i, "n_pool": 0,
                         "max_block_day": -1, "trunc_load": 0, "trunc_pv": 0, "trunc_price": 0,
                         "mean_abs_dev_load": 0.0, "mean_abs_dev_pv": 0.0, "mean_abs_dev_price": 0.0,
                         "cold_start": 1})
            continue

        rng = np.random.default_rng(rng_seed * 1000 + i)
        idx = rng.integers(0, pool.size, size=M)
        draw = pool[idx]

        Ls = Lhat[:, i][None, :] + np.vstack([res_l[:, j] for j in draw])
        Gs = G_center[:, i][None, :] + np.vstack([res_g[:, j] for j in draw])
        Ps = Phat[:, i][None, :] + np.vstack([res_p[:, j] for j in draw])

        tl = int(np.sum(Ls < 0)); tg = int(np.sum(Gs < 0)); tp = int(np.sum(Ps < PRICE_FLOOR))
        Ls = np.clip(Ls, 0.0, None)
        Gs = np.clip(Gs, 0.0, None)
        Ps = np.clip(Ps, PRICE_FLOOR, None)
        trunc_l += tl; trunc_g += tg; trunc_p += tp

        L_all[i], G_all[i], P_all[i] = Ls, Gs, Ps
        rows.append({
            "date": dates[i].strftime("%Y-%m-%d"), "i": i, "n_pool": int(pool.size),
            "max_block_day": int(draw.max()), "trunc_load": tl, "trunc_pv": tg, "trunc_price": tp,
            "mean_abs_dev_load": float(np.mean(np.abs(Ls.mean(0) - Lhat[:, i]))),
            "mean_abs_dev_pv": float(np.mean(np.abs(Gs.mean(0) - G_center[:, i]))),
            "mean_abs_dev_price": float(np.mean(np.abs(Ps.mean(0) - Phat[:, i]))),
            "cold_start": 0,
        })

    diag = pd.DataFrame(rows)

    # ---------------- 核验 ----------------
    assert L_all.shape == G_all.shape == P_all.shape == (D, M, T)
    assert np.isfinite(L_all).all() and np.isfinite(G_all).all() and np.isfinite(P_all).all()
    assert (L_all >= 0).all() and (G_all >= 0).all(), "负荷/光伏场景出现负值"
    assert (P_all > 0).all(), "价格场景出现非正值"
    reg = diag[diag["cold_start"] == 0]
    assert (reg["max_block_day"].to_numpy() < reg["i"].to_numpy()).all(), "残差块因果性违规"
    assert (reg["n_pool"] <= HISTORY_WINDOW).all(), "回看窗口越界"
    assert (reg["n_pool"] > 0).all(), "存在空残差池（非冷启动）"

    # 联合结构检查：残差跨变量相关应与历史一致（抽同一个历史日的结果）
    hist_corr_gp = float(np.corrcoef(res_g.ravel(), res_p.ravel())[0, 1])
    sc_corr_gp = float(np.corrcoef((G_all - G_center.T[:, None, :]).ravel(),
                                   (P_all - Phat.T[:, None, :]).ravel())[0, 1])
    hist_corr_lp = float(np.corrcoef(res_l.ravel(), res_p.ravel())[0, 1])
    sc_corr_lp = float(np.corrcoef((L_all - Lhat.T[:, None, :]).ravel(),
                                   (P_all - Phat.T[:, None, :]).ravel())[0, 1])

    # ---------------- 落盘 ----------------
    cache = {
        "M": M, "L_all": L_all, "G_all": G_all, "P_all": P_all,
        "seed": rng_seed, "history_window_days": HISTORY_WINDOW, "pv_source": pv_source,
        "centers": {"Lhat": Lhat, "Ghat": G_center, "Phat": Phat},
        "sampling_rule": "joint_daily_residual_blocks_3d_strictly_before_decision_day",
    }
    with open(OUT_DATA / f"scenarios_M{M}.pkl", "wb") as fh:
        pickle.dump(cache, fh, protocol=pickle.HIGHEST_PROTOCOL)
    diag.to_csv(TABLES / "q4_scenario_diagnostics.csv", index=False, encoding="utf-8-sig")

    # 代表日长表
    dstr = [d.strftime("%Y-%m-%d") for d in dates]
    di = dstr.index(DEMO_DATE)
    demo = []
    for m in range(M):
        for t in range(T):
            demo.append([DEMO_DATE, m + 1, t + 1, L_all[di, m, t], G_all[di, m, t], P_all[di, m, t]])
    pd.DataFrame(demo, columns=["date", "scenario", "interval",
                                "L_scen_kwh", "G_scen_kwh", "P_scen_yuan_per_kwh"]
                 ).to_csv(OUT_DATA / f"scenario_demo_M{M}.csv", index=False, encoding="utf-8-sig")

    with open(TABLES / "q4_scenario_report.md", "w", encoding="utf-8") as fh:
        fh.write(f"# 问题 4-2 价格—负荷—光伏联合场景报告（M={M}，pv_source={pv_source}）\n\n")
        fh.write("- 脚本：`Data_processing/05_q4_scenarios.py`\n")
        fh.write(f"- 规则：决策日 i 只抽严格早于 i 的最近 {HISTORY_WINDOW} 个已结束日；"
                 f"三维残差块**同一历史日**抽取（有放回）；种子 {SEED}*1000+i\n")
        fh.write(f"- 形状：L_all/G_all/P_all = ({D}, {M}, {T})\n\n")
        fh.write("## 截断与因果\n\n")
        fh.write(f"- 负荷截断：{trunc_l}；光伏截断：{trunc_g}；价格截断（<{PRICE_FLOOR}）：{trunc_p}"
                 f"（总样本 {D * M * T}）\n")
        fh.write(f"- 冷启动天数（残差库为空，退化为点预测）：{int(diag['cold_start'].sum())}\n")
        fh.write(f"- 因果核验：所有非冷启动日的 max block day < 决策日 → PASS\n")
        fh.write(f"- 回看天数取值范围：[{int(reg['n_pool'].min())}, {int(reg['n_pool'].max())}]，"
                 f"上限 {HISTORY_WINDOW} → PASS\n\n")
        fh.write("## 联合结构保持（残差相关系数）\n\n")
        fh.write("| 变量对 | 历史残差相关 | 场景残差相关 |\n| --- | --- | --- |\n")
        fh.write(f"| 光伏 × 价格 | {hist_corr_gp:.5f} | {sc_corr_gp:.5f} |\n")
        fh.write(f"| 负荷 × 价格 | {hist_corr_lp:.5f} | {sc_corr_lp:.5f} |\n\n")
        fh.write("说明：两者由同一批历史残差块抽样得到，理论上应同阶；"
                 "抽样带放回会带来小幅偏离，量级一致即说明未破坏相依结构。\n\n")
        fh.write("## 代表性诊断（前 5 行）\n\n")
        fh.write(diag.head(5).to_string(index=False) + "\n")

    print(f"[05] M={M}，pv_source={pv_source}")
    print(f"     场景矩阵 {L_all.shape}（天 × 场景 × 时段）")
    print(f"     截断：负荷 {trunc_l}，光伏 {trunc_g}，价格 {trunc_p} / 总 {D * M * T}")
    print(f"     联合相关：光伏×价格 历史 {hist_corr_gp:+.5f} → 场景 {sc_corr_gp:+.5f}；"
          f"负荷×价格 历史 {hist_corr_lp:+.5f} → 场景 {sc_corr_lp:+.5f}")
    print(f"     缓存: {OUT_DATA / f'scenarios_M{M}.pkl'}")
    return cache


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--M", type=int, default=20)
    ap.add_argument("--pv-source", choices=["q2", "official"], default="q2")
    args = ap.parse_args()
    try:
        TABLES.mkdir(parents=True, exist_ok=True)
        build(args.M, args.pv_source)
        return 0
    except Exception as exc:  # noqa: BLE001
        print("=" * 70)
        traceback.print_exc()
        print(f"[05] 失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
