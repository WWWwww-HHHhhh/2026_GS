# -*- coding: utf-8 -*-
"""近期窗口 + 残差缩尺 + 小beta 精细网格"""
import os, sys, time, pickle, json
import numpy as np
GS=r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
BASE=os.path.join(GS,"All_Code","Q2")
sys.path.insert(0,os.path.join(BASE,"Model_Establishment+Solution"))
from optimizer import solve_day2
from settlement import settle_day
DS=pickle.load(open(os.path.join(BASE,"Data_processing","q2_dataset.pkl"),"rb"))
FC=pickle.load(open(os.path.join(BASE,"Data_processing","forecasts.pkl"),"rb"))
T,D=144,365; load=DS["load"]; pv=DS["pv"]; Lhat=FC["Lhat"]; Ghat=FC["Ghat"]

def build(window,gamma,M=20,seed=20260101):
    L_all=np.zeros((D,M,T)); G_all=np.zeros((D,M,T)); blocks=[]
    for i in range(D):
        avail=[b for b in blocks if b[0]>=max(1,i-window)]
        if len(avail)==0:
            L_scen=np.tile(np.clip(Lhat[:,i],0,None),(M,1)); G_scen=np.tile(np.clip(Ghat[:,i],0,None),(M,1))
        else:
            rng=np.random.default_rng(seed*1000+i); idx=rng.integers(0,len(avail),size=M)
            L_res=np.vstack([avail[j][1] for j in idx]); G_res=np.vstack([avail[j][2] for j in idx])
            L_scen=np.clip(Lhat[:,i][None,:]+gamma*L_res,0,None); G_scen=np.clip(Ghat[:,i][None,:]+gamma*G_res,0,None)
        L_all[i]=L_scen; G_all[i]=G_scen
        if i>=1: blocks.append((i,load[:,i]-Lhat[:,i],pv[:,i]-Ghat[:,i]))
    return L_all,G_all

def roll(L_all,G_all,beta):
    s=6000.0; logs=[]
    for i in range(1,D):
        price=DS["price"][:,i]
        plan=solve_day2(price,{"L":L_all[i],"G":G_all[i]},s,{"beta":beta,"alpha":0.90,"kappa2":0.132917})
        st=settle_day(price,plan["x"],plan["c"],plan["r"],load[:,i],pv[:,i],s)
        s=float(st["s_actual"][144])
        logs.append({"day_index":i,"cost_plan":st["cost_plan"],"cost_emergency":st["cost_emergency"],"cost_total":st["cost_total"],
                     "emergency_kwh":float(np.sum(st["e"])),"load_kwh":float(np.sum(load[:,i])),
                     "curtail_kwh":float(np.sum(st["w"])),"unextracted_kwh":float(np.sum(plan["x"]-st["y"]))})
    logs=[l for l in logs if l["day_index"]>=31]
    a=dict(cost=sum(l["cost_total"] for l in logs),plan=sum(l["cost_plan"] for l in logs),emg_cost=sum(l["cost_emergency"] for l in logs),
           emg_rate=sum(l["emergency_kwh"] for l in logs)/sum(l["load_kwh"] for l in logs),emg_kwh=sum(l["emergency_kwh"] for l in logs),
           cur_kwh=sum(l["curtail_kwh"] for l in logs),une_kwh=sum(l["unextracted_kwh"] for l in logs))
    print(json.dumps(a,ensure_ascii=False),flush=True); return a

cache={}
def scen(window,gamma):
    key=(window,gamma)
    if key not in cache:
        cache[key]=build(window,gamma)
    return cache[key]

variants=[]
for window,gamma,beta in [
    (30,0.9,0.0),(30,0.9,0.01),(30,0.9,0.02),(30,0.9,0.03),
    (30,0.95,0.01),(30,0.95,0.02),
    (45,0.9,0.01),(45,0.9,0.02),
]:
    t0=time.time(); L,G=scen(window,gamma); a=roll(L,G,beta); a.update(variant=f"w{window}_g{gamma}_b{beta}",dt=round(time.time()-t0,1)); variants.append(a)
    print("variant",a["variant"],"dt",a["dt"],flush=True)
json.dump(variants,open(os.path.join(GS,"_opt_scenarios3.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("DONE")
