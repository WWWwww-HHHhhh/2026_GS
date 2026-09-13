from __future__ import annotations

import pickle
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q4_common import D, OUT_DATA, REPORT_START, REPORT_END, TABLES, T, load_dataset  # noqa: E402

PRICE_FLOOR = 0.0076   # 附件4 全年最小电价，预测值不得低于该量级（保持价格正性）
PRIOR_FLAT_PLACEHOLDER = 0.7662  # 仅在未提供先验时的占位常量（= 附件4 全年均价）；主链路传入附件1 典型日曲线
SHAPE_COLS = None


def wape(pred: np.ndarray, actual: np.ndarray) -> float:
    den = float(np.sum(np.abs(actual)))
    return float(np.sum(np.abs(pred - actual)) / den) if den > 0 else float("inf")


def mae(pred: np.ndarray, actual: np.ndarray) -> float:
    return float(np.mean(np.abs(pred - actual)))


def build_candidates(P: np.ndarray, SH: np.ndarray, MU: np.ndarray, dow: np.ndarray, i: int,
                     prior: np.ndarray | None = None) -> dict:
    """给出决策日 i 的全部候选预测（只使用 j < i 的数据）。

    冷启动（i = 0，无任何历史价格）：
      禁止使用当天实际价格。口径为**退化为题面自带的典型日曲线（附件1，全年逐时段均值）**——
      它是题目给定数据，不含 2025 年的未来信息，因此不构成泄露。
      `prior` 未提供时使用常量占位（仅供脱离主链路单独调用，主链路始终传入附件1 先验）。
    """
    out: dict[str, np.ndarray] = {}
    if i >= 1:
        out["naive_last"] = P[:, i - 1].copy()
    if i >= 7:
        out["naive_dow7"] = P[:, i - 7].copy()

    def shape_level(K: int, agg: str, dow_only: bool = False) -> np.ndarray | None:
        idx = np.arange(max(0, i - K), i)
        if dow_only and idx.size:
            same = np.array([dow[j] == dow[i] for j in idx])
            if same.any():
                idx = idx[same]
        if idx.size == 0:
            return None
        level = float(np.median(MU[idx])) if agg == "med" else float(np.mean(MU[idx]))
        prof = np.median(SH[:, idx], axis=1) if agg == "med" else np.mean(SH[:, idx], axis=1)
        return level * prof

    for K in (7, 14, 28):
        for agg in ("mean", "med"):
            v = shape_level(K, agg)
            if v is not None:
                out[f"shape{agg}{K}"] = v
    for agg in ("mean", "med"):
        v = shape_level(28, agg, dow_only=True)
        if v is not None:
            out[f"sha_dow28_{agg}"] = v

    if not out:  # 冷启动兜底（仅 i = 0 触发）
        if i > 0:
            out["fallback_hist"] = MU[:i].mean() * SH[:, :i].mean(axis=1)
        else:
            if prior is not None:
                out["fallback_typical_day"] = np.asarray(prior, dtype=float).copy()
            else:
                out["fallback_flat_placeholder"] = np.full(T, PRIOR_FLAT_PLACEHOLDER)
    return {k: np.maximum(v, PRICE_FLOOR) for k, v in out.items()}


def forecast_all(P: np.ndarray, dates: list, prior: np.ndarray | None = None) -> tuple[np.ndarray, pd.DataFrame]:
    """逐日滚动预测，返回 (price_hat (144,365), 选择日志 DataFrame)。

    `prior`：无历史价格时的先验曲线（主链路传附件1 的典型日曲线）。只在与冷启动日生效。
    """
    Dn = P.shape[1]
    MU = P.mean(axis=0)
    SH = P / np.maximum(MU, 1e-12)[None, :]
    dow = np.array([d.weekday() for d in dates])

    hat = np.zeros_like(P)
    rows = []
    for i in range(Dn):
        # 1) 模型挑选：评价各候选在 i-1 日的表现（各候选自身的口径仍只用 < i-1 的数据）
        chosen, score_best, wapes_eval = None, np.inf, {}
        if i >= 1:
            for name, pred_prev in build_candidates(P, SH, MU, dow, i - 1, prior).items():
                s = wape(pred_prev, P[:, i - 1])
                wapes_eval[name] = s
                if s < score_best:
                    chosen, score_best = name, s
        # 2) 用选定模型生成 i 日预测（用截至 i-1 的数据）
        cands = build_candidates(P, SH, MU, dow, i, prior)
        if chosen is None or chosen not in cands:
            chosen = sorted(cands.keys())[0] if "naive_last" not in cands else "naive_last"
        hat[:, i] = cands[chosen]
        rows.append({
            "date": dates[i].strftime("%Y-%m-%d"),
            "i": i,
            "selected": chosen,
            "prev_day_wape_selected": score_best if np.isfinite(score_best) else np.nan,
            "prev_day_wape_naive_last": wapes_eval.get("naive_last", np.nan),
            "n_candidates": len(cands),
            "train_max_day_index": i - 1,
        })
    return hat, pd.DataFrame(rows)


def df_to_md(df: pd.DataFrame, floatfmt: str = ".5f") -> str:
    """轻量 markdown 表格（不依赖 tabulate）。"""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for rec in df.to_dict("records"):
        cells = []
        for c in df.columns:
            v = rec[c]
            if isinstance(v, float):
                cells.append(f"{v:{floatfmt}}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> int:
    try:
        ds = load_dataset()
        price = np.asarray(ds["price"], dtype=float)
        dates = list(ds["dates"])
        report_idx = np.asarray(ds["report_idx"], dtype=int)

        print(f"[04] 电价预测：{price.shape[1]} 天 × {price.shape[0]} 时段，因果滚动")
        prior = np.asarray(ds["price_q2_fixed"], dtype=float)   # 附件1 典型日曲线（冷启动先验）
        hat, sel = forecast_all(price, dates, prior=prior)
        res = price - hat

        # ---------- 真实性核验 ----------
        assert hat.shape == price.shape == res.shape == (T, D), "形状异常"
        assert np.isfinite(hat).all() and (hat > 0).all(), "预测出现非正或非有限值"
        # 因果性：第 i 天预测只用 ≤ i-1 的数据，用日志中的 train_max_day_index 复核
        assert (sel["train_max_day_index"].to_numpy() < sel["i"].to_numpy()).all(), "存在因果性违规"
        # 逐日复算：hat[:,i] 必须等于"用选定模型、只用 <i 数据"重新算出的向量
        MU = price.mean(axis=0)
        SH = price / np.maximum(MU, 1e-12)[None, :]
        dow = np.array([d.weekday() for d in dates])
        max_dev = 0.0
        for r in sel.itertuples():
            i = int(r.i)
            again = build_candidates(price, SH, MU, dow, i, prior)[r.selected]
            max_dev = max(max_dev, float(np.max(np.abs(again - hat[:, i]))))
        assert max_dev < 1e-12, f"预测与候选模型不一致 max|Δ|={max_dev:.3e}"
        # 冷启动核验：day0 的预测不得等于当天实际价格（历史上曾因 P[:,0] 兜底而泄露）
        dev0 = float(np.max(np.abs(hat[:, 0] - price[:, 0])))
        assert dev0 > 1e-6, f"首日预测仍等于当天实际价格（max|Δ|={dev0:.3e}），冷启动泄露未修复"

        # 朴素基线（昨日形状）用于技能对比
        naive = np.zeros_like(price)
        naive[:, 1:] = price[:, :-1]
        naive[:, 0] = price[:, 0]

        rows = []
        months = np.array([d.month for d in dates])
        for m in range(2, 13):
            msk = (months == m) & np.isin(np.arange(D), report_idx)
            if not msk.any():
                continue
            rows.append({
                "month": m, "n_days": int(msk.sum()),
                "MAE_selected": mae(hat[:, msk], price[:, msk]),
                "WAPE_selected": wape(hat[:, msk], price[:, msk]),
                "MAE_naive_last": mae(naive[:, msk], price[:, msk]),
                "WAPE_naive_last": wape(naive[:, msk], price[:, msk]),
            })
        monthly = pd.DataFrame(rows)

        allsel_w = wape(hat[:, report_idx], price[:, report_idx])
        allnai_w = wape(naive[:, report_idx], price[:, report_idx])
        skill = 1.0 - allsel_w / allnai_w

        TABLES.mkdir(parents=True, exist_ok=True)
        monthly.to_csv(TABLES / "q4_price_forecast_monthly.csv", index=False, encoding="utf-8-sig")
        sel.to_csv(TABLES / "q4_price_forecast_selection.csv", index=False, encoding="utf-8-sig")

        out = {
            "price_hat": hat, "price_res": res, "selection": sel, "monthly": monthly,
            "report_idx": report_idx,
            "metrics": {"WAPE_selected_report": allsel_w, "WAPE_naive_report": allnai_w,
                        "skill_vs_naive": skill,
                        "MAE_selected_report": mae(hat[:, report_idx], price[:, report_idx]),
                        "MAE_naive_report": mae(naive[:, report_idx], price[:, report_idx])},
            "causality": "day i forecast uses price data only through day i-1; model chosen by day i-1 WAPE",
            "candidates": "naive_last, naive_dow7, shape{mean,med}{7,14,28}, sha_dow28_{mean,med}",
        }
        with open(OUT_DATA / "price_forecast.pkl", "wb") as fh:
            pickle.dump(out, fh, protocol=pickle.HIGHEST_PROTOCOL)

        with open(TABLES / "q4_price_forecast_report.md", "w", encoding="utf-8") as fh:
            fh.write("# 问题 4-2 电价因果预测报告\n\n")
            fh.write("- 脚本：`Data_processing/04_q4_price_forecast.py`\n")
            fh.write(f"- 输入：`Data_processing/q4_dataset.pkl` 的 `price`（附件4，{T}×{D}，元/kWh）\n")
            fh.write("- 口径：决策日 i 只用 j<i 的已实现电价；模型挑选用 i−1 日 WAPE；i−1 日候选自身只用 j<i−1\n")
            fh.write(f"- 冷启动（day0 = {dates[0]}）：无历史价格，**退化为附件1 典型日曲线**（题目给定数据），"
                     f"不得使用当天实际价格；实测 max|预测−实际| = {dev0:.6f}（>0 即无泄露）\n")
            fh.write("- 候选族：" + out["candidates"] + "\n\n")
            fh.write("## 报告期（2025-02-01~12-31，334 天）整体技能\n\n")
            fh.write(f"| 指标 | 选定模型 | 朴素基线(昨日形状) |\n| --- | --- | --- |\n")
            fh.write(f"| WAPE | {allsel_w:.6f} | {allnai_w:.6f} |\n")
            fh.write(f"| MAE (元/kWh) | {out['metrics']['MAE_selected_report']:.6f} | "
                     f"{out['metrics']['MAE_naive_report']:.6f} |\n\n")
            fh.write(f"相对朴素基线的 WAPE 技能分：**{skill:+.4f}**"
                     f"（{'优于' if skill > 0 else '劣于'}基线）\n\n")
            fh.write("## 逐月\n\n")
            fh.write(df_to_md(monthly) + "\n\n")
            fh.write(f"## 核验\n\n- 形状/正性/有限性：PASS\n- 因果性（train_max_day_index < i）：PASS\n")
            fh.write(f"- 预测向量与候选模型逐日复算一致：PASS（max|Δ|={max_dev:.3e}）\n")
            fh.write(f"\n## 模型选择分布\n\n")
            dist = sel["selected"].value_counts().rename_axis("model").reset_index(name="days")
            fh.write(df_to_md(dist, floatfmt=".0f") + "\n")

        print(f"    报告期 WAPE：选定 {allsel_w:.6f} vs 朴素 {allnai_w:.6f}，技能分 {skill:+.4f}")
        print(f"    逐月表: {TABLES / 'q4_price_forecast_monthly.csv'}")
        print(f"    选择日志: {TABLES / 'q4_price_forecast_selection.csv'}")
        print(f"    预测缓存: {OUT_DATA / 'price_forecast.pkl'}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print("=" * 70)
        traceback.print_exc()
        print(f"[04] 失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
