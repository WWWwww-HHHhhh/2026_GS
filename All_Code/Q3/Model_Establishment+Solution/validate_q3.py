from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from q3_core import CAP, ETA_C, ETA_D, M, Q2, SOC_MAX, SOC_MIN, STRATEGIES, T, SourceData

HERE = Path(__file__).resolve().parent
ATOL = 2e-5


def close(a, b, label: str, tol: float = ATOL) -> float:
    av = np.asarray(a, dtype=float)
    bv = np.asarray(b, dtype=float)
    if av.shape != bv.shape:
        raise AssertionError(f"{label}: shape {av.shape} != {bv.shape}")
    deviation = float(np.max(np.abs(av - bv)))
    if not np.isfinite(deviation) or deviation > tol:
        raise AssertionError(f"{label}: max deviation {deviation}")
    return deviation


def verify_one(folder: Path, name: str, data: SourceData) -> dict:
    daily = pd.read_csv(folder / name / "daily.csv")
    slots = pd.read_csv(folder / name / "intervals.csv")
    updates = pd.read_csv(folder / name / "updates.csv")
    manifest = pd.read_csv(folder / name / "scenario_manifest.csv")
    summary = json.loads((folder / name / "summary.json").read_text(encoding="utf-8"))
    if len(daily) != 334 or len(slots) != 334*T:
        raise AssertionError(f"{name}: incomplete formal period")
    dates = data.dates[31:]
    if daily.date.tolist() != dates or slots.date.tolist() != np.repeat(dates, T).tolist():
        raise AssertionError(f"{name}: calendar sequence mismatch")
    if not np.array_equal(slots.interval_index.to_numpy(), np.tile(np.arange(T), 334)):
        raise AssertionError(f"{name}: 10-minute indexing mismatch")
    if not np.array_equal(slots.interval_start_min.to_numpy(), 10*np.tile(np.arange(T), 334)):
        raise AssertionError(f"{name}: interval start mismatch")
    if not np.array_equal(slots.interval_end_min.to_numpy(), 10*np.tile(np.arange(1,T+1), 334)):
        raise AssertionError(f"{name}: interval end mismatch")
    expected = {
        "price_yuan_per_kwh": data.price[:,31:].T.reshape(-1),
        "load_actual_kwh": data.load[:,31:].T.reshape(-1),
        "pv_actual_kwh": data.pv[:,31:].T.reshape(-1),
    }
    residuals = {f"source_{k}": close(slots[k], v, k) for k,v in expected.items()}
    p = slots.price_yuan_per_kwh.to_numpy()
    x = slots.zero_plan_kwh.to_numpy()
    q = slots.final_plan_kwh.to_numpy()
    c = slots.charge_kwh.to_numpy()
    r = slots.discharge_kwh.to_numpy()
    y = slots.used_plan_kwh.to_numpy()
    e = slots.emergency_kwh.to_numpy()
    g = slots.pv_used_kwh.to_numpy()
    w = slots.curtail_kwh.to_numpy()
    v = slots.spill_kwh.to_numpy()
    l = slots.load_actual_kwh.to_numpy()
    pv = slots.pv_actual_kwh.to_numpy()
    s0 = slots.soc_start_kwh.to_numpy()
    s1 = slots.soc_end_kwh.to_numpy()
    for key, values, lo, hi in (
        ("zero_plan",x,0,np.inf),("final_plan",q,0,np.inf),
        ("charge",c,0,CAP),("discharge",r,0,CAP),
        ("used_plan",y,0,np.inf),("emergency",e,0,np.inf),
        ("pv_used",g,0,np.inf),("curtail",w,0,np.inf),
        ("spill",v,0,np.inf),("soc_start",s0,SOC_MIN,SOC_MAX),
        ("soc_end",s1,SOC_MIN,SOC_MAX),
    ):
        if not np.isfinite(values).all() or min(values) < lo-ATOL or max(values) > hi+ATOL:
            raise AssertionError(f"{name}: invalid {key} bounds")
    if np.max(y-q) > ATOL:
        raise AssertionError(f"{name}: planned purchase exceeded")
    residuals["soc_recurrence"] = close(s1,s0+ETA_C*c-r/ETA_D,"SOC recurrence")
    residuals["soc_continuity"] = close(s0[1:],s1[:-1],"SOC continuity")
    residuals["power_balance"] = close(y+e+g+r,l+c+v,"realized balance")
    residuals["pv_partition"] = close(g+w,pv,"PV partition")
    demand = np.maximum(l+c-r,0)
    residuals["spill_rule"] = close(v,np.maximum(r-l-c,0),"spill rule")
    residuals["pv_first"] = close(g,np.minimum(pv,demand),"PV first")
    residuals["used_plan_rule"] = close(y,np.minimum(q,np.maximum(demand-g,0)),"used plan rule")
    residuals["emergency_rule"] = close(e,np.maximum(demand-g-y,0),"emergency rule")
    market = np.maximum(0.5*p*(x+q),1.5*p*q-0.5*p*x)
    alt_market = p*x+0.5*p*np.maximum(x-q,0)+1.5*p*np.maximum(q-x,0)
    residuals["market_cost"] = close(slots.market_cost_yuan,market,"market settlement")
    residuals["emergency_cost"] = close(slots.emergency_cost_yuan,5*p*e,"emergency settlement")
    residuals["alternative_market"] = close(slots.alternative_market_cost_yuan,alt_market,"alternate settlement")
    if np.min(alt_market-market) < -ATOL:
        raise AssertionError(f"{name}: alternate fee less than primary")
    grouped = slots.groupby("date",sort=False)
    sums = grouped[["zero_plan_kwh","final_plan_kwh","used_plan_kwh","emergency_kwh",
                    "curtail_kwh","spill_kwh","charge_kwh","discharge_kwh",
                    "market_cost_yuan","emergency_cost_yuan","alternative_market_cost_yuan"]].sum()
    for source,target in (
        ("zero_plan_kwh","zero_plan_kwh"),("final_plan_kwh","final_plan_kwh"),
        ("used_plan_kwh","used_plan_kwh"),("emergency_kwh","emergency_kwh"),
        ("curtail_kwh","curtail_kwh"),("spill_kwh","spill_kwh"),
        ("charge_kwh","charge_kwh"),("discharge_kwh","discharge_kwh"),
        ("market_cost_yuan","market_cost_yuan"),("emergency_cost_yuan","emergency_cost_yuan"),
    ):
        residuals[f"daily_{target}"] = close(daily[target],sums[source],f"daily {target}")
    residuals["daily_plan_cost"] = close(daily.plan_cost_yuan,grouped.apply(
        lambda z: float(np.dot(z.price_yuan_per_kwh,z.zero_plan_kwh)),include_groups=False),"daily plan fee")
    residuals["daily_adjustment"] = close(daily.adjustment_cost_yuan,
        daily.market_cost_yuan-daily.plan_cost_yuan,"daily adjustment fee")
    residuals["daily_total"] = close(daily.total_cost_yuan,
        daily.market_cost_yuan+daily.emergency_cost_yuan,"daily total")
    residuals["daily_alt_total"] = close(daily.alternative_total_cost_yuan,
        sums.alternative_market_cost_yuan+sums.emergency_cost_yuan,"daily alternate total")
    residuals["daily_soc_start"] = close(daily.soc_initial_kwh,s0.reshape(334,T)[:,0],"daily start SOC")
    residuals["daily_soc_end"] = close(daily.soc_final_kwh,s1.reshape(334,T)[:,-1],"daily end SOC")
    if abs(daily.soc_initial_kwh.iloc[0]-6000) > ATOL or abs(daily.soc_final_kwh.iloc[-1]-6000) > ATOL:
        raise AssertionError(f"{name}: initial or year-end SOC mismatch")
    if np.sum((c>ATOL)&(r>ATOL)) != 0:
        raise AssertionError(f"{name}: simultaneous charge-discharge")
    expected_issues = {0,*[k//6 for k in STRATEGIES[name]]}
    for tbl,table_name in ((updates,"updates"),(manifest,"manifest")):
        date_column="date" if table_name=="updates" else "target_date"
        groups = tbl.groupby([date_column,"issue_hour"],sort=False)
        if len(groups) != 334*len(expected_issues):
            raise AssertionError(f"{name}: incomplete {table_name} issue groups")
        if set(tbl.issue_hour.unique()) != expected_issues:
            raise AssertionError(f"{name}: wrong {table_name} issue times")
        if table_name == "manifest" and not (groups.size()==M).all():
            raise AssertionError(f"{name}: scenario count mismatch")
    idx = {d:i for i,d in enumerate(data.dates)}
    for row in manifest.itertuples():
        target, source = idx[row.target_date],idx[row.source_day]
        if not max(1,target-30) <= source < target or abs(row.weight-1/M)>1e-12:
            raise AssertionError(f"{name}: future or invalid scenario source")
    for field in ("plan_cost_yuan","adjustment_cost_yuan","market_cost_yuan","emergency_cost_yuan",
                  "total_cost_yuan","alternative_total_cost_yuan_for_same_policy","emergency_kwh",
                  "curtail_kwh","spill_kwh"):
        daily_field = "alternative_total_cost_yuan" if field.startswith("alternative_") else field
        residuals[f"summary_{field}"] = close(summary[field],daily[daily_field].sum(),f"summary {field}")
    if abs(summary["final_soc_kwh"]-6000)>ATOL:
        raise AssertionError(f"{name}: reported year-end SOC mismatch")
    return {"strategy":name,"days":len(daily),"slots":len(slots),
            "issues":len(updates),"scenario_rows":len(manifest),
            "total_cost_yuan":summary["total_cost_yuan"],
            "max_independent_residual":max(residuals.values()),
            "all_checks_passed":True}


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",type=Path,default=HERE/"results")
    parser.add_argument("--strategies",nargs="+",choices=tuple(STRATEGIES))
    args=parser.parse_args()
    data=SourceData.load_verified()
    metadata=json.loads((args.folder/"run_metadata.json").read_text(encoding="utf-8"))
    q2_book=Q2/"Results"/"Tables"/"result2.xlsx"
    actual_hash=hashlib.sha256(q2_book.read_bytes()).hexdigest()
    if metadata["source_hashes"]["q2_result2_sha256"]!=actual_hash:
        raise AssertionError("Q2 result2 source hash changed")
    q2_daily=pd.read_csv(Q2/"Results"/"Tables"/"daily_rolling_log.csv")
    q2_formal=q2_daily[q2_daily.date.between("2025-02-01","2025-12-31")]
    q2_cost=float(q2_formal.cost_total.sum())
    if len(q2_formal)!=334 or abs(q2_cost-14708963.494455712)>1e-3:
        raise AssertionError("Q2_yy validated baseline mismatch")
    names=args.strategies or metadata["strategies"]
    records=[verify_one(args.folder,name,data) for name in names]
    report={"status":"PASS","Q2_baseline_yuan":q2_cost,
            "strategies":records,"source_hashes":metadata["source_hashes"]}
    if args.strategies is None:
        (args.folder/"validation_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
