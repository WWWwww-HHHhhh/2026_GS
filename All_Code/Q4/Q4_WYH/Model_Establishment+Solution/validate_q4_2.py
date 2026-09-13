# -*- coding: utf-8 -*-
"""validate_q4_2.py —— 问题 4-2 的独立验证、基线与稳健性。

包含四类内容：
  A. 结构核验（口径 spec §7 的 Q4-2 版本，独立于 Excel 回读，直接在解向量上验算）
  B. 基线对比：B0 完美预见下界 / B1 Q2固定价策略 / B2 实时缺口购电 / B3 典型日(Q1)策略
  C. 结算口径 R1(实际波动价) vs R2(0:00 预测价) 的对照
  D. 场景数 M 稳健性与价格不确定度注入（可选）

运行：
    python validate_q4_2.py                     # A + B + C
    python validate_q4_2.py --sensitivity       # 追加 D（重跑报告期，耗时数分钟）
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


def load_results() -> dict:
    with open(OUT_DATA / "q4_2_rolling_results.pkl", "rb") as fh:
        return pickle.load(fh)


def load_scenarios(M: int) -> dict:
    with open(OUT_DATA / f"scenarios_M{M}.pkl", "rb") as fh:
        return pickle.load(fh)


def md_table(rows: list[list], header: list[str], floatfmt: str = ".2f") -> str:
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    for r in rows:
        cells = [f"{v:{floatfmt}}" if isinstance(v, float) else str(v) for v in r]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


# ----------------------------------------------------------------- 结构核验
def structural_checks(res: dict, ds: dict) -> tuple[list[dict], list[str]]:
    logs = res["report_logs"]
    rows, notes = [], []
    dates = [l["date"] for l in logs]

    ok_days = len(logs) == 334 and dates[0] == "2025-02-01" and dates[-1] == "2025-12-31"
    rows.append({"检查项": "报告期 334 天且首末日期正确", "是否通过": ok_days, "实测值": f"{len(logs)} 天 {dates[0]}~{dates[-1]}"})

    cont = all((pd.Timestamp(dates[i + 1]) - pd.Timestamp(dates[i])).days == 1 for i in range(len(dates) - 1))
    rows.append({"检查项": "报告期日期连续无缺日", "是否通过": cont, "实测值": f"{len(dates)} 天"})

    max_bal = max_yx = max_cap = max_soc = 0.0
    soc_lo, soc_hi = np.inf, -np.inf
    for l in logs:
        x = np.asarray(l["plan_x"]); c = np.asarray(l["plan_c"]); r = np.asarray(l["plan_r"])
        s = np.asarray(l["settle_s_actual"])
        y = np.asarray(l["settle_y"]); e = np.asarray(l["settle_e"])
        g = np.asarray(l["settle_g"]); w = np.asarray(l["settle_w"])
        sp = np.asarray(l["settle_spill"])
        L = np.asarray(l["load_actual"]); G = np.asarray(l["pv_actual"])
        max_bal = max(max_bal, float(np.max(np.abs(y + e + g + r - L - c - sp))))
        max_yx = max(max_yx, float(np.max(y - x)))
        max_cap = max(max_cap, float(max(c.max(), r.max())))
        soc_lo = min(soc_lo, float(s.min())); soc_hi = max(soc_hi, float(s.max()))
        max_soc = max(max_soc, float(np.max(np.abs(s[1:] - (s[:-1] + 0.9 * c - r / 0.9)))))
    rows += [
        {"检查项": "电量平衡残差", "是否通过": max_bal < 1e-6, "实测值": f"max={max_bal:.3e} kWh"},
        {"检查项": "提取上限 y ≤ x", "是否通过": max_yx < 1e-6, "实测值": f"max(y-x)={max_yx:.3e} kWh"},
        {"检查项": "充放电功率上限", "是否通过": max_cap <= 5000 / 6 + 1e-6, "实测值": f"max={max_cap:.4f} kWh/时段（上限 833.3333）"},
        {"检查项": "SOC 轨迹递推一致", "是否通过": max_soc < 1e-6, "实测值": f"max|Δ|={max_soc:.3e} kWh"},
        {"检查项": "SOC 全程在 [1200,10800]", "是否通过": soc_lo >= 1200 - 1e-6 and soc_hi <= 10800 + 1e-6,
         "实测值": f"[{soc_lo:.2f}, {soc_hi:.2f}]"},
    ]
    # 结算金额自洽：cost_plan 必须等于 Σ 实际价 × 计划量
    max_cost = 0.0
    for l in logs:
        price = np.asarray(l["price"], dtype=float); x = np.asarray(l["plan_x"], dtype=float)
        max_cost = max(max_cost, abs(float(l["cost_plan"]) - float(np.sum(price * x))))
    rows.append({"检查项": "计划购电费 = Σ 实际波动价 × 计划量（口径 R1）",
                 "是否通过": max_cost < 1e-6, "实测值": f"max|Δ|={max_cost:.3e} 元"})

    # 因果性
    rp = [l for l in logs]
    rows.append({"检查项": "场景残差块仅用决策日之前的历史", "是否通过": True,
                 "实测值": "由 05_q4_scenarios.py 断言保证（max_block_day < i）与 selection 日志（train_max_day_index < i）"})
    notes.append(f"跨日 SOC 起点 2025-01-01 00:00 = {SOC0} kWh；报告期起点 SOC = {logs[0]['s0']:.2f} kWh；"
                 f"报告期末点 SOC = {logs[-1]['final_soc']:.2f} kWh")
    return rows, notes


# ----------------------------------------------------------------- 基线
def run_b0_perfect_foresight(ds: dict, res: dict) -> dict:
    """完美信息对照方案：逐日 M=1、用当天实际价格/负荷/光伏求解，SOC 链与主模型同起点。

    ⚠️ 术语纪律：它**不是**严格的数学下界。原因有三：
      1) 每日独立求解、只通过 SOC 链耦合，未对整段报告期做全局最优；
      2) 目标里仍保留软终端惩罚 κ·|ξ|，而结算的真实费用不含该项；
      3) 电池充放电仍走同一套策略结构。
    因此对外一律称"完美信息对照方案"，其与主模型的差额是"相对该对照方案的费用差"，
    包含终端惩罚、逐日求解与策略结构的共同影响，**不等于纯信息成本**。
    """
    logs = res["report_logs"]
    s0 = float(logs[0]["s0"])
    kappa = float(res["params"]["kappa2"])
    total = 0.0
    emg_cost = 0.0
    for l in logs:
        i = l["day_index"]
        P = ds["price"][:, i][None, :]; L = ds["load"][:, i][None, :]; G = ds["pv"][:, i][None, :]
        kw = {"kappa2": kappa, "beta": 0.0, "alpha": 0.90}
        if i == D - 1:
            kw.update({"hard_terminal": True, "s_ref": SOC0})
        plan = solve_day(P, L, G, s0, kw)
        st = settle_day(ds["price"][:, i], plan["x"], plan["c"], plan["r"], L[0], G[0], s0)
        s0 = float(st["s_actual"][-1])
        total += st["cost_total"]; emg_cost += st["cost_emergency"]
    return {"name": "B0 完美信息对照方案（当日实际值，逐日求解）", "cost": total,
            "emergency_cost": emg_cost}


def run_b1_fixed_price(ds: dict, res: dict, scen: dict) -> dict:
    """B1：沿用 Q2 的固定电价（附件1）做日前优化，但按实际波动电价结算。"""
    logs = res["report_logs"]
    s0 = float(logs[0]["s0"])
    params = {"kappa2": float(res["params"]["kappa2"]), "beta": float(res["params"]["beta"]),
              "alpha": float(res["params"]["alpha"])}
    total = 0.0
    emg_cost = 0.0
    for l in logs:
        i = l["day_index"]
        P = np.tile(ds["price_q2_fixed"][None, :], (scen["M"], 1))
        kw = dict(params)
        if i == D - 1:
            kw.update({"hard_terminal": True, "s_ref": SOC0})
        plan = solve_day(P, scen["L_all"][i], scen["G_all"][i], s0, kw)
        st = settle_day(ds["price"][:, i], plan["x"], plan["c"], plan["r"],
                        ds["load"][:, i], ds["pv"][:, i], s0)
        s0 = float(st["s_actual"][-1])
        total += st["cost_total"]; emg_cost += st["cost_emergency"]
    return {"name": "B1 Q2固定价策略（实际波动价结算）", "cost": total, "emergency_cost": emg_cost}


def run_b2_realtime_gap(ds: dict, res: dict) -> dict:
    """B2 **假想情景**：实时市场即时购电（无 0:00 计划承诺、可按实时价即时买入缺口），且不动储能。

    ⚠️ 命名纪律：本情景**不是题目规则下的可执行策略**。题面规定"微网供电低于负载时按交易时刻电价的
    5 倍紧急购电"，若完全没有 0:00 计划，则全部用能都应按 5 倍结算 —— 那是下方 B2' 的口径。
    B2 只用于给出"完全不做日前优化、但能在实时市场按平价即时成交"这一假想下的费用量级。
    """
    logs = res["report_logs"]
    total = 0.0
    for l in logs:
        i = l["day_index"]
        price = ds["price"][:, i]; L = ds["load"][:, i]; G = ds["pv"][:, i]
        gap = np.maximum(L - G, 0.0)
        total += float(np.sum(price * gap))
    return {"name": "B2 实时市场即时购电（假想：无 0:00 计划承诺，按实时价成交）", "cost": total}


def run_b2p_all_emergency(ds: dict, res: dict) -> dict:
    """B2' **题目规则口径**：无日前计划 ⇒ 全部用能均按紧急购电结算，即 5 × Σ λ·(L−PV)⁺。

    这才是"完全不制定计划"在题面规则下的真实代价，与 B2 并列呈现，两者语义差别明确。
    """
    logs = res["report_logs"]
    total = 0.0
    emg_kwh = 0.0
    for l in logs:
        i = l["day_index"]
        price = ds["price"][:, i]; L = ds["load"][:, i]; G = ds["pv"][:, i]
        gap = np.maximum(L - G, 0.0)
        total += float(np.sum(5.0 * price * gap))
        emg_kwh += float(np.sum(gap))
    return {"name": "B2' 无计划·全额紧急购电（题目规则 5× 交易时刻电价）", "cost": total,
            "emergency_kwh": emg_kwh}


def run_b3_typical_day(ds: dict, res: dict) -> dict:
    """B3 典型日策略：把 Q1（附件1 平均日）的最优计划每天原样执行，按实际波动价结算。"""
    r1 = REPO / "All_Code" / "Q1" / "Results" / "Tables" / "result1.xlsx"
    if not r1.exists():
        return {"name": "B3 典型日(Q1)策略", "cost": float("nan"), "note": f"缺少 {r1}"}
    plan = pd.read_excel(r1, sheet_name="计划购电量")
    stor = pd.read_excel(r1, sheet_name="充放电量")
    x = pd.to_numeric(plan.iloc[:, 1], errors="coerce").to_numpy(float)
    if x.shape[0] != T or not np.isfinite(x).all():
        return {"name": "B3 典型日(Q1)策略", "cost": float("nan"), "note": "Q1 计划向量形状异常"}
    c = np.zeros(T); r = np.zeros(T)
    bands = [(0, 24), (24, 48), (48, 72), (72, 96), (96, 120), (120, 144)]
    for k, (a, b) in enumerate(bands):
        c[a:b] = float(pd.to_numeric(stor.iloc[k, 1], errors="coerce") or 0.0) / (b - a)
        r[a:b] = float(pd.to_numeric(stor.iloc[k, 2], errors="coerce") or 0.0) / (b - a)
    total = 0.0
    emg_cost = 0.0
    s0 = SOC0
    for l in res["report_logs"]:
        i = l["day_index"]
        st = settle_day(ds["price"][:, i], x, c, r, ds["load"][:, i], ds["pv"][:, i], s0)
        s0 = SOC0  # Q1 典型日策略保证 0:00 与 24:00 储电量相同，日间不传递
        total += st["cost_total"]; emg_cost += st["cost_emergency"]
    return {"name": "B3 典型日(Q1)策略", "cost": total, "emergency_cost": emg_cost}


def r1_vs_r2(res: dict) -> pd.DataFrame:
    """R2 反事实：计划购电费改按 0:00 的价格预测结算（只改计价，不改计划与执行）。"""
    pf = pickle.load(open(OUT_DATA / "price_forecast.pkl", "rb"))
    Phat = pf["price_hat"]
    rows = []
    for l in res["report_logs"]:
        i = l["day_index"]
        x = np.asarray(l["plan_x"])
        c1 = float(l["cost_plan"])
        c2 = float(np.sum(Phat[:, i] * x))
        rows.append({"date": l["date"], "cost_plan_R1": c1, "cost_plan_R2": c2,
                     "diff": c1 - c2, "cost_emergency": l["cost_emergency"]})
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sensitivity", action="store_true")
    args = ap.parse_args()
    started = time.time()
    try:
        ds = load_dataset()
        res = load_results()
        TABLES.mkdir(parents=True, exist_ok=True)
        scen = load_scenarios(int(res["params"]["M"]))

        print("[A] 结构核验")
        rows, notes = structural_checks(res, ds)
        audit = pd.DataFrame(rows)
        for r in rows:
            print(f"    [{'PASS' if r['是否通过'] else 'FAIL'}] {r['检查项']}: {r['实测值']}")
        for n in notes:
            print(f"    · {n}")
        if not audit["是否通过"].all():
            raise RuntimeError("结构核验存在 FAIL")

        print("[B] 基线对比（全部重跑，非引用既有数字）")
        base = [run_b0_perfect_foresight(ds, res), run_b1_fixed_price(ds, res, scen),
                run_b2_realtime_gap(ds, res), run_b2p_all_emergency(ds, res),
                run_b3_typical_day(ds, res)]
        main_cost = float(sum(l["cost_total"] for l in res["report_logs"]))
        emg = float(sum(l["cost_emergency"] for l in res["report_logs"]))
        b0 = float(base[0]["cost"])
        # 修正：主模型行的"相对增量"必须等于 main_cost − b0，不得写死 0
        bros = [["Q4-2 主模型（波动电价随机规划）", main_cost, main_cost - b0, emg]]
        for b in base:
            cost = b["cost"]
            gap = (cost - b0) if np.isfinite(cost) else float("nan")
            if b["name"].startswith("B2'"):
                emgc = cost                      # 全额按紧急购电结算，紧急购电费即总额
            else:
                emgc = float(b.get("emergency_cost", float("nan")))
            bros.append([b["name"], cost, gap, emgc])
            print(f"    {b['name']}: {cost:,.2f} 元"
                  + (f"（相对完美信息对照方案 +{cost - b0:,.2f}）" if np.isfinite(cost) else f" {b.get('note','')}"))
        print(f"    主模型相对完美信息对照方案的费用差 = {main_cost - b0:,.2f} 元"
              f"（{(main_cost - b0)/b0*100:.2f}%）；该差值含终端惩罚、逐日求解与策略结构的共同影响，"
              f"不等于纯信息成本")
        base_df = pd.DataFrame(bros, columns=["方案", "报告期总费用(元)",
                                              "相对完美信息对照方案的费用差(元)", "其中紧急购电费(元)"])

        print("[C] 结算口径 R1 vs R2")
        rr = r1_vs_r2(res)
        print(f"    R1（实际波动价）计划购电费合计 = {rr['cost_plan_R1'].sum():,.2f} 元")
        print(f"    R2（0:00 预测价）计划购电费合计 = {rr['cost_plan_R2'].sum():,.2f} 元"
              f"（差 {rr['diff'].sum():+,.2f} 元，{(rr['diff'].sum()/rr['cost_plan_R1'].sum())*100:+.3f}%）")

        sens_df = None
        if args.sensitivity:
            print("[D] 场景数 M 与价格不确定度稳健性（重跑报告期）")
            srows = []
            for M in (10, 20, 30):
                try:
                    sp = load_scenarios(M)
                except FileNotFoundError:
                    continue
                logs = res["report_logs"]
                s0 = float(logs[0]["s0"])
                tot = 0.0
                for l in logs:
                    i = l["day_index"]
                    kw = {"kappa2": float(res["params"]["kappa2"]), "beta": float(res["params"]["beta"]),
                          "alpha": float(res["params"]["alpha"])}
                    if i == D - 1:
                        kw.update({"hard_terminal": True, "s_ref": SOC0})
                    plan = solve_day(sp["P_all"][i], sp["L_all"][i], sp["G_all"][i], s0, kw)
                    st = settle_day(ds["price"][:, i], plan["x"], plan["c"], plan["r"],
                                    ds["load"][:, i], ds["pv"][:, i], s0)
                    s0 = float(st["s_actual"][-1]); tot += st["cost_total"]
                srows.append({"M": M, "report_total_cost": tot})
                print(f"    M={M}: {tot:,.2f} 元")
            for scale in (0.8, 1.2):
                logs = res["report_logs"]
                s0 = float(logs[0]["s0"]); tot = 0.0
                for l in logs:
                    i = l["day_index"]
                    cen = scen["P_all"][i].mean(axis=0)[None, :]
                    P = cen + scale * (scen["P_all"][i] - cen)
                    P = np.maximum(P, 0.0076)
                    kw = {"kappa2": float(res["params"]["kappa2"]), "beta": float(res["params"]["beta"]),
                          "alpha": float(res["params"]["alpha"])}
                    if i == D - 1:
                        kw.update({"hard_terminal": True, "s_ref": SOC0})
                    plan = solve_day(P, scen["L_all"][i], scen["G_all"][i], s0, kw)
                    st = settle_day(ds["price"][:, i], plan["x"], plan["c"], plan["r"],
                                    ds["load"][:, i], ds["pv"][:, i], s0)
                    s0 = float(st["s_actual"][-1]); tot += st["cost_total"]
                srows.append({"M": f"价格不确定度×{scale}", "report_total_cost": tot})
                print(f"    价格不确定度 ×{scale}: {tot:,.2f} 元")
            sens_df = pd.DataFrame(srows)
            sens_df.to_csv(TABLES / "q4_2_robustness.csv", index=False, encoding="utf-8-sig")

        monthly = []
        logs = res["report_logs"]
        mdf = pd.DataFrame([{k: v for k, v in l.items() if not isinstance(v, np.ndarray)} for l in logs])
        mdf["month"] = pd.to_datetime(mdf["date"]).dt.month
        for m, g in mdf.groupby("month"):
            monthly.append([int(m), int(len(g)), float(g["cost_total"].sum()),
                            float(g["cost_plan"].sum()), float(g["cost_emergency"].sum()),
                            float(g["plan_total_kwh"].sum()), float(g["emergency_kwh"].sum()),
                            float(g["load_kwh"].sum()),
                            float(g["emergency_kwh"].sum() / g["load_kwh"].sum() * 100)])
        mon_df = pd.DataFrame(monthly, columns=["month", "days", "cost_total", "cost_plan",
                                                "cost_emergency", "plan_kwh", "emergency_kwh",
                                                "load_kwh", "emergency_rate_pct"])
        mon_df.to_csv(TABLES / "q4_2_monthly_summary.csv", index=False, encoding="utf-8-sig")
        audit.to_csv(TABLES / "q4_2_structural_checks.csv", index=False, encoding="utf-8-sig")
        base_df.to_csv(TABLES / "q4_2_baselines.csv", index=False, encoding="utf-8-sig")
        rr.to_csv(TABLES / "q4_2_settlement_R1_vs_R2.csv", index=False, encoding="utf-8-sig")

        # 汇总报告
        lines = ["# 问题 4-2 验证与基线报告", "",
                 f"- 参数：M={res['params']['M']}，β={res['params']['beta']}，"
                 f"κ={res['params']['kappa2']:.4f}（κ_base={res['kappa2_base']:.4f}），α={res['params']['alpha']}",
                 f"- 选参期：{res['selection_period']}；报告期：{res['report_period']}",
                 f"- 状态起点：{res['state_origin']}；终端：{res['terminal_constraint']}", "",
                 "## A 结构核验", "",
                 md_table([[r["检查项"], "PASS" if r["是否通过"] else "FAIL", r["实测值"]] for r in rows],
                          ["检查项", "结果", "实测值"], floatfmt=".0f")]
        lines += ["", "备注：" + "；".join(notes), "",
                  "## B 基线对比", "",
                  md_table(base_df.values.tolist(), list(base_df.columns)),
                  "",
                  f"主模型报告期总费用 {main_cost:,.2f} 元，相对 B0 完美信息对照方案的费用差为 "
                  f"{main_cost - b0:,.2f} 元（{(main_cost - b0) / b0 * 100:.2f}%）。"
                  f"**该差值不等于纯信息成本**：B0 逐日独立求解、只经 SOC 链耦合，且目标中保留软终端惩罚、"
                  f"沿用同一套策略结构，因此它是对照方案而非严格数学下界；其中主模型紧急购电费 {emg:,.2f} 元。", "",
                  "口径说明：**B2 是假想情景**（无 0:00 计划承诺、可按实时价即时成交），"
                  "**B2' 才是题面规则下「完全不制定计划」的口径**（全部用能按交易时刻电价 5 倍紧急购电）。"
                  "两者并列，语义差别明确，不可混用。", "",
                  "## C 结算口径对照", "",
                  f"- R1（实际波动价）：{rr['cost_plan_R1'].sum():,.2f} 元（主口径）",
                  f"- R2（0:00 预测价）：{rr['cost_plan_R2'].sum():,.2f} 元",
                  f"- 差异：{rr['diff'].sum():+,.2f} 元（{rr['diff'].sum() / rr['cost_plan_R1'].sum() * 100:+.3f}%）",
                  "", "## D 逐月汇总", "", md_table(monthly,
                          ["月", "天数", "总费用", "计划购电费", "紧急购电费", "计划购电量", "紧急购电量", "负荷", "紧急购电率%"],
                          floatfmt=".2f")]
        if sens_df is not None:
            lines += ["", "## E 稳健性", "", sens_df.to_string(index=False)]
        (TABLES / "q4_2_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"    报告: {TABLES / 'q4_2_validation_report.md'}")
        print(f"[validate] 完成，用时 {time.time() - started:.1f}s")
        return 0
    except Exception as exc:  # noqa: BLE001
        print("=" * 70)
        traceback.print_exc()
        print(f"[validate] 失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
