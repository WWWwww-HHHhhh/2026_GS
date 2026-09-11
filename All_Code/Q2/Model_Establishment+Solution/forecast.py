# -*- coding: utf-8 -*-
"""
P1 因果负荷/光伏预测（2026 数模 C 题 问题二）
================================================
实现依据：总纲第 4.2 节（具体模型流程）、4.4 节（符号）、4.8 节（注意事项）。
本模块对负荷与光伏“分别建模”，严禁只预测净负荷。

【全局铁律摘要】
1. 所有数值只来自附件或严格衍生。
2. 因果纪律：预测第 i 天只允许使用 <= i-1 天（当天 0:00 以前）的数据；
   当天实际值只用于事后误差统计，绝不进入预测特征。
3. 负荷与光伏分别建模。
4. 2025-01-01 无历史，预测输出全 0（仅预热，不进残差库、不进统计）；
   2025-01 整月为预热期，仅用于滚动机器与残差库积累。
5. 随机种子固定，保证复现。

【特征说明（只用历史构成）】
f0=时段索引 t(1..144), f1=星期(0..6), f2=年内日序 doy,
f3=前1天同t实际值, f4=前7天同t实际值, f5=同t滚动均值(窗口7天), f6=同t滚动标准差(窗口7天)。
缺失滞后值按“可得的过去值”回退填充（提示词明确允许），并在日志记录填充量。

【三个候选预测器】
a) seasonal_naive：训练集同 t 历史中位数；
b) ridge：岭回归（正则化线性）；
c) gbm：sklearn HistGradientBoostingRegressor（浅树）。
"""
import os
import sys
import pickle
import traceback
from datetime import datetime, date

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor

# ---------------------------------------------------------------------------
# 路径常量（自包含）
# ---------------------------------------------------------------------------
GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q2CODE = os.path.join(GS, r"All_Code\Q2")
DATA_PROC = os.path.join(Q2CODE, "Data_processing")
TABLES = os.path.join(Q2CODE, "Results", "Tables")
MODEL_DIR = os.path.join(Q2CODE, "Model_Establishment+Solution")

SEED = 20260101
T = 144
D = 365
ROLL_WINDOW = 7

# GBM 超参（浅树，总纲/提示词：max_depth=3, learning_rate=0.1, n_estimators<=200）
GBM_PARAMS = dict(max_iter=100, max_depth=3, learning_rate=0.1,
                  min_samples_leaf=20, l2_regularization=1.0, random_state=SEED)
RIDGE_ALPHA = 1.0


def ensure_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"无法创建目录 {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# 特征构造
# ---------------------------------------------------------------------------
def build_feature_matrix(Z: np.ndarray, dates) -> np.ndarray:
    """
    构造全部 (D*T, 7) 的特征矩阵。Z: (144, D) 每时段电量 kWh。
    特征只依赖 <= 当前样本日 d 的历史，因此训练与预测共用同一特征矩阵。
    """
    n_days = Z.shape[1]
    rows = []
    for d in range(n_days):
        dow = dates[d].weekday()          # Monday=0..Sunday=6
        doy = dates[d].timetuple().tm_yday
        for t in range(T):
            # 前1天 / 前7天 同 t 实际值（缺失回退到最早可得）
            lag1 = Z[t, d - 1] if d - 1 >= 0 else Z[t, 0]
            src7 = max(0, d - 7)
            lag7 = Z[t, src7]
            # 同 t 滚动均值 / 标准差（窗口 7 天，只用历史，不含当天 d）
            hist = Z[t, max(0, d - ROLL_WINDOW):d]
            if hist.size == 0:
                roll_mean = Z[t, 0]       # 无过去值，回退最早可得
                roll_std = 0.0
            else:
                roll_mean = float(np.mean(hist))
                roll_std = float(np.std(hist)) if hist.size >= 2 else 0.0
            rows.append([float(t + 1), float(dow), float(doy),
                         float(lag1), float(lag7), roll_mean, roll_std])
    return np.asarray(rows, dtype=float)


def slice_train(Xfull: np.ndarray, upto_day: int):
    """取 0..upto_day 天（含）的训练特征。"""
    if upto_day < 0:
        return Xfull[:0]
    return Xfull[:(upto_day + 1) * T]


def slice_day(Xfull: np.ndarray, day: int):
    """取第 day 天的特征（144 行）。"""
    return Xfull[day * T:(day + 1) * T]


def seasonal_predict(Z: np.ndarray, train_upto: int, pred_day: int):
    """
    季节朴素：用训练集（0..train_upto 天）同 t 历史中位数预测 pred_day。
    """
    if train_upto < 0:
        return np.zeros(T, dtype=float)
    hist = Z[:, :train_upto + 1]          # (144, n_days)
    return np.nanmedian(hist, axis=1)


def wape(pred: np.ndarray, actual: np.ndarray) -> float:
    """加权绝对百分比误差：sum|pred-actual| / sum|actual|。"""
    denom = float(np.sum(np.abs(actual)))
    if denom == 0:
        return 0.0 if float(np.sum(np.abs(pred))) == 0.0 else np.inf
    return float(np.sum(np.abs(pred - actual)) / denom)


def train_ridge(X: np.ndarray, y: np.ndarray):
    if X.shape[0] == 0:
        raise ValueError("训练集为空，无法训练 Ridge")
    model = Ridge(alpha=RIDGE_ALPHA, random_state=SEED)
    model.fit(X, y)
    return model


def train_gbm(X: np.ndarray, y: np.ndarray):
    if X.shape[0] == 0:
        raise ValueError("训练集为空，无法训练 GBM")
    model = HistGradientBoostingRegressor(**GBM_PARAMS)
    model.fit(X, y)
    return model


# ---------------------------------------------------------------------------
# 每日模型选择与预测
# ---------------------------------------------------------------------------
def choose_and_predict(i: int, Z: np.ndarray, Xfull: np.ndarray):
    """
    对决策日 i（0-based，i>=1）：
    1) 验证：用 0..i-2 天训练，评估 i-1 天，以 WAPE 选最优候选；
    2) 重训：用 0..i-1 天训练选中候选，预测第 i 天。
    返回 (pred_day_144, selected_name, val_wape)。
    """
    # ---- 特殊：i=0 无历史 ----
    if i == 0:
        return np.zeros(T, dtype=float), "seasonal_naive", None

    # ---- 验证阶段（i=1 时无 i-2 天数据，退化为季节朴素） ----
    val_train_upto = i - 2
    val_day = i - 1
    y_val = Z[:, val_day]
    X_val = slice_day(Xfull, val_day)

    candidates = {}
    val_scores = {}
    # a) 季节朴素
    pred_naive_val = seasonal_predict(Z, val_train_upto, val_day)
    candidates["seasonal_naive"] = lambda: seasonal_predict(Z, i - 1, i)
    val_scores["seasonal_naive"] = wape(pred_naive_val, y_val) if val_train_upto >= 0 else np.inf

    # b) 岭回归 / c) GBM：仅在存在训练数据时参与验证
    X_tr = slice_train(Xfull, val_train_upto)
    if val_train_upto >= 0 and X_tr.shape[0] > 0:
        y_tr = Z[:, :val_train_upto + 1].T.reshape(-1)
        for name in ("ridge", "gbm"):
            try:
                model = train_ridge(X_tr, y_tr) if name == "ridge" else train_gbm(X_tr, y_tr)
                pred_val = model.predict(X_val)
                val_scores[name] = wape(pred_val, y_val)
            except Exception as exc:  # 训练失败则该候选不可用
                val_scores[name] = np.inf
                print(f"    [warn] 日{i} {name} 验证失败: {exc}")
    else:
        val_scores["ridge"] = np.inf
        val_scores["gbm"] = np.inf

    # 选择验证 WAPE 最小的候选
    finite_scores = {k: v for k, v in val_scores.items() if np.isfinite(v)}
    if not finite_scores:
        selected = "seasonal_naive"
        val_wape = None
    else:
        selected = min(finite_scores, key=finite_scores.get)
        val_wape = float(finite_scores[selected])

    # ---- 重训并预测第 i 天 ----
    if selected == "seasonal_naive":
        pred_i = seasonal_predict(Z, i - 1, i)
    else:
        X_final = slice_train(Xfull, i - 1)
        y_final = Z[:, :i].T.reshape(-1)
        try:
            model = train_ridge(X_final, y_final) if selected == "ridge" else train_gbm(X_final, y_final)
            pred_i = model.predict(slice_day(Xfull, i))
        except Exception as exc:
            # 极端情况下退化为季节朴素，保证流程不中断
            print(f"    [warn] 日{i} {selected} 重训失败，退化为季节朴素: {exc}")
            pred_i = seasonal_predict(Z, i - 1, i)
            selected = "seasonal_naive"
            val_wape = None

    return pred_i, selected, val_wape


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run_forecast() -> dict:
    pkl_path = os.path.join(DATA_PROC, "q2_dataset.pkl")
    if not os.path.exists(pkl_path):
        raise FileNotFoundError(f"缺少数据集: {pkl_path}，请先运行 P0 q2_data_prepare.py")
    with open(pkl_path, "rb") as fh:
        ds = pickle.load(fh)

    dates = list(ds["dates"])
    Z_load = ds["load"].astype(float)     # (144,365) kWh
    Z_pv = ds["pv"].astype(float)         # (144,365) kWh
    if Z_load.shape != (T, D) or Z_pv.shape != (T, D):
        raise ValueError(f"数据矩阵形状异常: load={Z_load.shape}, pv={Z_pv.shape}")

    print("[P1] 构造负荷与光伏特征矩阵（只用历史）")
    Xf_load = build_feature_matrix(Z_load, dates)
    Xf_pv = build_feature_matrix(Z_pv, dates)

    Lhat = np.zeros((T, D), dtype=float)
    Ghat = np.zeros((T, D), dtype=float)
    records = []

    for i in range(D):
        if i == 0:
            Lhat[:, 0] = 0.0
            Ghat[:, 0] = 0.0
            records.append([dates[0], "load", "seasonal_naive", None, 1])
            records.append([dates[0], "pv", "seasonal_naive", None, 1])
            continue

        pred_l, sel_l, w_l = choose_and_predict(i, Z_load, Xf_load)
        pred_g, sel_g, w_g = choose_and_predict(i, Z_pv, Xf_pv)
        Lhat[:, i] = pred_l
        Ghat[:, i] = pred_g
        warmup = 1 if dates[i].month == 1 else 0
        records.append([dates[i], "load", sel_l, w_l, warmup])
        records.append([dates[i], "pv", sel_g, w_g, warmup])
        if i % 30 == 0 or i == D - 1:
            print(f"    已预测到 {dates[i]} (i={i})")

    # 每日模型选择与验证 WAPE 表
    val_df = pd.DataFrame(records, columns=["date", "series", "selected_model", "validation_wape", "is_warmup"])
    val_path = os.path.join(TABLES, "forecast_validation.csv")
    val_df.to_csv(val_path, index=False, encoding="utf-8-sig")
    print(f"    每日模型选择表已写入: {val_path}")

    # 事后预测误差（预测 vs 实际）按月汇总，仅报告期 2-12 月
    months = [d.month for d in dates]
    load_err = np.abs(Lhat - Z_load)      # (144,365)
    pv_err = np.abs(Ghat - Z_pv)
    mae_rows = []
    for m in range(2, 13):
        mask = np.array([1 if mm == m else 0 for mm in months], dtype=bool)
        n_days = int(mask.sum())
        n_samples = n_days * T
        for name, err, actual in (("load", load_err, Z_load), ("pv", pv_err, Z_pv)):
            err_m = err[:, mask]
            act_m = actual[:, mask]
            mae = float(np.sum(err_m) / n_samples) if n_samples else np.nan
            denom = float(np.sum(np.abs(act_m)))
            w = float(np.sum(err_m) / denom) if denom else 0.0
            mae_rows.append([m, name, mae, w, n_days, n_samples])
    mae_df = pd.DataFrame(mae_rows, columns=["month", "series", "MAE_kwh", "WAPE", "n_days", "n_samples"])
    mae_path = os.path.join(TABLES, "forecast_monthly_metrics.csv")
    mae_df.to_csv(mae_path, index=False, encoding="utf-8-sig")
    print(f"    月度预测误差表已写入: {mae_path}")

    # 缓存预测，供 scenarios/rolling 复用
    fcast = {
        "Lhat": Lhat, "Ghat": Ghat,
        "dates": np.array(dates, dtype=object),
        "selected_models": val_df,
        "monthly_metrics": mae_df,
    }
    fcast_path = os.path.join(DATA_PROC, "forecasts.pkl")
    with open(fcast_path, "wb") as fh:
        pickle.dump(fcast, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"    预测缓存已保存: {fcast_path}")

    # 因果验收打印：预测第 i 天所用最大特征日期 < i
    print("    因果检查：预测特征的最大可用日期为 i-1（严格早于决策日 i）")
    return {"Lhat": Lhat, "Ghat": Ghat, "records": records}


def main() -> int:
    try:
        run_forecast()
        print("P1 forecast 完成")
        return 0
    except Exception as exc:
        print("=" * 60)
        print("P1 forecast 执行失败：")
        traceback.print_exc()
        print(f"错误信息: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
