from __future__ import annotations

from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
Q4 = HERE.parent / "Results" / "Tables"
Q3 = HERE.parents[2] / "Q3" / "Results" / "Tables"

COLS = ["strategy", "total_cost_yuan", "plan_cost_yuan", "adjustment_cost_yuan",
        "market_cost_yuan", "emergency_cost_yuan", "emergency_kwh",
        "curtail_kwh", "spill_kwh"]


def main() -> None:
    q3 = pd.read_csv(Q3 / "strategy_summary.csv")
    q4 = pd.read_csv(Q4 / "strategy_summary.csv")
    m = q3[COLS].merge(q4[COLS], on="strategy", suffixes=("_fixed", "_fluc"))
    for c in COLS[1:]:
        m[c + "_diff"] = m[c + "_fluc"] - m[c + "_fixed"]
    m.to_csv(Q4 / "compare_fluc_vs_fixed.csv", index=False, encoding="utf-8-sig")

    show = m[["strategy", "total_cost_yuan_fixed", "total_cost_yuan_fluc", "total_cost_yuan_diff",
              "emergency_kwh_fixed", "emergency_kwh_fluc",
              "curtail_kwh_fixed", "curtail_kwh_fluc"]].copy()
    show.columns = ["策略", "固定总费", "波动总费", "总费差", "固定紧急kWh", "波动紧急kWh", "固定弃光", "波动弃光"]
    for c in show.columns[1:]:
        show[c] = show[c].map(lambda v: f"{v:,.0f}")
    print(show.to_string(index=False))

    best_f = m.loc[m.total_cost_yuan_fixed.idxmin(), "strategy"]
    best_l = m.loc[m.total_cost_yuan_fluc.idxmin(), "strategy"]
    print(f"\n固定电价最优策略: {best_f} = {m.total_cost_yuan_fixed.min():,.2f} 元")
    print(f"波动电价最优策略: {best_l} = {m.total_cost_yuan_fluc.min():,.2f} 元")
    s0 = m[m.strategy == "S0"].iloc[0]
    sall = m[m.strategy == "Sall"].iloc[0]
    print("\n引入全部更新的价值（S0 - Sall）:")
    print(f"  固定电价: {s0.total_cost_yuan_fixed - sall.total_cost_yuan_fixed:,.2f} 元")
    print(f"  波动电价: {s0.total_cost_yuan_fluc - sall.total_cost_yuan_fluc:,.2f} 元")
    print(f"\n对比表已写入 {Q4 / 'compare_fluc_vs_fixed.csv'}")


if __name__ == "__main__":
    main()
