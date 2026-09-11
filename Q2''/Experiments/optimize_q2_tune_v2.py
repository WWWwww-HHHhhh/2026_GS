# -*- coding: utf-8 -*-
"""v2预测+近30天场景 的 2月调参窗口 β 选择"""
import os, sys, time, pickle, json
import numpy as np
GS=r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
BASE=os.path.join(GS,"All_Code","Q2"); Q2P=os.path.join(GS,"Q2''")
sys.path.insert(0,os.path.join(BASE,"Model_Establishment+Solution"))
from optimizer import solve_day2
from settlement import settle_day
DS=pickle.load(open(os.path.join(BASE,"Data_processing","q2_dataset.pkl"),"rb"))
FC=pickle.load(open(os.path.join(Q2P,"Data_processing","forecasts_v2.pkl"),"rb"))
T,D=144,365; load=DS["load"]; pv=DS["pv"]; Lhat=FC["Lhat"]; Ghat=FC["Ghat"]

def build(window=30,M=20,seed=20260101):
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
    return L_all,G_all
L,G=build()
print("scenarios built", flush=True)

def roll(days,s0,beta,kappa2=0.132917):
    s=float(s0); logs=[]
    for i in days:
        price=DS["price"][:,i]
        plan=solve_day2(price,{"L":L[i],"G":G[i]},s,{"beta":beta,"alpha":0.90,"kappa2":kappa2})
        st=settle_day(price,plan["x"],plan["c"],plan["r"],load[:,i],pv[:,i],s)
        s=float(st["s_actual"][144])
        logs.append({"cost_total":st["cost_total"],"cost_plan":st["cost_plan"],"cost_emergency":st["cost_emergency"],
                     "emergency_kwh":float(np.sum(st["e"])),"load_kwh":float(np.sum(load[:,i]))})
    return logs,s

# warmup with beta=0.5
logs_w,s0_0201=roll(list(range(1,31)),6000.0,0.5,0.132917)
print("warmup final s0_0201",s0_0201, flush=True)
tune=list(range(31,59))
rows=[]
for b in [0.0,0.005,0.01,0.02,0.03,0.05,0.1,0.2]:
    logs,_=roll(tune,s0_0201,b,0.132917)
    cost=sum(l["cost_total"] for l in logs); ek=sum(l["emergency_kwh"] for l in logs); lk=sum(l["load_kwh"] for l in logs)
    rows.append([b,cost,ek/lk])
    print(json.dumps({"beta":b,"tune_cost":cost,"tune_emg_rate":ek/lk},ensure_ascii=False),flush=True)
json.dump(rows,open(os.path.join(GS,"_opt_tune_v2.json"),"w"),ensure_ascii=False,indent=2)
print("DONE")
