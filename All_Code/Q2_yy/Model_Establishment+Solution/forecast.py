import os
import pickle
import time
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
try:
    from sklearn.experimental import enable_hist_gradient_boosting  # noqa: F401
except ImportError:
    pass
from sklearn.ensemble import HistGradientBoostingRegressor
from paths import Q2_DATA_PROCESSING as DATA_PROC, Q2_TABLES as TABLES

T, D = 144, 365
SEED = 20260101
RIDGE_ALPHA_LOAD = 10.0
RIDGE_ALPHA_PV = 1.0
GBM_LOAD = dict(max_iter=250, max_depth=4, learning_rate=0.08,
                min_samples_leaf=20, l2_regularization=1.0, random_state=SEED)
GBM_PV = dict(max_iter=100, max_depth=3, learning_rate=0.10,
              min_samples_leaf=20, l2_regularization=1.0, random_state=SEED)


def build_features(Z, dates, extended):
    rows = []
    for d in range(D):
        dow = dates[d].weekday()
        doy = dates[d].timetuple().tm_yday
        prev_mean = float(np.mean(Z[:, d - 1])) if d else float(np.mean(Z[:, 0]))
        for t in range(T):
            lag = lambda k: Z[t, d-k] if d-k >= 0 else Z[t, 0]
            h7 = Z[t, max(0, d-7):d]
            rm7 = float(np.mean(h7)) if h7.size else float(Z[t, 0])
            rs7 = float(np.std(h7)) if h7.size >= 2 else 0.0
            if not extended:
                rows.append([t+1, dow, doy, lag(1), lag(7), rm7, rs7])
                continue
            h14 = Z[t, max(0, d-14):d]
            ph = t / T
            rows.append([ph, np.sin(2*np.pi*ph), np.cos(2*np.pi*ph), dow, int(dow >= 5),
                         doy, np.sin(2*np.pi*doy/365.0), np.cos(2*np.pi*doy/365.0),
                         lag(1), lag(2), lag(3), lag(7), lag(14), rm7, rs7,
                         float(np.mean(h14)) if h14.size else float(Z[t, 0]), prev_mean])
    return np.asarray(rows, dtype=float)


def slice_train(X, upto):
    return X[:(upto+1)*T] if upto >= 0 else X[:0]


def slice_day(X, d):
    return X[d*T:(d+1)*T]


def naive(Z, upto):
    return np.zeros(T) if upto < 0 else np.median(Z[:, :upto+1], axis=1)


def wape(pred, actual):
    den = float(np.sum(np.abs(actual)))
    return float(np.sum(np.abs(pred-actual))/den) if den else float("inf")


def predict_day(i, Z, X, gbm_params, ridge_alpha):
    if i == 0:
        return np.zeros(T), "seasonal_naive", np.nan
    train_end = i - 2
    val_day = i - 1
    scores = {"seasonal_naive": wape(naive(Z, train_end), Z[:, val_day]) if train_end >= 0 else np.inf}
    Xtr = slice_train(X, train_end)
    if Xtr.shape[0]:
        ytr = Z[:, :train_end+1].T.reshape(-1)
        for name in ("ridge", "gbm"):
            try:
                model = Ridge(alpha=ridge_alpha) if name == "ridge" else HistGradientBoostingRegressor(**gbm_params)
                model.fit(Xtr, ytr)
                scores[name] = wape(model.predict(slice_day(X, val_day)), Z[:, val_day])
            except Exception:
                scores[name] = np.inf
    else:
        scores.update(ridge=np.inf, gbm=np.inf)
    selected = min(scores, key=scores.get)
    if selected == "seasonal_naive":
        pred = naive(Z, i-1)
    else:
        model = Ridge(alpha=ridge_alpha) if selected == "ridge" else HistGradientBoostingRegressor(**gbm_params)
        model.fit(slice_train(X, i-1), Z[:, :i].T.reshape(-1))
        pred = model.predict(slice_day(X, i))
    return np.clip(np.asarray(pred, dtype=float), 0.0, None), selected, float(scores[selected])


def run_forecast():
    started = time.time()
    with open(os.path.join(str(DATA_PROC), "q2_dataset.pkl"), "rb") as fh:
        ds = pickle.load(fh)
    dates = list(ds["dates"]); load = ds["load"].astype(float); pv = ds["pv"].astype(float)
    Xl = build_features(load, dates, extended=True)
    Xg = build_features(pv, dates, extended=False)
    Lhat = np.zeros((T, D)); Ghat = np.zeros((T, D)); rows = []
    for i in range(D):
        Lhat[:, i], ml, el = predict_day(i, load, Xl, GBM_LOAD, RIDGE_ALPHA_LOAD)
        Ghat[:, i], mg, eg = predict_day(i, pv, Xg, GBM_PV, RIDGE_ALPHA_PV)
        rows.extend([[dates[i], "load", ml, el, int(dates[i].month == 1)],
                     [dates[i], "pv", mg, eg, int(dates[i].month == 1)]])
        if i % 30 == 0 or i == D-1:
            print(f"forecast {dates[i]} ({i}/{D-1})", flush=True)
    val = pd.DataFrame(rows, columns=["date", "series", "selected_model", "validation_wape", "is_warmup"])
    val.to_csv(os.path.join(str(TABLES), "forecast_validation.csv"), index=False, encoding="utf-8-sig")
    mrows = []
    months = np.array([d.month for d in dates])
    for m in range(2, 13):
        mask = months == m
        for name, pred, actual in (("load", Lhat, load), ("pv", Ghat, pv)):
            err = np.abs(pred[:, mask]-actual[:, mask])
            mrows.append([m, name, float(np.mean(err)), float(np.sum(err)/np.sum(np.abs(actual[:, mask]))), int(mask.sum())])
    metrics = pd.DataFrame(mrows, columns=["month", "series", "MAE_kwh", "WAPE", "n_days"])
    metrics.to_csv(os.path.join(str(TABLES), "forecast_monthly_metrics.csv"), index=False, encoding="utf-8-sig")
    out = {"Lhat": Lhat, "Ghat": Ghat, "dates": np.array(dates, dtype=object),
           "selected_models": val, "monthly_metrics": metrics,
           "causality": "prediction day i uses target data only through i-1"}
    with open(os.path.join(str(DATA_PROC), "forecasts.pkl"), "wb") as fh:
        pickle.dump(out, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"forecast complete {time.time()-started:.1f}s", flush=True)
    return out


if __name__ == "__main__":
    run_forecast()
