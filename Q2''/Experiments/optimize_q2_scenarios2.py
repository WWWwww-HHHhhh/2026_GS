# -*- coding: utf-8 -*-
"""场景生成变体回测 v2"""
import os, sys, time, pickle, json
import numpy as np
GS=r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
BASE=os.path.join(GS,"All_Code","Q2")
sys.path.insert(0,os.path.join(BASE,"Model_Establishment+Solution"))
from optimizer import solve_day2
from settlement import settle_day

DS=pickle.load(open(os.path.join(BASE,"Data_processing","q2_dataset.pkl"),"rb"))
FC=pickle.load(open(os.path.join(BASE,"Data_processing","forecasts.pkl"),"rb"))
T,D=144,365
load=DS["load"]; pv=DS["pv"]; Lhat=FC["Lhat"]; Ghat=FC["Ghat"]
doy=np.array([d.timetuple().tm_yday for d in DS["dates"]],dtype=int)

def build_scenarios(M=20,window=None,doy_span=None,gamma=1.0,seed=20260101):
    L_all=np.zeros((D,M,T)); G_all=np.zeros((D,M,T)); blocks=[]
    for i in range(D):
        if window is not None:
            avail=[b for b in blocks if b[0]>=max(1,i-window)]
        elif doy_span is not None:
            avail=[]
            for b in blocks:
                dd=min(abs(doy[b[0]]-doy[i]),365-abs(doy[b[0]]-doy[i]))
                if dd<=doy_span: avail.append(b)
        else:
            avail=blocks
        if len(avail)==0:
            L_scen=np.tile(np.clip(Lhat[:,i],0,None),(M,1)); G_scen=np.tile(np.clip(Ghat[:,i],0,None),(M,1))
        else:
            rng=np.random.default_rng(seed*1000+i)
            idx=rng.integers(0,len(avail),size=M)
            L_res=np.vstack([avail[j][1] for j in idx]); G_res=np.vstack([avail[j][2] for j in idx])
            L_scen=np.clip(Lhat[:,i][None,:]+gamma*L_res,0,None)
            G_scen=np.clip(Ghat[:,i][None,:]+gamma*G_res,0,None)
        L_all[i]=L_scen; G_all[i]=G_scen
        if i>=1: blocks.append((i, load[:,i]-Lhat[:,i], pv[:,i]-Ghat[:,i]))
    return L_all,G_all

def roll(L_all,G_all,beta=0.0,kappa2=0.132917):
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

variants=[]
for name,kw,beta in [
    ("seasonal30",dict(doy_span=30),0.0),
    ("seasonal45",dict(doy_span=45),0.0),
    ("all_gamma0.9",dict(gamma=0.9),0.0),
    ("all_gamma0.8",dict(gamma=0.8),0.0),
    ("recent30_gamma0.9",dict(window=30,gamma=0.9),0.0),
    ("recent30_beta0.01",dict(window=30),0.01),
    ("recent30_beta0.02",dict(window=30),0.02),
    ("recent30_beta0.03",dict(window=30),0.03),
]:
    t0=time.time(); L,G=build_scenarios(20,**kw); a=roll(L,G,beta=beta); a["variant"]=name; a["build_dt"]=round(time.time()-t0,1); variants.append(a)
    print("variant",name,"build+roll",round(time.time()-t0,1),flush=True)
json.dump(variants,open(os.path.join(GS,"_opt_scenarios2.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("DONE")
