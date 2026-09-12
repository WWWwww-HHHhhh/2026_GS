"""Prepare typed result3 cell matrices from the validated Sall long records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
T=144


def hhmm(minutes: int) -> str:
    return f"{minutes//60}:{minutes%60:02d}"


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",type=Path,default=HERE/"results")
    parser.add_argument("--strategy",default="S6_12")
    args=parser.parse_args()
    report=json.loads((args.folder/"validation_report.json").read_text(encoding="utf-8"))
    if report["status"]!="PASS" or not any(x["strategy"]==args.strategy for x in report["strategies"]):
        raise RuntimeError(f"{args.strategy} must pass validation before export")
    slots=pd.read_csv(args.folder/args.strategy/"intervals.csv")
    daily=pd.read_csv(args.folder/args.strategy/"daily.csv")
    if len(slots)!=334*T or len(daily)!=334:
        raise RuntimeError("incomplete formal records")
    dates=daily.date.tolist()
    x=slots.zero_plan_kwh.to_numpy().reshape(334,T)
    q=slots.final_plan_kwh.to_numpy().reshape(334,T)
    c=slots.charge_kwh.to_numpy().reshape(334,T)
    r=slots.discharge_kwh.to_numpy().reshape(334,T)
    e=slots.emergency_kwh.to_numpy().reshape(334,T)
    start_soc=slots.soc_start_kwh.to_numpy().reshape(334,T)[:,0]
    end_soc=slots.soc_end_kwh.to_numpy().reshape(334,T)[:,-1]

    def purchase_matrix(values:np.ndarray, fee:np.ndarray) -> list[list]:
        rows=[]
        for i,day in enumerate(dates):
            display=values[i,1:].tolist()
            display.append(float(values[i+1,0]) if i<333 else None)
            rows.append([day]+[float(v) if v is not None else None for v in display]
                        +[float(np.sum(values[i])),float(fee[i])])
        return rows

    plan_rows=purchase_matrix(x,daily.plan_cost_yuan.to_numpy())
    adjusted_rows=purchase_matrix(q,daily.market_cost_yuan.to_numpy())
    charge_rows=[]
    for i,day in enumerate(dates):
        for block in range(6):
            row=[day if block==0 else None,
                 f"{hhmm(block*240)}-{hhmm((block+1)*240)}",
                 float(np.sum(c[i,block*24:(block+1)*24])),
                 float(np.sum(r[i,block*24:(block+1)*24])),
                 "0:00" if block==0 else "24:00" if block==1 else None,
                 float(start_soc[i]) if block==0 else float(end_soc[i]) if block==1 else None]
            charge_rows.append(row)
    emergency_rows=[]
    for i,day in enumerate(dates):
        positive=e[i]>1e-8
        starts=np.flatnonzero(positive & ~np.r_[False,positive[:-1]])
        ends=np.flatnonzero(positive & ~np.r_[positive[1:],False])+1
        for episode,(a,b) in enumerate(zip(starts,ends)):
            emergency_rows.append([day if episode==0 else None,
                                   f"{hhmm(int(a)*10)}-{hhmm(int(b)*10)}",
                                   float(np.sum(e[i,a:b]))])
    if abs(sum(row[2] for row in emergency_rows)-daily.emergency_kwh.sum())>1e-5:
        raise RuntimeError("emergency event aggregation mismatch")
    payload={"plan":plan_rows,"adjusted":adjusted_rows,
             "charge":charge_rows,"emergency":emergency_rows,
             "report_days":334,"emergency_episode_count":len(emergency_rows)}
    path=args.folder/"result3_payload.json"
    path.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps({"payload":str(path),"plan_rows":len(plan_rows),
                      "charge_rows":len(charge_rows),"emergency_rows":len(emergency_rows)},ensure_ascii=False))


if __name__=="__main__":
    main()
