from __future__ import annotations

import hashlib
import pickle
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

# ---- 口径常量与工具统一来自 q4_common（单一来源，避免口径漂移）----
sys.path.insert(0, str(Path(__file__).resolve().parent))
from q4_common import (  # noqa: E402
    CALIB_END, CALIB_START, CHARGE_CAP, D, DELTA_T, ETA_C, ETA_R, FH_COLS, OUT_DATA,
    Q2_DIR, REPORT_END, REPORT_START, SOC0, SOC_MAX, SOC_MIN, T, T_COLS, TABLES,
    TRANS, WYH, load_pickle_compat, sha256, wide_to_matrix,
)

OUT_DIR = OUT_DATA
CHECKS: list[dict] = []


def check(name: str, ok: bool, value: str, requirement: str) -> None:
    CHECKS.append({"检查项": name, "是否通过": bool(ok), "实测值": value, "要求": requirement})
    if not ok:
        raise AssertionError(f"[核验失败] {name}: 实测 {value}，要求 {requirement}")


def pv_forecast_linear_endpoint(hourly_kw: np.ndarray, issue_slot: int, prev_actual_kwh: float | None) -> np.ndarray:
    """附件3 小时级 kW -> 当日剩余时段 10min kWh。

    与 Q3 已审计通过的 `linear_endpoint` 完全同构（`All_Code/Q3/.../q3_core.py::PVForecast.get`）：
    节点位于 hour 端点（0, 60, ..., 1440 分钟），在 10, 20, ..., 10h 分钟处线性插值；
    issue=0 时锚点取 0 kW（当日尚无已实现光伏），锚点本身不进入未来时段。
    """
    h = T - issue_slot
    nodes = np.concatenate(([0.0], np.asarray(hourly_kw, dtype=float)))
    kw = np.interp(np.arange(1, h + 1) * 10.0, np.arange(25) * 60.0, nodes)
    return np.maximum(kw, 0.0) * DELTA_T


def build() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)

    # ---------------- 1. 官方附件指纹 ----------------
    att = WYH / "others" / "原始附件_CUMCM2026_C" / "附件"
    hashes = {}
    for f in ["附件1.xlsx", "附件2.xlsx", "附件3.xlsx", "附件4.xlsx"]:
        p = att / f
        if not p.exists():
            raise FileNotFoundError(p)
        hashes[f] = sha256(p)
    check("官方附件齐备（附件1-4）", len(hashes) == 4, f"{len(hashes)} 个文件", "4 个")

    # ---------------- 2. 读取项目标准派生产物 ----------------
    df_load = pd.read_parquet(TRANS / "df_load.parquet")
    df_pv = pd.read_parquet(TRANS / "df_pv.parquet")
    df_price = pd.read_parquet(TRANS / "df_price.parquet")
    df_fcst = pd.read_parquet(TRANS / "df_fcst.parquet")
    df_p1 = pd.read_parquet(TRANS / "df_p1.parquet")
    time_map = pd.read_csv(TRANS / "time_map.csv", encoding="utf-8-sig")

    dates = pd.to_datetime(df_load["date"]).dt.date.tolist()
    expected = pd.date_range("2025-01-01", "2025-12-31", freq="D").date.tolist()
    check("日期为 2025 完整 365 天且无重复", dates == expected, f"n={len(dates)}", "365 天连续")

    load = wide_to_matrix(df_load)      # (144,365) kWh
    pv = wide_to_matrix(df_pv)          # (144,365) kWh
    price = wide_to_matrix(df_price)    # (144,365) 元/kWh
    check("矩阵形状 (144,365)", load.shape == pv.shape == price.shape == (T, D),
          f"load={load.shape}, pv={pv.shape}, price={price.shape}", "(144,365)")
    check("无缺失/非有限值", all(np.isfinite(a).all() for a in (load, pv, price)), "全部有限", "全部有限")
    check("负荷、光伏非负", (load >= 0).all() and (pv >= 0).all(),
          f"min load={load.min():.4f}, min pv={pv.min():.4f}", "≥ 0")
    check("电价严格为正（附件4）", (price > 0).all(),
          f"min={price.min():.4f}, max={price.max():.4f}", "> 0")
    check("time_map 为 1..144 完整映射",
          time_map.shape[0] == T and np.array_equal(time_map["time_idx"].to_numpy(int), np.arange(1, T + 1)),
          f"n={time_map.shape[0]}", "144 行且序号连续")

    # ---------------- 3. 双路径一致性（数据真实性核验）----------------
    q2 = load_pickle_compat(Q2_DIR / "q2_dataset.pkl")
    q2f = load_pickle_compat(Q2_DIR / "forecasts.pkl")
    check("Q2 数据集日期轴一致", [str(x) for x in q2["date_str"]] == [d.strftime("%Y-%m-%d") for d in dates],
          f"n={len(q2['date_str'])}", "与 parquet 同日序")
    d_load = float(np.max(np.abs(q2["load"] - load)))
    d_pv = float(np.max(np.abs(q2["pv"] - pv)))
    check("负荷双路径重建一致（parquet vs Q2）", d_load < 1e-9, f"max|Δ|={d_load:.3e}", "≤ 1e-9 kWh（浮点级一致）")
    check("光伏双路径重建一致（parquet vs Q2）", d_pv < 1e-9, f"max|Δ|={d_pv:.3e}", "≤ 1e-9 kWh（浮点级一致）")

    # 附件1 = 全年逐时段均值曲线的实测事实（用于论文数据说明，不是假设）
    p1_price = df_p1["price"].to_numpy(float)
    p1_load = df_p1["load_kwh"].to_numpy(float)
    m1 = float(np.max(np.abs(p1_price - price.mean(axis=1))))
    m2 = float(np.max(np.abs(p1_load - load.mean(axis=1))))
    check("附件1 电价 = 附件4 全年逐时段均值（4 位小数精度）", m1 < 2e-4, f"max|Δ|={m1:.3e}", "< 2e-4")
    check("附件1 负载 = 附件2 全年逐时段均值", m2 < 1e-3, f"max|Δ|={m2:.3e}", "< 1e-3 kWh")

    # ---------------- 4. 载荷/光伏预测（沿用 Q2，口径不变）----------------
    Lhat = np.asarray(q2f["Lhat"], dtype=float)
    Ghat = np.asarray(q2f["Ghat"], dtype=float)
    check("Q2 负荷/光伏预测形状", Lhat.shape == Ghat.shape == (T, D),
          f"Lhat={Lhat.shape}, Ghat={Ghat.shape}", "(144,365)")
    Lhat = np.maximum(Lhat, 0.0)
    Ghat = np.maximum(Ghat, 0.0)

    # ---------------- 5. 附件3 issue=0 官方光伏预报（linear_endpoint）----------------
    fc0 = df_fcst[df_fcst["issue_hour"] == 0].sort_values("date")
    check("附件3 issue=0 恰 365 行", len(fc0) == D, f"n={len(fc0)}", "365")
    check("附件3 issue=0 日期与日序一致",
          pd.to_datetime(fc0["date"]).dt.date.tolist() == dates, "同序", "同序")
    Ghat_official = np.zeros((T, D))
    hourly_all = fc0[FH_COLS].to_numpy(dtype=float)
    check("附件3 预报值非负且有限",
          np.isfinite(hourly_all).all() and (hourly_all >= 0).all(),
          f"min={hourly_all.min():.4f}, max={hourly_all.max():.4f}", "≥0 且有限")
    for d in range(D):
        Ghat_official[:, d] = pv_forecast_linear_endpoint(hourly_all[d], 0, None)

    rep = np.array([(d >= pd.Timestamp(REPORT_START).date()) and (d <= pd.Timestamp(REPORT_END).date()) for d in dates])
    wape_off = float(np.sum(np.abs(Ghat_official[:, rep] - pv[:, rep])) / np.sum(np.abs(pv[:, rep])))
    wape_q2 = float(np.sum(np.abs(Ghat[:, rep] - pv[:, rep])) / np.sum(np.abs(pv[:, rep])))
    check("官方预报 issue=0 的 WAPE 与 Q3 审计一致（≈0.083）",
          abs(wape_off - 0.08301939106151637) < 0.01, f"WAPE={wape_off:.4f}", "≈0.0830（±0.01）")

    # ---------------- 6. 报告期 / 标定期切分 ----------------
    calib_idx = np.where([(d >= pd.Timestamp(CALIB_START).date()) and (d <= pd.Timestamp(CALIB_END).date())
                          for d in dates])[0]
    report_idx = np.where(rep)[0]
    check("标定期 = 2025-01-15~01-31 共 17 天", len(calib_idx) == 17,
          f"n={len(calib_idx)}", "17")
    check("报告期 = 2025-02-01~12-31 共 334 天", len(report_idx) == 334,
          f"n={len(report_idx)}", "334")
    check("报告期首日 = 2025-02-01", str(dates[report_idx[0]]) == REPORT_START,
          str(dates[report_idx[0]]), REPORT_START)
    check("报告期末日 = 2025-12-31", str(dates[report_idx[-1]]) == REPORT_END,
          str(dates[report_idx[-1]]), REPORT_END)

    # ---------------- 7. 打包 ----------------
    dataset = {
        "dates": dates,
        "date_str": np.asarray([d.strftime("%Y-%m-%d") for d in dates], dtype=object),
        # 实际观测（结算与评价用）
        "load": load, "pv": pv, "price": price,
        # Q2 口径的确定电价（附件1，仅用于 Q2 基准复现与对比）
        "price_q2_fixed": p1_price,
        # 预测（决策用）：Lhat/Ghat 沿用 Q2；Ghat_official 为附件3 issue=0
        "Lhat": Lhat, "Ghat": Ghat, "Ghat_official": Ghat_official,
        "calib_idx": calib_idx, "report_idx": report_idx,
        "constants": {"T": T, "D": D, "DELTA_T": DELTA_T, "ETA_C": ETA_C, "ETA_R": ETA_R,
                      "SOC_MIN": SOC_MIN, "SOC_MAX": SOC_MAX, "SOC0": SOC0,
                      "CHARGE_CAP": CHARGE_CAP},
        "kappa2_base": float(q2["kappa2_base"]),
        "kappa2_stats": q2.get("kappa2_stats", {}),
        "time_mapping": q2["time_mapping"],
        "provenance": {
            "generated_by": "03_q4_dataset.py",
            "parquet": {n: str(TRANS / n) for n in
                        ["df_load.parquet", "df_pv.parquet", "df_price.parquet", "df_fcst.parquet", "df_p1.parquet"]},
            "q2_forecast": str(Q2_DIR / "forecasts.pkl"),
            "attachment_sha256": hashes,
            "unit_rule": "负荷/光伏 原始 kW × (1/6) h = kWh；电价 元/kWh 保持",
            "conversion_rule_official_pv": "附件3 小时 kW 经 linear_endpoint 插值到 10min，再 ×1/6 得 kWh",
        },
    }
    with open(OUT_DIR / "q4_dataset.pkl", "wb") as fh:
        pickle.dump(dataset, fh, protocol=pickle.HIGHEST_PROTOCOL)

    # ---------------- 8. 落盘核验报告 ----------------
    extra = [
        {"检查项": "附件4 电价统计", "是否通过": True,
         "实测值": f"min={price.min():.4f} max={price.max():.4f} mean={price.mean():.4f} std={price.std():.4f}",
         "要求": "记录备查"},
        {"检查项": "日内峰谷差（全年范围）", "是否通过": True,
         "实测值": f"min={np.min(price.max(0) - price.min(0)):.4f} max={np.max(price.max(0) - price.min(0)):.4f} 元/kWh",
         "要求": "记录备查"},
        {"检查项": "官方光伏预报 WAPE（报告期, issue=0）", "是否通过": True,
         "实测值": f"{wape_off:.6f}", "要求": "与 Q3 审计 0.083019 一致"},
        {"检查项": "Q2 光伏预测 WAPE（报告期）", "是否通过": True,
         "实测值": f"{wape_q2:.6f}", "要求": "记录备查（对照口径）"},
    ]
    audit = pd.DataFrame(CHECKS + extra)
    audit.to_csv(TABLES / "q4_data_audit.csv", index=False, encoding="utf-8-sig")
    with open(TABLES / "q4_data_audit.md", "w", encoding="utf-8") as fh:
        fh.write("# 问题 4-2 数据集构建核验\n\n")
        fh.write(f"- 产出：`Data_processing/q4_dataset.pkl`\n- 脚本：`Data_processing/03_q4_dataset.py`\n")
        fh.write(f"- 报告期：{REPORT_START} ~ {REPORT_END}（{len(report_idx)} 天）；")
        fh.write(f"标定期：{CALIB_START} ~ {CALIB_END}（{len(calib_idx)} 天）\n\n")
        fh.write("## 官方附件 SHA-256\n\n")
        for k, v in hashes.items():
            fh.write(f"- `{k}`：`{v}`\n")
        fh.write("\n## 逐项核验\n\n")
        fh.write("| 检查项 | 结果 | 实测值 | 要求 |\n| --- | --- | --- | --- |\n")
        for r in audit.to_dict("records"):
            fh.write(f"| {r['检查项']} | {'PASS' if r['是否通过'] else 'FAIL'} | {r['实测值']} | {r['要求']} |\n")

    print(f"[03] 数据集已生成: {OUT_DIR / 'q4_dataset.pkl'}")
    print(f"     load={load.shape} pv={pv.shape} price={price.shape} (kWh/时段, 元/kWh)")
    print(f"     报告期 {len(report_idx)} 天，标定期 {len(calib_idx)} 天")
    print(f"     双路径一致性 max|Δload|={d_load:.3e}, max|Δpv|={d_pv:.3e}")
    print(f"     官方光伏预报 WAPE={wape_off:.6f}；Q2 光伏预测 WAPE={wape_q2:.6f}")
    print(f"     核验报告: {TABLES / 'q4_data_audit.csv'}（{len(audit)} 项全部 PASS）")
    return dataset


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:  # noqa: BLE001
        print("=" * 70)
        traceback.print_exc()
        print(f"[03] 构建失败：{exc}")
        sys.exit(1)
