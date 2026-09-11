# -*- coding: utf-8 -*-
"""kappa2 扫描：v2 load + 原版 pv, w30, M20"""
import os, sys, time, pickle, json
import numpy as np
GS=r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
BASE=os.path.join(GS,"All_Code","Q2"); Q2P=os.path.join(GS,"Q2''")
sys.path.insert(0,os.path.join(BASE,"Model_Establishment+Solution"))
from optimizer import solve_day2
from settlement import settle_day
DS=pickle.load(open(os.path.join(BASE,"Data_processing","q2_dataset.pkl"),"rb"))
FCv2=pickle.load(open(os.path.join(Q2P,"Data_processing","forecasts_v2.pkl"),"rb"))
FCo=pickle.load(open(os.path.join(BASE,"Data_processing","forecasts.pkl"),"rb"))
T,D=144,365; load=DS["load"]; pv=DS["pv"]; Lhat=FCv2["Lhat"]; Ghat=FCo["Ghat"]

def run(beta,kappa2):
    M=20; window=30; seed=20260101
    L_all=np.zeros((D,M,T)); G_all=np.zeros((D,M,T)); blocks=[]
    for i in range(D):
        avail=[b for b in blocks if b[0]>=max(1,i-window)]
        if len(avail)==0:
            L_scen=np.tile(np.clip(Lhat[:,i],0,None),(M,1)); G_scen=np.tile(np.clip(Ghat[:,i],0,None),(M,1))
        else:
            rng=np.random.default_rng(seed*1000+i); idx=rng.integers(0,len(avail),size=M)
            L_res=np.vstack([avail[j][1] for j in idx]); G_res=np.vstack([avail[j][2] for j in idx])
            L_scen=np.clip(Lhat[:,i][None,:]+L_res,0,None); G_scen=np.clip(Ghat[:,i][None,:]+G_res,0,None)
        L_all[i]=L_scen; G_all[i]=G_scen
        if i>=1: blocks.append((i,load[:,i]-Lhat[:,i],pv[:,i]-Ghat[:,i]))
    s=6000.0; logs=[]; t0=time.time()
    for i in range(1,D):
        price=DS["price"][:,i]
        plan=solve_day2(price,{"L":L_all[i],"G":G_all[i]},s,{"beta":beta,"alpha":0.90,"kappa2":kappa2})
        st=settle_day(price,plan["x"],plan["c"],plan["r"],load[:,i],pv[:,i],s)
        s=float(st["s_actual"][144])
        logs.append({"day_index":i,"cost_plan":st["cost_plan"],"cost_emergency":st["cost_emergency"],"cost_total":st["cost_total"],
                     "emergency_kwh":float(np.sum(st["e"])),"load_kwh":float(np.sum(load[:,i])),
                     "curtail_kwh":float(np.sum(st["w"])),"unextracted_kwh":float(np.sum(plan["x"]-st["y"]))})
    logs=[l for l in logs if l["day_index"]>=31]
    a=dict(cost=sum(l["cost_total"] for l in logs),plan=sum(l["cost_plan"] for l in logs),emg_cost=sum(l["cost_emergency"] for l in logs),
           emg_rate=sum(l["emergency_kwh"] for l in logs)/sum(l["load_kwh"] for l in logs),emg_kwh=sum(l["emergency_kwh"] for l in logs),
           cur_kwh=sum(l["curtail_kwh"] for l in logs),une_kwh=sum(l["unextracted_kwh"] for l in logs),dt=round(time.time()-t0,1))
    print(json.dumps(a,ensure_ascii=False),flush=True); return a

results=[]
for k in [0.531667,1.063333,2.0,5.0,10.0,20.0]:
    a=run(0.01,k); a.update(kappa2=k); results.append(a); print("kappa",k,flush=True)
# also beta=0.005 with kappa=1.063333
a=run(0.005,1.063333); a.update(kappa2=1.063333,beta=0.005); results.append(a); print("beta0.005 kappa1.063333",flush=True)
json.dump(results,open(os.path.join(GS,"_opt_kappa.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("DONE")
