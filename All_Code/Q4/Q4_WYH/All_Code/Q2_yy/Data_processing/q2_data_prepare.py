from pathlib import Path
import pickle
import sys

import numpy as np
import pandas as pd

Q2_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = Q2_ROOT.parents[1]
ATTACH_DIR = REPO_ROOT / "Data" / "附件"
Q1_MV = REPO_ROOT / "All_Code" / "Q1" / "Results" / "Tables" / "q1_storage_marginal_value_for_q2.csv"
TRANS_DIR = REPO_ROOT / "All_Code" / "Data_preprocessing" / "Data_transformation"
OUT_DIR = Q2_ROOT / "Data_processing"
TABLES = Q2_ROOT / "Results" / "Tables"

T, D = 144, 365


def prepare():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    a1 = pd.read_excel(ATTACH_DIR / "附件1.xlsx", sheet_name=0)
    if a1.shape[0] != T or a1.shape[1] < 2:
        raise ValueError(f"附件1结构异常: {a1.shape}")
    price_vec = pd.to_numeric(a1.iloc[:, 1], errors="raise").to_numpy(float)

    sheets = pd.read_excel(ATTACH_DIR / "附件2.xlsx", sheet_name=None)
    if len(sheets) != 2:
        raise ValueError(f"附件2工作表数量应为2，实际{len(sheets)}")
    load_raw, pv_raw = list(sheets.values())
    if load_raw.shape != (D, T + 1) or pv_raw.shape != (D, T + 1):
        raise ValueError(f"附件2结构异常: load={load_raw.shape}, pv={pv_raw.shape}")
    load_dates = pd.to_datetime(load_raw.iloc[:, 0], errors="raise").dt.date.to_list()
    pv_dates = pd.to_datetime(pv_raw.iloc[:, 0], errors="raise").dt.date.to_list()
    expected = pd.date_range("2025-01-01", "2025-12-31", freq="D").date.tolist()
    if load_dates != expected or pv_dates != expected:
        raise ValueError("附件2负荷/光伏日期与2025年完整日历不一致")
    # 附件记录功率(kW)，每格10分钟，严格乘1/6得到电量(kWh)。
    load_kwh = load_raw.iloc[:, 1:].apply(pd.to_numeric, errors="raise").to_numpy(float).T / 6.0
    pv_kwh = pv_raw.iloc[:, 1:].apply(pd.to_numeric, errors="raise").to_numpy(float).T / 6.0
    if (price_vec <= 0).any() or (load_kwh < 0).any() or (pv_kwh < 0).any():
        raise ValueError("官方附件存在非正电价或负荷/光伏负值，程序拒绝修改后继续")

    tm = pd.read_csv(TRANS_DIR / "time_map.csv", encoding="utf-8-sig")
    if tm.shape[0] != T or not np.array_equal(tm["time_idx"].to_numpy(int), np.arange(1, T + 1)):
        raise ValueError("time_map不是1..144的完整时段映射")
    q1 = pd.read_csv(Q1_MV, encoding="utf-8-sig")
    col = "storage_marginal_value_yuan_per_kwh"
    if col not in q1.columns:
        raise KeyError(f"Q1边际价值文件缺少{col}")
    mv = pd.to_numeric(q1[col], errors="coerce").dropna().to_numpy(float)
    if mv.size == 0:
        raise ValueError("Q1边际价值没有有效数据")
    stats = {"median": float(np.median(mv)), "mean": float(np.mean(mv)),
             "min": float(np.min(mv)), "max": float(np.max(mv)),
             "p25": float(np.percentile(mv, 25)), "p75": float(np.percentile(mv, 75)),
             "n": int(mv.size)}

    dates = np.asarray(expected, dtype=object)
    dataset = {
        "dates": dates,
        "date_str": np.asarray([d.strftime("%Y-%m-%d") for d in expected], dtype=object),
        "price": np.tile(price_vec[:, None], (1, D)),
        "load": load_kwh, "pv": pv_kwh,
        "time_mapping": {"internal_idx": tm["time_idx"].to_numpy(int),
                         "time_labels": tm["data_label"].astype(str).tolist(),
                         "template_col": np.arange(2, T + 2, dtype=int),
                         "template_labels": tm["template_col_label"].astype(str).tolist()},
        "kappa2_base": stats["median"], "kappa2_stats": stats,
        "constants": {"T": T, "D": D, "DELTA_T": 1/6,
                      "CHARGE_CAP_KWH": 5000/6, "ETA_C": 0.9, "ETA_R": 0.9,
                      "SOC_MIN": 1200.0, "SOC_MAX": 10800.0, "SOC0": 6000.0},
        "provenance": {"price": str(ATTACH_DIR / "附件1.xlsx"),
                       "load_pv": str(ATTACH_DIR / "附件2.xlsx"),
                       "conversion": "official power kW * (10/60) h = kWh; no imputation"},
    }
    with open(OUT_DIR / "q2_dataset.pkl", "wb") as fh:
        pickle.dump(dataset, fh, protocol=pickle.HIGHEST_PROTOCOL)
    pd.DataFrame([stats]).to_excel(TABLES / "kappa2_calibration.xlsx", index=False)
    print(f"dataset saved: price={dataset['price'].shape}, load={load_kwh.shape}, pv={pv_kwh.shape}")
    print("raw attachment conversion: exact /6, no imputation")
    return dataset


if __name__ == "__main__":
    try:
        prepare()
    except Exception as exc:
        print(f"data preparation failed: {exc}")
        sys.exit(1)
