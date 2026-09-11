# -*- coding: utf-8 -*-
"""问题二 激进降本实验：点预测计划 + 计划购电量覆盖因子标定"""
import os, sys, time, pickle, json
import numpy as np
GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
BASE = os.path.join(GS, "All_Code", "Q2")
sys.path.insert(0, os.path.join(BASE, "Model_Establishment+Solution"))
from optimizer import solve_day2
from settlement import settle_day

DS = pickle.load(open(os.path.join(BASE,"Data_processing","q2_dataset.pkl"),"rb"))
FC = pickle.load(open(os.path.join(BASE,"Data_processing","forecasts.pkl"),"rb"))
SC = pickle.load(open(os.path.join(BASE,"Data_processing","scenarios_M20.pkl"),"rb"))
FULL = list(range(1,365))

def roll(beta, scenL, scenG, lam=1.0, lam_cr=1.0, kappa2=0.132917, verbose=True):
    s=6000.0; logs=[]; t0=time.time()
    for i in FULL:
        price=DS["price"][:,i]
        plan=solve_day2(price, {"L":scenL[i], "G":scenG[i]}, s, {"beta":beta,"alpha":0.90,"kappa2":kappa2})
        x=plan["x"]*lam
        c=plan["c"]*lam_cr
        r=plan["r"]*lam_cr
        st=settle_day(price, x, c, r, DS["load"][:,i], DS["pv"][:,i], s)
        s=float(st["s_actual"][144])
        logs.append({"day_index":i,"cost_plan":st["cost_plan"],"cost_emergency":st["cost_emergency"],
                     "cost_total":st["cost_total"],"emergency_kwh":float(np.sum(st["e"])),
                     "load_kwh":float(np.sum(DS["load"][:,i])),"curtail_kwh":float(np.sum(st["w"])),
                     "unextracted_kwh":float(np.sum(x-st["y"]))})
    logs=[l for l in logs if l["day_index"]>=31]
    a=dict(cost=sum(l["cost_total"] for l in logs), plan=sum(l["cost_plan"] for l in logs),
           emg_cost=sum(l["cost_emergency"] for l in logs),
           emg_rate=sum(l["emergency_kwh"] for l in logs)/sum(l["load_kwh"] for l in logs),
           emg_kwh=sum(l["emergency_kwh"] for l in logs), cur_kwh=sum(l["curtail_kwh"] for l in logs),
           une_kwh=sum(l["unextracted_kwh"] for l in logs), dt=round(time.time()-t0,1))
    if verbose: print(json.dumps(a, ensure_ascii=False), flush=True)
    return a

which=sys.argv[1] if len(sys.argv)>1 else "shrink"
out=os.path.join(GS, f"_opt_{which}.json")
results=[]
if which=="point":
    # M=1 point forecast (repeat to M=20? use single scenario; solver M=1)
    Lp=np.clip(FC["Lhat"].T[:,None,:],0,None); Gp=np.clip(FC["Ghat"].T[:,None,:],0,None)
    results.append({"label":"point_forecast_beta0","beta":0.0,"lam":1.0,**roll(0.0,Lp,Gp,1.0,1.0)})
elif which=="shrink":
    L=SC["L_all"]; G=SC["G_all"]
    for lam in [1.0,0.95,0.90,0.85,0.80,0.75,0.70]:
        a=roll(0.0,L,G,lam,1.0); a.update({"beta":0.0,"lam":lam}); results.append(a)
elif which=="shrink_cr":
    L=SC["L_all"]; G=SC["G_all"]
    for lam_cr in [1.0,0.9,0.8,0.7,0.6,0.5]:
        a=roll(0.0,L,G,1.0,lam_cr); a.update({"beta":0.0,"lam_cr":lam_cr}); results.append(a)
json.dump(results, open(out,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print("DONE", which)

