# -*- coding: utf-8 -*-
"""
负荷与光伏联合场景生成（2026 数模 C 题 问题二）。

把 144 维负荷残差与 144 维光伏残差按同一历史日期作为一个“整日联合残差块”同步抽样，
以保持二者的日内时间相关性与相互关联，不单独打乱任一侧的残差。

实现约定：
1. 残差定义 res = 实际 - 预测（负荷、光伏各自）。
2. 第 i 天结束后，把当天的整日联合残差块追加进残差库（2025-01-01 无历史，不追加）。
3. 决策日 i 的场景只使用严格早于 i 的最近 30 个残差块。
4. 场景值作物理截断 L_scen >= 0、G_scen >= 0，并记录截断比例。
5. 固定随机种子；场景数 M 变化时共用同一基础种子（取前 M 个抽样），保证嵌套可比。
"""
import os
import pickle
import traceback

import numpy as np
import pandas as pd

# 路径常量（自包含）
from paths import Q2_ROOT, Q2_DATA_PROCESSING, Q2_TABLES
Q2CODE = str(Q2_ROOT)
DATA_PROC = str(Q2_DATA_PROCESSING)
TABLES = str(Q2_TABLES)

SEED = 20260101
HISTORY_WINDOW = 30
T = 144
D = 365


class _ResidualBlock:
    """一个“同日联合残差块”：同一天的负荷残差 + 光伏残差（144 维各一）。"""

    __slots__ = ("day", "load_res", "pv_res")

    def __init__(self, day: int, load_res: np.ndarray, pv_res: np.ndarray):
        self.day = day
        self.load_res = load_res.astype(float)
        self.pv_res = pv_res.astype(float)


class ScenarioEngine:
    def __init__(self, dataset: dict, forecasts: dict, seed: int = SEED):
        self.load = dataset["load"].astype(float)     # (144, D)
        self.pv = dataset["pv"].astype(float)         # (144, D)
        self.Lhat = forecasts["Lhat"].astype(float)   # (144, D)
        self.Ghat = forecasts["Ghat"].astype(float)   # (144, D)
        self.dates = list(dataset["dates"])
        self.seed = seed
        if self.load.shape != (T, D) or self.pv.shape != (T, D):
            raise ValueError(f"数据矩阵形状异常: load={self.load.shape}, pv={self.pv.shape}")

    def _available_blocks(self, i: int, blocks: list) -> list:
        """仅返回决策日前最近30个已实现日的联合残差块。"""
        first_day = max(1, i - HISTORY_WINDOW)
        return [b for b in blocks if first_day <= b.day < i]

    def generate_day(self, i: int, M: int, blocks: list):
        """
        生成决策日 i 的 M 个联合场景。
        返回 (L_scen (M,144), G_scen (M,144), trunc_load, trunc_pv)。
        """
        M = int(M)
        avail = self._available_blocks(i, blocks)
        if len(avail) == 0:
            # 残差库为空：场景退化为点预测（20 个相同场景），日志说明
            L_scen = np.tile(self.Lhat[:, i], (M, 1))
            G_scen = np.tile(self.Ghat[:, i], (M, 1))
            return L_scen, G_scen, 0, 0

        rng = np.random.default_rng(self.seed * 1000 + i)
        idx = rng.integers(0, len(avail), size=M)   # 有放回抽样，嵌套可比
        L_res = np.vstack([avail[j].load_res for j in idx])   # (M,144)
        G_res = np.vstack([avail[j].pv_res for j in idx])     # (M,144)

        L_scen = self.Lhat[:, i][None, :] + L_res
        G_scen = self.Ghat[:, i][None, :] + G_res

        # 物理截断：负荷、光伏均不小于 0，并记录截断量
        trunc_load = int(np.sum(L_scen < 0))
        trunc_pv = int(np.sum(G_scen < 0))
        L_scen = np.clip(L_scen, 0.0, None)
        G_scen = np.clip(G_scen, 0.0, None)
        return L_scen, G_scen, trunc_load, trunc_pv

    def generate_all(self, M: int):
        """
        按天顺序生成全部决策日的场景（模拟滚动：day i 只使用截至 i-1 的残差库）。
        返回 L_all(D,M,T), G_all(D,M,T), trunc_load_total, trunc_pv_total。
        """
        blocks: list = []
        L_all = np.zeros((D, M, T), dtype=float)
        G_all = np.zeros((D, M, T), dtype=float)
        trunc_load_total = 0
        trunc_pv_total = 0
        for i in range(D):
            L_all[i], G_all[i], tl, tp = self.generate_day(i, M, blocks)
            trunc_load_total += tl
            trunc_pv_total += tp
            if i >= 1:
                # 第 i 天结束后追加残差块（day0=2025-01-01 不入库）
                blocks.append(_ResidualBlock(
                    day=i,
                    load_res=self.load[:, i] - self.Lhat[:, i],
                    pv_res=self.pv[:, i] - self.Ghat[:, i],
                ))
        return L_all, G_all, trunc_load_total, trunc_pv_total

    def save_demo(self, L_all: np.ndarray, G_all: np.ndarray, demo_date: str = "2025-07-15"):
        """挑一个典型日保存 20 个场景长表，供绘制场景分位区间图。"""
        date_strs = [d.strftime("%Y-%m-%d") for d in self.dates]
        if demo_date not in date_strs:
            raise ValueError(f"演示日 {demo_date} 不在日期序列中")
        i = date_strs.index(demo_date)
        M = L_all.shape[1]
        rows = []
        for m in range(M):
            for t in range(T):
                rows.append([demo_date, m + 1, t + 1, L_all[i, m, t], G_all[i, m, t]])
        df = pd.DataFrame(rows, columns=["date", "scenario", "interval", "L_scen_kwh", "G_scen_kwh"])
        path = os.path.join(DATA_PROC, "scenario_demo.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"    场景演示表已写入: {path} (date={demo_date}, M={M})")
        return path


def run_scenarios(M_demo: int = 20) -> dict:
    ds_path = os.path.join(DATA_PROC, "q2_dataset.pkl")
    fc_path = os.path.join(DATA_PROC, "forecasts.pkl")
    if not os.path.exists(ds_path):
        raise FileNotFoundError(f"缺少数据集: {ds_path}")
    if not os.path.exists(fc_path):
        raise FileNotFoundError(f"缺少预测缓存: {fc_path}，请先运行 forecast.py")
    with open(ds_path, "rb") as fh:
        ds = pickle.load(fh)
    with open(fc_path, "rb") as fh:
        fc = pickle.load(fh)

    eng = ScenarioEngine(ds, fc)
    print(f"[场景生成] 生成 M={M_demo} 全部场景（整日残差块联合抽样）")
    L_all, G_all, tl, tp = eng.generate_all(M_demo)
    print(f"    场景矩阵: L_all={L_all.shape}, G_all={G_all.shape}")
    print(f"    物理截断统计: 负荷截断 {tl} 个, 光伏截断 {tp} 个 "
          f"(总样本 {D * M_demo * T})")

    # 因果检查：打印最大残差库日期 < 决策日（结构性保证）
    print("    因果检查：决策日 i 仅使用最近30个日期 < i 的联合残差块")

    eng.save_demo(L_all, G_all, "2025-07-15")

    # 缓存场景供 rolling 复用（M=20 默认）
    cache = {
        "M": M_demo,
        "L_all": L_all,
        "G_all": G_all,
        "seed": SEED,
        "history_window_days": HISTORY_WINDOW,
        "sampling_rule": "joint_daily_residual_blocks_strictly_before_decision_day",
    }
    cache_path = os.path.join(DATA_PROC, f"scenarios_M{M_demo}.pkl")
    with open(cache_path, "wb") as fh:
        pickle.dump(cache, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"    场景缓存已保存: {cache_path}")
    return cache


def main() -> int:
    try:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--M", type=int, default=20)
        args = parser.parse_args()
        if args.M <= 0:
            raise ValueError("M 必须为正整数")
        run_scenarios(args.M)
        print("场景生成完成")
        return 0
    except Exception as exc:
        print("=" * 60)
        print("场景生成失败：")
        traceback.print_exc()
        print(f"错误信息: {exc}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
