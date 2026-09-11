# -*- coding: utf-8 -*-
"""优化版 Q2 因果预测：直接预测净负荷 N=L-G，使用价格加权的非对称损失。"""
import os, pickle, traceback
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from paths import Q2_DATA_PROCESSING, Q2_TABLES, Q2_ROOT

T = 144
D = 365
SEED = 20260101
ROLL_WINDOW = 7
RIDGE_ALPHA = 1.0
GBM_PARAMS = dict(max_iter=100, max_depth=3, learning_rate=0.1,
                  min_samples_leaf=20, l2_regularization=1.0, random_state=SEED)
ASYMMETRY = 3.0  # 低估净负荷的惩罚倍数（低估比高估更危险）


def build_feature_matrix(Z, dates):
    rows = []
    for d in range(D):
        dow = dates[d].weekday()
        doy = dates[d].timetuple().tm_yday
        for t in range(T):
            lag1 = Z[t, d - 1] if d - 1 >= 0 else Z[t, 0]
            lag7 = Z[t, max(0, d - 7)]
            hist = Z[t, max(0, d - ROLL_WINDOW):d]
            if hist.size == 0:
                roll_mean = Z[t, 0]
                roll_std = 0.0
            else:
                roll_mean = float(np.mean(hist))
                roll_std = float(np.std(hist)) if hist.size >= 2 else 0.0
            rows.append([float(t + 1), float(dow), float(doy),
                         float(lag1), float(lag7), roll_mean, roll_std])
    return np.asarray(rows, dtype=float)


def slice_train(Xfull, upto_day):
    if upto_day < 0:
        return Xfull[:0]
    return Xfull[:(upto_day + 1) * T]


def slice_day(Xfull, day):
    return Xfull[day * T:(day + 1) * T]


def seasonal_predict(Z, train_upto):
    if train_upto < 0:
        return np.zeros(T, dtype=float)
    return np.nanmedian(Z[:, :train_upto + 1], axis=1)


def price_weighted_asym_loss(pred, actual, price):
    err = pred - actual
    w = price * np.where(err < 0, ASYMMETRY, 1.0)
    denom = float(np.sum(price * np.abs(actual)))
    if denom == 0:
        return 0.0 if float(np.sum(np.abs(pred))) == 0.0 else np.inf
    return float(np.sum(w * np.abs(err)) / denom)


def train_ridge(X, y):
    model = Ridge(alpha=RIDGE_ALPHA, random_state=SEED)
    model.fit(X, y)
    return model


def train_gbm(X, y):
    model = HistGradientBoostingRegressor(**GBM_PARAMS)
    model.fit(X, y)
    return model


def choose_and_predict(i, Z, Xfull, price):
    if i == 0:
        return np.zeros(T), "seasonal_naive", None, None
    val_train_upto = i - 2
    val_day = i - 1
    y_val = Z[:, val_day]
    X_val = slice_day(Xfull, val_day)
    scores = {}
    pred_naive_val = seasonal_predict(Z, val_train_upto)
    scores["seasonal_naive"] = price_weighted_asym_loss(pred_naive_val, y_val, price) if val_train_upto >= 0 else np.inf
    X_tr = slice_train(Xfull, val_train_upto)
    if val_train_upto >= 0 and X_tr.shape[0] > 0:
        y_tr = Z[:, :val_train_upto + 1].T.reshape(-1)
        for name in ("ridge", "gbm"):
            try:
                model = train_ridge(X_tr, y_tr) if name == "ridge" else train_gbm(X_tr, y_tr)
                pred_val = model.predict(X_val)
                scores[name] = price_weighted_asym_loss(pred_val, y_val, price)
            except Exception:
                scores[name] = np.inf
    else:
        scores["ridge"] = scores["gbm"] = np.inf
    finite = {k: v for k, v in scores.items() if np.isfinite(v)}
    selected = min(finite, key=finite.get) if finite else "seasonal_naive"
    val_loss = float(finite[selected]) if selected in finite else None
    if selected == "seasonal_naive":
        pred_i = seasonal_predict(Z, i - 1)
    else:
        try:
            model = train_ridge(slice_train(Xfull, i - 1), Z[:, :i].T.reshape(-1)) if selected == "ridge" else train_gbm(slice_train(Xfull, i - 1), Z[:, :i].T.reshape(-1))
            pred_i = model.predict(slice_day(Xfull, i))
        except Exception:
            pred_i = seasonal_predict(Z, i - 1)
            selected = "seasonal_naive"
            val_loss = None
    return pred_i, selected, val_loss, scores


def run_forecast():
    pkl = os.path.join(Q2_DATA_PROCESSING, "q2_dataset.pkl")
    with open(pkl, "rb") as fh:
        ds = pickle.load(fh)
    dates = list(ds["dates"])
    L = ds["load"].astype(float)
    G = ds["pv"].astype(float)
    N = L - G
    price_vec = ds["price"][:, 0].astype(float)
    Xfull = build_feature_matrix(N, dates)
    Nhat = np.zeros((T, D))
    records = []
    for i in range(D):
        if i == 0:
            Nhat[:, 0] = 0.0
            records.append([dates[0], "seasonal_naive", None, 1])
            continue
        pred, sel, val_loss, scores = choose_and_predict(i, N, Xfull, price_vec)
        Nhat[:, i] = pred
        records.append([dates[i], sel, val_loss, 1 if dates[i].month == 1 else 0])
    val_df = pd.DataFrame(records, columns=["date", "selected_model", "validation_loss", "is_warmup"])
    val_df.to_csv(os.path.join(Q2_TABLES, "net_forecast_validation.csv"), index=False, encoding="utf-8-sig")
    months = [d.month for d in dates]
    rows = []
    for m in range(2, 13):
        mask = np.array([1 if mm == m else 0 for mm in months], dtype=bool)
        err = np.abs(Nhat - N)[:, mask]
        act = N[:, mask]
        n = err.size
        mae = float(np.sum(err) / n)
        wape = float(np.sum(err) / np.sum(np.abs(act))) if np.sum(np.abs(act)) else 0.0
        rows.append([m, mae, wape, int(mask.sum()), n])
    metrics = pd.DataFrame(rows, columns=["month", "MAE_kwh", "WAPE", "n_days", "n_samples"])
    metrics.to_csv(os.path.join(Q2_TABLES, "net_forecast_monthly_metrics.csv"), index=False, encoding="utf-8-sig")
    fcast = {"Nhat": Nhat, "N": N, "dates": np.array(dates, dtype=object),
             "selected_models": val_df, "monthly_metrics": metrics}
    with open(os.path.join(Q2_DATA_PROCESSING, "net_forecasts.pkl"), "wb") as fh:
        pickle.dump(fcast, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print("[opt forecast] net-load forecasts saved")
    return fcast

if __name__ == "__main__":
    try:
        run_forecast()
    except Exception:
        traceback.print_exc()
        raise


