"""计算附件3 那一格（V_official_unknown_q2params）的全部论文用数，并与自建口径对比。

只读当前Q4工作区的结果文件，全部产出写入 All_Code/Q4/Q4_WYH。
输出：official_cell_numbers.md、official_cell_numbers.csv
"""

import io
import os
import sys
import json
import numpy as np
import pandas as pd

NEW = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(NEW, "..", "..", ".."))
Q4W = NEW
sys.path.insert(0, os.path.join(Q4W, "Data_processing"))
from q4_common import T, load_pickle_compat  # noqa: E402

CELL = os.path.join(Q4W, "Data_processing", "variants", "V_official_unknown_q2params_results.pkl")
MAIN = os.path.join(Q4W, "Data_processing", "q4_2_rolling_results.pkl")
OUT_MD = os.path.join(NEW, "official_cell_numbers.md")
OUT_CSV = os.path.join(NEW, "official_cell_numbers.csv")

L = []


def log(s=""):
    L.append(str(s))


def timing_metrics(logs):
    """复刻 q4_2_diagnostics.py 的口径：按当日价格排序分四档，统计计划/充电/放电的落档占比。"""
    plan_cheap, chg_cheap, dis_exp = [], [], []
    tot_cost = tot_x = 0.0
    for l in logs:
        p = np.asarray(l["price"], dtype=float)
        x = np.asarray(l["plan_x"], dtype=float)
        c = np.asarray(l.get("settle_c_actual", l["plan_c"]), dtype=float)
        r = np.asarray(l.get("settle_r_actual", l["plan_r"]), dtype=float)
        order = np.argsort(p, kind="stable")
        q = np.empty(T, dtype=int)
        q[order] = np.minimum(3, (np.arange(T) * 4) // T)   # 0=最便宜 25%，3=最贵 25%
        sx = x.sum()
        if sx > 0:
            plan_cheap.append(float(x[q == 0].sum()) / float(sx))
        sc = c.sum()
        if sc > 0:
            chg_cheap.append(float(c[q == 0].sum()) / float(sc))
        sr = r.sum()
        if sr > 0:
            dis_exp.append(float(r[q == 3].sum()) / float(sr))
        tot_cost += float(np.sum(p * x))
        tot_x += float(sx)
    return {
        "unit_price": tot_cost / tot_x,
        "plan_cheap_pct": float(np.mean(plan_cheap)) * 100,
        "charge_cheap_pct": float(np.mean(chg_cheap)) * 100,
        "discharge_expensive_pct": float(np.mean(dis_exp)) * 100,
    }


def cell_stats(tag, path):
    obj = load_pickle_compat(path)
    logs = obj["report_logs"]
    s = {k: v for k, v in obj["summary"].items()} if isinstance(obj.get("summary"), dict) else {}
    tot = sum(float(l["cost_total"]) for l in logs)
    plan_cost = sum(float(l["cost_plan"]) for l in logs)
    emg_cost = sum(float(l["cost_emergency"]) for l in logs)
    plan_kwh = sum(float(l["plan_total_kwh"]) for l in logs)
    emg_kwh = sum(float(l["emergency_kwh"]) for l in logs)
    load_kwh = sum(float(l["load_kwh"]) for l in logs)
    unext = sum(float(l["unextracted_kwh"]) for l in logs)
    curt = sum(float(l["curtail_kwh"]) for l in logs)
    pv = sum(float(l["pv_kwh"]) for l in logs)
    prices = np.concatenate([np.asarray(l["price"], dtype=float) for l in logs])
    loads = np.concatenate([np.asarray(l["load_actual"], dtype=float) for l in logs])
    daily = np.array([float(l["cost_total"]) for l in logs])
    var = np.sort(daily)[int(np.ceil(0.90 * len(daily))) - 1:]
    cvar90 = float(var.mean())
    tm = timing_metrics(logs)
    return {
        "tag": tag,
        "days": len(logs),
        "total_cost": tot,
        "plan_cost": plan_cost,
        "emergency_cost": emg_cost,
        "plan_kwh": plan_kwh,
        "emergency_kwh": emg_kwh,
        "load_kwh": load_kwh,
        "unextracted_kwh": unext
        ,
        "curtail_kwh": curt,
        "pv_kwh": pv,
        "final_soc": float(logs[-1]["final_soc"]),
        "s0": float(logs[0]["s0"]),
        "unit_price": tm["unit_price"],
        "plan_cheap_pct": tm["plan_cheap_pct"],
        "charge_cheap_pct": tm["charge_cheap_pct"],
        "discharge_expensive_pct": tm["discharge_expensive_pct"],
        "market_mean_price": float(prices.mean()),
        "market_load_weighted": float((prices * loads).sum() / loads.sum()),
        "emergency_rate_pct": emg_kwh / load_kwh * 100,
        "unextracted_pct": unext / plan_kwh * 100,
        "curtail_pct": curt / pv * 100,
        "cvar90_daily": cvar90,
        "max_daily": float(daily.max()),
        "max_eq_residual": max(float(l.get("eq_residual", 0.0)) for l in logs),
        "max_ub_violation": max(float(l.get("ub_violation", 0.0)) for l in logs),
        "soc_violations": int(sum(int(l.get("soc_violate_count", 0)) for l in logs)),
        "_summary": s,
    }


def main():
    off = cell_stats("附件3 预报（official）", CELL)
    own = cell_stats("自建因果预测（q2）", MAIN)

    log("# 附件3 口径（新主口径）的全部论文用数")
    log("")
    log("数据来源：`Data_processing/variants/V_official_unknown_q2params_results.pkl`（价格零点未知、附件3 光伏预报、M=30、β=0.20、κ×1.0）")
    log("")
    log("| 指标 | 附件3 口径（新主口径） | 自建预测口径（原主口径，改为对照） | 论文原写法 |")
    log("| --- | --- | --- | --- |")
    papers = {
        "total_cost": "15561929.84 元",
        "plan_cost": "14670390.10 元",
        "emergency_cost": "891539.74 元",
        "plan_kwh": "22803530.04 kWh",
        "emergency_kwh": "217118.05 kWh",
        "emergency_rate_pct": "0.587%",
        "unit_price": "0.6433 元/kWh",
        "plan_cheap_pct": "41.17%",
        "charge_cheap_pct": "48.22%",
        "discharge_expensive_pct": "71.95%",
        "unextracted_kwh": "1639609.3 kWh",
        "unextracted_pct": "7.19%",
        "cvar90_daily": "未写入正文",
        "final_soc": "6000 kWh",
        "max_eq_residual": "2.27e-13 kWh",
        "max_ub_violation": "未写入正文",
        "market_mean_price": "0.7575 元/kWh",
    }
    labels = {
        "total_cost": "报告期总费用（元）",
        "plan_cost": "其中计划购电费（元）",
        "emergency_cost": "其中紧急购电费（元）",
        "plan_kwh": "计划购电量（kWh）",
        "emergency_kwh": "紧急购电量（kWh）",
        "load_kwh": "报告期总负荷（kWh）",
        "emergency_rate_pct": "紧急购电量占总负荷（%）",
        "unit_price": "计划购电平均单价（元/kWh）",
        "market_mean_price": "报告期市场均价（算术平均，元/kWh）",
        "market_load_weighted": "报告期市场均价（负荷加权，元/kWh）",
        "plan_cheap_pct": "计划量落在当日最便宜 25%（%）",
        "charge_cheap_pct": "充电量落在当日最便宜 25%（%）",
        "discharge_expensive_pct": "放电量落在当日最贵 25%（%）",
        "unextracted_kwh": "累计未提取量（kWh）",
        "unextracted_pct": "未提取占计划量（%）",
        "curtail_kwh": "累计弃光量（kWh）",
        "curtail_pct": "弃光率（%）",
        "cvar90_daily": "日费用 CVaR90（元）",
        "max_daily": "单日最大费用（元）",
        "max_eq_residual": "电量平衡最大残差（kWh）",
        "max_ub_violation": "上界违约最大残差（kWh）",
        "soc_violations": "储电量越界次数",
        "final_soc": "年末储电量（kWh）",
    }
    for k, lab in labels.items():
        if k in ("load_kwh", "market_load_weighted", "curtail_kwh", "curtail_pct", "max_daily", "soc_violations"):
            pv = "未写入正文"
        else:
            pv = papers.get(k, "未写入正文")
        fo = off[k]
        fo_s = ("%.6f" % fo) if isinstance(fo, float) and abs(fo) < 1000 else ("%,.2f".replace("%,", "{:,").format(fo) if False else format(fo, ",.2f"))
        fo_s = format(fo, ",.2f") if not isinstance(fo, int) else str(fo)
        if k in ("emergency_rate_pct", "plan_cheap_pct", "charge_cheap_pct", "discharge_expensive_pct",
                 "unextracted_pct", "curtail_pct"):
            fo_s = "%.3f" % fo
        ow_s = format(own[k], ",.2f") if not isinstance(own[k], int) else str(own[k])
        if k in ("emergency_rate_pct", "plan_cheap_pct", "charge_cheap_pct", "discharge_expensive_pct",
                 "unextracted_pct", "curtail_pct"):
            ow_s = "%.3f" % own[k]
        if k in ("unit_price", "market_mean_price", "market_load_weighted"):
            fo_s = "%.4f" % fo
            ow_s = "%.4f" % own[k]
        if k in ("max_eq_residual", "max_ub_violation"):
            fo_s = "%.3e" % fo
            ow_s = "%.3e" % own[k]
        log("| %s | %s | %s | %s |" % (lab, fo_s, ow_s, pv))
    log("")

    log("## 派生量（论文直接引用）")
    log("")
    d_price_off = off["unit_price"] - off["market_mean_price"]
    log("- 计划购电单价相对市场均价的折让：附件3 口径 %.4f / %.4f = %+.2f%%，自建口径 %.4f / %.4f = %+.2f%%"
        % (off["unit_price"], off["market_mean_price"], (off["unit_price"] / off["market_mean_price"] - 1) * 100,
           own["unit_price"], own["market_mean_price"], (own["unit_price"] / own["market_mean_price"] - 1) * 100))
    log("- 自建预测相对附件3 预报的收益：%.2f 元 = %.2f 万元 = %.2f%%"
        % (off["total_cost"] - own["total_cost"], (off["total_cost"] - own["total_cost"]) / 1e4,
           (off["total_cost"] - own["total_cost"]) / off["total_cost"] * 100))
    log("")

    log("## 受控 2×2 在新主口径下的表述")
    log("")
    q2u = off["total_cost"]          # 附件3 + 未知（新主模型）
    q2k = 15345273.08                # 自建 + 已知
    ofk = 15504400.92                # 附件3 + 已知
    ofu = own["total_cost"]          # 自建 + 未知
    log("- 新主模型（附件3 + 价格未知）= %.2f 元 = %.2f 万元" % (q2u, q2u / 1e4))
    log("- 附件3 + 价格已知 = %.2f 元 = %.2f 万元；价格信息价值 = %.2f 元 = %.2f 万元 = %.2f%%"
        % (ofk, ofk / 1e4, q2u - ofk, (q2u - ofk) / 1e4, (q2u - ofk) / q2u * 100))
    log("- 自建 + 价格未知（对照）= %.2f 元 = %.2f 万元；改用自建预报可省 = %.2f 元 = %.2f 万元 = %.2f%%"
        % (ofu, ofu / 1e4, q2u - ofu, (q2u - ofu) / 1e4, (q2u - ofu) / q2u * 100))
    log("- 自建 + 价格已知 = %.2f 元 = %.2f 万元；该口径下价格信息价值 = %.2f 元 = %.2f 万元 = %.2f%%"
        % (q2k, q2k / 1e4, ofu - q2k, (ofu - q2k) / 1e4, (ofu - q2k) / ofu * 100))
    log("- 交互项 = (附件3 未知 − 附件3 已知) − (自建 未知 − 自建 已知) = %.2f 元 = %.2f 万元"
        % ((q2u - ofk) - (ofu - q2k), ((q2u - ofk) - (ofu - q2k)) / 1e4))
    log("")

    log("## 结构核验（10.6.1 用）")
    log("")
    log("- 附件3 口径：电量平衡最大残差 %.3e kWh，上界违约最大残差 %.3e kWh，储电量越界 %d 次，报告期 %d 天"
        % (off["max_eq_residual"], off["max_ub_violation"], off["soc_violations"], off["days"]))
    log("- 自建口径：电量平衡最大残差 %.3e kWh，上界违约最大残差 %.3e kWh，储电量越界 %d 次"
        % (own["max_eq_residual"], own["max_ub_violation"], own["soc_violations"]))
    log("")

    log("## 原始 summary 字段（附件3 格）")
    log("")
    log("```json")
    log(json.dumps({k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                    for k, v in off["_summary"].items()}, ensure_ascii=False, indent=2))
    log("```")

    io.open(OUT_MD, "w", encoding="utf-8", newline="").write("\n".join(L))

    rows = []
    for k in labels:
        rows.append({"指标": labels[k], "附件3口径": off[k], "自建口径": own[k]})
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print("report:", OUT_MD)
    print("csv:", OUT_CSV)


if __name__ == "__main__":
    main()
