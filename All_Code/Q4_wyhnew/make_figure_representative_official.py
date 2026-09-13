"""生成附件3 口径（新主口径）下的代表日图，输出到 Q4_wyhnew/figures。

与 make_figures_q4_2.py 的 fig_representative 保持同一绘图逻辑，仅两处不同：
  1 数据源改为 variants/V_official_unknown_q2params_results.pkl（附件3 光伏预报、价格零点未知）；
  2 左上角的“日前预测”曲线改用 price_forecast.pkl 的因果价格预测（该格日志未存 price_scen 键），
     因此图例写作“日前因果预测”而不是“场景均值”。
代表日仍按“报告期紧急购电量最多的一天”选取，与论文正文的措辞一致。
"""

import os
import sys
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 120

WS = Path(r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS")
Q4W = WS / "All_Code" / "Q4" / "Q4_wyh"
DATA = Q4W / "Data_processing"
NEW = WS / "All_Code" / "Q4_wyhnew"
OUTDIR = NEW / "figures"
T = 144
CELL = DATA / "variants" / "V_official_unknown_q2params_results.pkl"


def main():
    sys.path.insert(0, str(DATA))
    from q4_common import load_pickle_compat

    OUTDIR.mkdir(parents=True, exist_ok=True)
    ds = load_pickle_compat(DATA / "q4_dataset.pkl")
    res = load_pickle_compat(CELL)
    pf = load_pickle_compat(DATA / "price_forecast.pkl")

    logs = res["report_logs"]
    by = {l["date"]: l for l in logs}
    mdf = pd.DataFrame([{k: v for k, v in l.items() if not isinstance(v, np.ndarray)} for l in logs])
    pick = mdf.sort_values("emergency_kwh", ascending=False).iloc[0]["date"]
    l = by[pick]
    i = int(l["day_index"])
    print(f"新主口径代表日 = {pick}（day_index={i}），该日紧急购电量 {l['emergency_kwh']:.2f} kWh")
    print(f"该日总费用 {l['cost_total']:.2f} 元，计划购电量 {l['plan_total_kwh']:.2f} kWh")

    Phat = np.asarray(pf["price_hat"], dtype=float)
    if Phat.shape == (365, T):
        Phat = Phat.T
    hat_day = Phat[:, i]

    t = np.arange(1, T + 1) / 6.0
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.2))

    ax = axes[0, 0]
    ax.plot(t, ds["price"][:, i], color="#D05A4E", lw=1.2, label="实际波动电价")
    ax.plot(t, hat_day, color="#3F72AF", lw=1.0, ls="--", label="日前因果预测")
    ax.set_ylabel("电价（元/kWh）"); ax.set_xlabel("时刻（小时）")
    ax.set_title(f"{pick} 电价：实际 vs 日前预测", fontsize=9)
    ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25, lw=0.5)

    ax = axes[0, 1]
    ax.plot(t, ds["load"][:, i], color="#2F8F67", lw=1.2, label="实际负荷")
    ax.plot(t, ds["pv"][:, i], color="#E8A33D", lw=1.2, label="实际光伏")
    ax.plot(t, np.asarray(l["plan_x"]), color="#3F72AF", lw=1.0, label="计划购电量")
    ax.plot(t, np.asarray(l["settle_e"]), color="#B03A2E", lw=1.0, label="紧急购电量")
    ax.set_ylabel("电量（kWh/10min）"); ax.set_xlabel("时刻（小时）")
    ax.set_title("计划购电 vs 实际负荷/光伏/紧急购电", fontsize=9)
    ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25, lw=0.5)

    ax = axes[1, 0]
    c = np.asarray(l["plan_c"]); r = np.asarray(l["plan_r"])
    ax.bar(t, c, width=0.15, color="#3F72AF", label="充电")
    ax.bar(t, -r, width=0.15, color="#D05A4E", label="放电")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_ylabel("充/放电量（kWh/10min）"); ax.set_xlabel("时刻（小时）")
    ax.set_title("储能充放电（负值为放电）", fontsize=9)
    ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25, lw=0.5)

    ax = axes[1, 1]
    s = np.asarray(l["settle_s_actual"])
    ax.plot(np.arange(T + 1) / 6.0, s, color="#6C4AB6", lw=1.3)
    ax.axhline(1200, color="#B03A2E", lw=0.8, ls=":"); ax.axhline(10800, color="#B03A2E", lw=0.8, ls=":")
    ax.set_ylabel("储电量（kWh）"); ax.set_xlabel("时刻（小时）")
    ax.set_title("储能 SOC 轨迹（虚线为上下限）", fontsize=9)
    ax.grid(alpha=0.25, lw=0.5)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        p = OUTDIR / f"fig_q4_representative_day_official.{ext}"
        fig.savefig(p, bbox_inches="tight")
        print("  已写出", p)
    plt.close(fig)

    # 同时记录选日依据，便于论文核对
    top = mdf.sort_values("emergency_kwh", ascending=False).head(3)[["date", "emergency_kwh", "cost_total"]]
    rep = NEW / "representative_day_official.md"
    lines = ["# 附件3 口径下的代表日", "",
             f"- 选取规则：报告期 334 天中紧急购电量最多的一天（与论文正文措辞一致）",
             f"- 选中日期：{pick}（day_index={i}）",
             f"- 该日紧急购电量：{l['emergency_kwh']:.2f} kWh",
             f"- 该日总费用：{l['cost_total']:.2f} 元",
             f"- 该日计划购电量：{l['plan_total_kwh']:.2f} kWh",
             f"- 该日负荷：{l['load_kwh']:.2f} kWh，光伏：{l['pv_kwh']:.2f} kWh",
             "", "## 紧急购电量前三名", "", "```", top.to_string(index=False), "```", ""]
    rep.write_text("\n".join(lines), encoding="utf-8")
    print("  已写出", rep)


if __name__ == "__main__":
    main()
