# -*- coding: utf-8 -*-
"""q4_2_experiments.py —— 问题 4-2 的反事实实验矩阵（支撑论文的全部对比数字）。

目的：把"波动电价建模到底值不值"这件事用可复核的实验回答，而不是靠叙述。
每一行实验都从**同一状态**出发（2025-02-01 00:00 的 SOC），用**同一套结算规则**（R1 实际波动价），
只在被研究的那一个维度上变化。

实验维度：
  main        主模型（选中配置）
  beta_*      风险厌恶系数扫描（β 从 0 到 0.5）
  M_*         场景数扫描（10/20/30）
  pscale_*    价格场景不确定度注入（0.8×/1.2×）
  B0          完美预见下界（逐日知道当天实际价格/负荷/光伏）
  B1          Q2 固定价策略（用附件1 电价做日前优化，按实际波动价结算）
  B2          实时缺口购电（不动储能，无日前优化）
  B3          典型日(Q1)策略（把平均日最优计划每天原样执行）
  B4          全量提取口径（y ≡ x，题目另一种读法，用于稳健性）

每个实验记录：总费用、日均费用、日费用 CVaR_90%（最差 10% 日均值）、日费用最大值、
紧急购电率、未提取比例、弃光率、期末 SOC。

运行：python q4_2_experiments.py            # 全部实验（约 30-40 分钟）
      python q4_2_experiments.py --quick    # 只跑 B0/B2/B3 与 main（约 2 分钟）
"""
from __future__ import annotations

import argparse
import pickle
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

WYH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WYH / "Data_processing"))
sys.path.insert(0, str(WYH / "Model_Establishment+Solution"))
from q4_common import D, OUT_DATA, REPO, TABLES, T, load_dataset  # noqa: E402
from q4_core import solve_day  # noqa: E402
from q4_settlement import settle_day  # noqa: E402

SOC0 = 6000.0


def _load():
    ds = load_dataset()
    res = pickle.load(open(OUT_DATA / "q4_2_rolling_results.pkl", "rb"))
    return ds, res


def _scen(M: int) -> dict:
    return pickle.load(open(OUT_DATA / f"scenarios_M{M}.pkl", "rb"))


def run_report(ds, res, scen, *, beta, kappa2, M, price_mode="scenario", pscale=1.0,
               full_extraction=False, label="", start_soc=None, verbose=False) -> dict:
    """跑整个报告期，返回费用与风险指标。所有实验共用同一结算规则与同一起点。"""
    logs = res["report_logs"]
    s0 = float(logs[0]["s0"]) if start_soc is None else float(start_soc)
    costs, emg_kwh, load_kwh, pv_kwh, unext, curt, spill = [], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    x_total = 0.0
    t0 = time.time()
    for n, l in enumerate(logs):
        i = l["day_index"]
        if price_mode == "scenario":
            P = np.asarray(scen["P_all"][i], dtype=float)
            if pscale != 1.0:
                cen = P.mean(axis=0)[None, :]
                P = np.maximum(cen + pscale * (P - cen), 0.0076)
        elif price_mode == "fixed":
            P = np.tile(ds["price_q2_fixed"][None, :], (M, 1))
        else:
            raise ValueError(price_mode)
        kw = {"alpha": 0.90, "beta": beta, "kappa2": kappa2, "full_extraction": full_extraction}
        if i == D - 1:
            kw.update({"hard_terminal": True, "s_ref": SOC0})
        plan = solve_day(P, scen["L_all"][i], scen["G_all"][i], s0, kw)
        st = settle_day(ds["price"][:, i], plan["x"], plan["c"], plan["r"],
                        ds["load"][:, i], ds["pv"][:, i], s0, full_extraction=full_extraction)
        s0 = float(st["s_actual"][-1])
        costs.append(st["cost_total"])
        x_total += float(np.sum(plan["x"]))
        emg_kwh += float(np.sum(st["e"])); load_kwh += float(np.sum(ds["load"][:, i]))
        pv_kwh += float(np.sum(ds["pv"][:, i])); curt += float(np.sum(st["w"]))
        unext += float(np.sum(plan["x"] - st["y"])); spill += float(np.sum(st["spill"]))
        if verbose and n and n % 80 == 0:
            print(f"      {label} {l['date']} ({n}/334)", flush=True)
    c = np.asarray(costs)
    k = max(1, int(round(0.10 * len(c))))
    worst = np.sort(c)[-k:]
    return {
        "实验": label, "总费用(元)": float(c.sum()), "日均费用(元)": float(c.mean()),
        "日费用标准差(元)": float(c.std(ddof=1)),
        "日费用CVaR90(元)": float(worst.mean()), "日费用最大值(元)": float(c.max()),
        "紧急购电率(%)": emg_kwh / load_kwh * 100, "未提取计划比例(%)": unext / x_total * 100,
        "弃光率(%)": curt / pv_kwh * 100, "紧急购电量(kWh)": emg_kwh,
        "期末SOC(kWh)": s0, "历时(s)": time.time() - t0,
    }


def run_b0(ds, res) -> dict:
    logs = res["report_logs"]
    s0 = float(logs[0]["s0"]); costs = []
    t0 = time.time()
    for l in logs:
        i = l["day_index"]
        kw = {"kappa2": float(res["params"]["kappa2"]), "beta": 0.0, "alpha": 0.90}
        if i == D - 1:
            kw.update({"hard_terminal": True, "s_ref": SOC0})
        plan = solve_day(ds["price"][:, i][None, :], ds["load"][:, i][None, :], ds["pv"][:, i][None, :], s0, kw)
        st = settle_day(ds["price"][:, i], plan["x"], plan["c"], plan["r"],
                        ds["load"][:, i], ds["pv"][:, i], s0)
        s0 = float(st["s_actual"][-1]); costs.append(st["cost_total"])
    c = np.asarray(costs); k = max(1, int(round(0.10 * len(c))))
    return {"实验": "B0 完美预见下界（下界）", "总费用(元)": float(c.sum()), "日均费用(元)": float(c.mean()),
            "日费用标准差(元)": float(c.std(ddof=1)), "日费用CVaR90(元)": float(np.sort(c)[-k:].mean()),
            "日费用最大值(元)": float(c.max()), "紧急购电率(%)": float("nan"),
            "未提取计划比例(%)": float("nan"), "弃光率(%)": float("nan"),
            "紧急购电量(kWh)": float("nan"), "期末SOC(kWh)": s0, "历时(s)": time.time() - t0}


def run_b2(ds, res) -> dict:
    logs = res["report_logs"]; costs = []; emg = 0.0; load = 0.0
    for l in logs:
        i = l["day_index"]
        price = ds["price"][:, i]; L = ds["load"][:, i]; G = ds["pv"][:, i]
        gap = np.maximum(L - G, 0.0)
        costs.append(float(np.sum(price * gap)))
        load += float(np.sum(L))
    c = np.asarray(costs); k = max(1, int(round(0.10 * len(c))))
    return {"实验": "B2 实时缺口购电（不动储能）", "总费用(元)": float(c.sum()), "日均费用(元)": float(c.mean()),
            "日费用标准差(元)": float(c.std(ddof=1)), "日费用CVaR90(元)": float(np.sort(c)[-k:].mean()),
            "日费用最大值(元)": float(c.max()), "紧急购电率(%)": 0.0,
            "未提取计划比例(%)": 0.0, "弃光率(%)": float("nan"), "紧急购电量(kWh)": 0.0,
            "期末SOC(kWh)": SOC0, "历时(s)": 0.0}


def run_b3(ds, res) -> dict:
    r1 = REPO / "All_Code" / "Q1" / "Results" / "Tables" / "result1.xlsx"
    if not r1.exists():
        return {"实验": "B3 典型日(Q1)策略", "总费用(元)": float("nan")}
    plan = pd.read_excel(r1, sheet_name="计划购电量")
    stor = pd.read_excel(r1, sheet_name="充放电量")
    x = pd.to_numeric(plan.iloc[:, 1], errors="coerce").to_numpy(float)
    c = np.zeros(T); r = np.zeros(T)
    for k, (a, b) in enumerate([(0, 24), (24, 48), (48, 72), (72, 96), (96, 120), (120, 144)]):
        c[a:b] = float(pd.to_numeric(stor.iloc[k, 1], errors="coerce") or 0.0) / (b - a)
        r[a:b] = float(pd.to_numeric(stor.iloc[k, 2], errors="coerce") or 0.0) / (b - a)
    costs = []
    for l in res["report_logs"]:
        i = l["day_index"]
        st = settle_day(ds["price"][:, i], x, c, r, ds["load"][:, i], ds["pv"][:, i], SOC0)
        costs.append(st["cost_total"])
    cc = np.asarray(costs); k = max(1, int(round(0.10 * len(cc))))
    return {"实验": "B3 典型日(Q1)策略", "总费用(元)": float(cc.sum()), "日均费用(元)": float(cc.mean()),
            "日费用标准差(元)": float(cc.std(ddof=1)), "日费用CVaR90(元)": float(np.sort(cc)[-k:].mean()),
            "日费用最大值(元)": float(cc.max()), "紧急购电率(%)": float("nan"),
            "未提取计划比例(%)": float("nan"), "弃光率(%)": float("nan"),
            "紧急购电量(kWh)": float("nan"), "期末SOC(kWh)": SOC0, "历时(s)": 0.0}


def diagnostic_full_extraction(res) -> dict:
    """「全量提取」口径（y≡x）的可行性诊断。

    该口径要求计划量必须被全额提取。但在因果执行下，0:00 的计划是**按预测**制定的，
    当日实际负荷/光伏一实现，某些时段的计划量必然超过当时的实际需要（剩余需求），
    此时 y≡x 会要求提取并不需要的电量。Q2 的 `settlement.py` 已把这种情形判为不可行；
    本诊断把它量化出来，说明「计划量决定付费、实际提取 ≤ 计划量」不是取巧，
    而是题目结构下的**必要**口径。
    """
    logs = res["report_logs"]
    bad_days = [l["date"] for l in logs if l["unextracted_kwh"] > 1e-6]
    unext = float(sum(l["unextracted_kwh"] for l in logs))
    plan = float(sum(l["plan_total_kwh"] for l in logs))
    return {
        "实验": "B4 全量提取口径（y≡x）—— 不可行诊断",
        "总费用(元)": float("nan"), "日均费用(元)": float("nan"), "日费用标准差(元)": float("nan"),
        "日费用CVaR90(元)": float("nan"), "日费用最大值(元)": float("nan"),
        "紧急购电率(%)": float("nan"), "未提取计划比例(%)": unext / plan * 100,
        "弃光率(%)": float("nan"), "紧急购电量(kWh)": float("nan"),
        "期末SOC(kWh)": float("nan"), "历时(s)": 0.0,
        "备注": f"{len(bad_days)}/334 天出现计划量超过实际需要，累计未提取 {unext:,.1f} kWh"
                f"（占计划量 {unext / plan * 100:.2f}%），故 y≡x 在因果执行下不可行",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    started = time.time()
    try:
        ds, res = _load()
        p = res["params"]
        M0 = int(p["M"]); beta0 = float(p["beta"]); kappa0 = float(p["kappa2"])
        print(f"[实验] 主模型配置 M={M0} β={beta0} κ={kappa0:.4f}")
        scen = _scen(M0)
        rows = []

        # 断点续跑：已完成的实验不重算
        csv_path = TABLES / "q4_2_experiments.csv"
        done = {}
        if csv_path.exists():
            old = pd.read_csv(csv_path, encoding="utf-8-sig")
            done = {r["实验"]: r.to_dict() for _, r in old.iterrows()}
            print(f"[实验] 发现已有结果 {len(done)} 条，将跳过重复项")

        def add(label: str, thunk) -> None:
            if label in done:
                rows.append(done[label])
                print(f"  [跳过] {label}（已有 {done[label].get('总费用(元)')}）", flush=True)
                return
            r = thunk()
            rows.append(r)
            print(f"    {label}: {r.get('总费用(元)')}", flush=True)

        add("主模型 Q4-2（选中配置）", lambda: run_report(
            ds, res, scen, beta=beta0, kappa2=kappa0, M=M0, label="主模型 Q4-2（选中配置）"))
        add("B0 完美预见下界（下界）", lambda: run_b0(ds, res))
        add("B2 实时缺口购电（不动储能）", lambda: run_b2(ds, res))
        add("B3 典型日(Q1)策略", lambda: run_b3(ds, res))
        add("B4 全量提取口径（y≡x）—— 不可行诊断", lambda: diagnostic_full_extraction(res))

        if not args.quick:
            add("B1 Q2固定价策略", lambda: run_report(
                ds, res, scen, beta=beta0, kappa2=kappa0, M=M0, price_mode="fixed",
                label="B1 Q2固定价策略", verbose=True))
            for b in (0.0, 0.05, 0.10, 0.25, 0.50):
                lab = f"β 扫描 β={b}（风险中性→保守）"
                add(lab, (lambda bb, ll: (lambda: run_report(
                    ds, res, scen, beta=bb, kappa2=kappa0, M=M0, label=ll, verbose=True)))(b, lab))
            for Mm in (10, 20, 30):
                lab = f"场景数扫描 M={Mm}"
                add(lab, (lambda m_, ll: (lambda: run_report(
                    ds, res, _scen(m_), beta=beta0, kappa2=kappa0, M=m_, label=ll, verbose=True)))(Mm, lab))
            for sc_ in (0.7, 1.3):
                lab = f"价格不确定度注入 ×{sc_}"
                add(lab, (lambda s_, ll: (lambda: run_report(
                    ds, res, scen, beta=beta0, kappa2=kappa0, M=M0, pscale=s_, label=ll,
                    verbose=True)))(sc_, lab))

        df = pd.DataFrame(rows)
        TABLES.mkdir(parents=True, exist_ok=True)
        df.to_csv(TABLES / "q4_2_experiments.csv", index=False, encoding="utf-8-sig")

        main_row = df[df["实验"].str.startswith("主模型")].iloc[0]
        b0 = df[df["实验"].str.startswith("B0")].iloc[0]
        lines = ["# 问题 4-2 反事实实验矩阵", "",
                 f"- 主模型配置：M={M0}，β={beta0}，κ={kappa0:.4f}，α=0.90",
                 f"- 报告期：2025-02-01 ~ 2025-12-31（334 天）；全部实验同起点、同结算规则（R1 实际波动价）",
                 f"- 脚本：`Model_Establishment+Solution/q4_2_experiments.py`", "",
                 "## 汇总表", "",
                 "| 实验 | 总费用(元) | 日均费用(元) | 日费用 CVaR90(元) | 日费用最大(元) | 紧急购电率(%) | 未提取(%) | 弃光(%) | 期末SOC |",
                 "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for _, r in df.iterrows():
            def f(v, fmt="{:.2f}"):
                return "—" if pd.isna(v) else fmt.format(v)
            lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                r["实验"], f(r["总费用(元)"], "{:,.0f}"), f(r["日均费用(元)"], "{:,.0f}"),
                f(r["日费用CVaR90(元)"], "{:,.0f}"), f(r["日费用最大值(元)"], "{:,.0f}"),
                f(r["紧急购电率(%)"]), f(r["未提取计划比例(%)"]), f(r["弃光率(%)"]),
                f(r["期末SOC(kWh)"], "{:,.1f}")))
        notes = [(r["实验"], r["备注"]) for _, r in df.iterrows()
                 if isinstance(r.get("备注"), str) and r["备注"]]
        if notes:
            lines += ["", "## 不可行 / 特别说明", ""]
            for lab, nt in notes:
                lines.append(f"- **{lab}**：{nt}")
        lines += ["", "## 关键读法", "",
                  f"1. **最优性 gap**：主模型 {main_row['总费用(元)']:,.0f} 元 vs 完美预见下界 "
                  f"{b0['总费用(元)']:,.0f} 元，gap = "
                  f"{(main_row['总费用(元)'] - b0['总费用(元)']) / b0['总费用(元)'] * 100:.2f}%。"
                  "该 gap 来自「0:00 电价未知 + 负荷/光伏预测误差」的信息缺口，是不可避免的信息成本。",
                  "2. **波动电价建模的价值**：与 B1（Q2 固定价策略）比较时必须同时看总费用与日费用 CVaR90。"
                  "若主模型总费用略高但 CVaR90 更低，则其价值体现在风险控制而非均值；若两者接近，"
                  "则说明该题结构下日内价格形状的可预测性很高，真正不可对冲的是日级价格水平"
                  "（R1 口径下计划量按交易时刻实际价成比例计费）。",
                  "3. **β 的方向**：β 增大 → 紧急购电率下降、日费用 CVaR90 下降、总费用上升，"
                  "构成可交易的风险—成本前沿。",
                  "4. **场景数 M**：反映场景抽样误差对决策质量的影响，用于论证 M 取值的合理性。",
                  "5. **价格不确定度注入**：检验模型对价格分布误设的敏感性；"
                  "若注入后费用变化有限，说明决策对价格分布形状不敏感。", ""]
        (TABLES / "q4_2_experiments_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(df.to_string(index=False))
        print(f"[实验] 完成，用时 {time.time() - started:.1f}s")
        return 0
    except Exception as exc:  # noqa: BLE001
        print("=" * 70)
        traceback.print_exc()
        print(f"[实验] 失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
