# -*- coding: utf-8 -*-
"""Q2'' 结果表：全年费用汇总、逐月预测/调度指标、2月调参窗口 β 网格。"""
import os, pickle, sys, time
import numpy as np
import pandas as pd

GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q2P = os.path.join(GS, "Q2''")
DATA_PROC = os.path.join(Q2P, "Data_processing")
TABLES = os.path.join(Q2P, "Results", "Tables")
T, D = 144, 365

from optimizer import solve_day2
from settlement import settle_day
from scenarios import build_scenarios

def roll(days, s0, beta, L_all, G_all, ds, kappa2=0.531667):
    s=float(s0); logs=[]
    for i in days:
        price=ds["price"][:,i]
        plan=solve_day2(price,{"L":L_all[i],"G":G_all[i]},s,{"beta":beta,"alpha":0.90,"kappa2":kappa2})
        st=settle_day(price,plan["x"],plan["c"],plan["r"],ds["load"][:,i],ds["pv"][:,i],s)
        s=float(st["s_actual"][T])
        logs.append({"cost_total":st["cost_total"],"cost_plan":st["cost_plan"],"cost_emergency":st["cost_emergency"],
                     "emergency_kwh":float(np.sum(st["e"])),"load_kwh":float(np.sum(ds["load"][:,i])),
                     "curtail_kwh":float(np.sum(st["w"])),"unextracted_kwh":float(np.sum(plan["x"]-st["y"]))})
    return logs

def main():
    os.makedirs(TABLES, exist_ok=True)
    ds=pickle.load(open(os.path.join(DATA_PROC,"q2_dataset.pkl"),"rb"))
    fc=pickle.load(open(os.path.join(DATA_PROC,"forecasts.pkl"),"rb"))
    res=pickle.load(open(os.path.join(DATA_PROC,"q2_rolling_results.pkl"),"rb"))
    report=res["report_logs"]
    dates=np.array(list(ds["dates"])); months=np.array([d.month for d in dates])

    # 全年汇总
    summary=pd.DataFrame([
        ["计划购电费(元)", res["plan_cost"]],
        ["紧急购电费(元)", res["emergency_cost"]],
        ["总费用(元)", res["total_cost"]],
        ["紧急购电量(kWh)", float(sum(l["emergency_kwh"] for l in report))],
        ["弃光量(kWh)", float(sum(l["curtail_kwh"] for l in report))],
        ["未提取计划量(kWh)", float(sum(l["unextracted_kwh"] for l in report))],
        ["紧急购电率(电量)", res["emergency_rate"]],
    ], columns=["指标","值"])
    with pd.ExcelWriter(os.path.join(TABLES,"annual_cost_summary.xlsx"), engine="openpyxl") as w:
        summary.to_excel(w,sheet_name="annual",index=False)

    # 月度预测指标（混合预测：load=v2, pv=v1）
    frows=[]
    for m in range(2,13):
        mask=months==m
        for name,err,act in (("load",np.abs(fc["Lhat"]-ds["load"]),ds["load"]),("pv",np.abs(fc["Ghat"]-ds["pv"]),ds["pv"])):
            frows.append([m,name,float(np.mean(err[:,mask])),float(np.sum(err[:,mask])/np.sum(np.abs(act[:,mask]))),int(mask.sum())])
    fdf=pd.DataFrame(frows,columns=["month","series","MAE_kwh","WAPE","n_days"])

    # 月度调度指标
    drows=[]
    for m in range(2,13):
        sub=[l for l in report if int(l["date"][5:7])==m]
        drows.append([m,len(sub),sum(l["cost_plan"] for l in sub),sum(l["cost_emergency"] for l in sub),sum(l["cost_total"] for l in sub),
                      sum(l["emergency_kwh"] for l in sub)/sum(l["load_kwh"] for l in sub),
                      sum(l["curtail_kwh"] for l in sub)/sum(l["load_kwh"] for l in sub)])
    ddf=pd.DataFrame(drows,columns=["month","n_days","plan_cost","emergency_cost","total_cost","emergency_rate","curtailment_rate"])
    with pd.ExcelWriter(os.path.join(TABLES,"monthly_metrics.xlsx"), engine="openpyxl") as w:
        fdf.to_excel(w,sheet_name="forecast",index=False); ddf.to_excel(w,sheet_name="dispatch",index=False)

    # 2月调参窗口 beta 网格（与正式运行同一套场景/预测，因果：只用 2 月窗口选参）
    L_all,G_all=build_scenarios(fc["Lhat"],fc["Ghat"],ds["load"],ds["pv"],window=30,M=20)
    # 重新计算 warmup 期末 SOC
    s=6000.0
    for i in range(1,31):
        price=ds["price"][:,i]
        plan=solve_day2(price,{"L":L_all[i],"G":G_all[i]},s,{"beta":0.5,"alpha":0.90,"kappa2":0.531667})
        st=settle_day(price,plan["x"],plan["c"],plan["r"],ds["load"][:,i],ds["pv"][:,i],s)
        s=float(st["s_actual"][T])
    s0_0201=s
    tune=list(range(31,59)); rows=[]
    for b in [0.0,0.005,0.01,0.02,0.03,0.05,0.1,0.2]:
        logs=roll(tune,s0_0201,b,L_all,G_all,ds,0.531667)
        cost=sum(l["cost_total"] for l in logs); ek=sum(l["emergency_kwh"] for l in logs); lk=sum(l["load_kwh"] for l in logs)
        rows.append([b,cost,ek/lk])
    tdf=pd.DataFrame(rows,columns=["beta","tuning_cost_total","tuning_emergency_rate"])
    tdf["cost_increase"]=tdf["tuning_cost_total"]/tdf.loc[tdf.beta==0,"tuning_cost_total"].iloc[0]-1
    tdf["selected"]=tdf.beta==0.01
    with pd.ExcelWriter(os.path.join(TABLES,"tuning_sensitivity.xlsx"), engine="openpyxl") as w:
        tdf.to_excel(w,sheet_name="beta",index=False)
    print("tables written", os.listdir(TABLES))

if __name__=="__main__":
    main()
