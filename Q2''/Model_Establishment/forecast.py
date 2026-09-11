# -*- coding: utf-8 -*-
"""Q2'' 预测模块：负荷用 v2 特征，光伏用 v1 特征，逐日按前一日 WAPE 选择模型。全部因果。"""
import os, pickle, time
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor

GS = r"E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS"
Q2P = os.path.join(GS, "Q2''")
DATA_PROC = os.path.join(Q2P, "Data_processing")
TABLES = os.path.join(Q2P, "Results", "Tables")
T, D = 144, 365
SEED = 20260101
RIDGE_ALPHA = 10.0
GBM_V2 = dict(max_iter=250, max_depth=4, learning_rate=0.08, min_samples_leaf=20, l2_regularization=1.0, random_state=SEED)
GBM_V1 = dict(max_iter=100, max_depth=3, learning_rate=0.1, min_samples_leaf=20, l2_regularization=1.0, random_state=SEED)

def build_features_v1(Z, dates):
    n=Z.shape[1]; rows=[]
    for d in range(n):
        dow=dates[d].weekday(); doy=dates[d].timetuple().tm_yday
        for t in range(T):
            lag1=Z[t,d-1] if d-1>=0 else Z[t,0]
            lag7=Z[t,max(0,d-7)]
            hist=Z[t,max(0,d-7):d]
            rm=float(np.mean(hist)) if hist.size else Z[t,0]
            rs=float(np.std(hist)) if hist.size>=2 else 0.0
            rows.append([float(t+1),float(dow),float(doy),float(lag1),float(lag7),rm,rs])
    return np.asarray(rows,float)

def build_features_v2(Z, dates):
    n=Z.shape[1]; rows=[]
    for d in range(n):
        dow=dates[d].weekday(); doy=dates[d].timetuple().tm_yday
        prev=float(np.mean(Z[:,d-1])) if d-1>=0 else float(np.mean(Z[:,0]))
        for t in range(T):
            lag1=Z[t,d-1] if d-1>=0 else Z[t,0]
            lag2=Z[t,d-2] if d-2>=0 else Z[t,0]
            lag3=Z[t,d-3] if d-3>=0 else Z[t,0]
            lag7=Z[t,max(0,d-7)]
            lag14=Z[t,max(0,d-14)]
            h7=Z[t,max(0,d-7):d]; h14=Z[t,max(0,d-14):d]
            rm7=float(np.mean(h7)) if h7.size else Z[t,0]
            rs7=float(np.std(h7)) if h7.size>=2 else 0.0
            rm14=float(np.mean(h14)) if h14.size else Z[t,0]
            ph=t/T
            rows.append([ph,np.sin(2*np.pi*ph),np.cos(2*np.pi*ph),float(dow),float(1 if dow>=5 else 0),
                         float(doy),np.sin(2*np.pi*doy/365.0),np.cos(2*np.pi*doy/365.0),
                         float(lag1),float(lag2),float(lag3),float(lag7),float(lag14),rm7,rs7,rm14,prev])
    return np.asarray(rows,float)

def _slice_tr(X,u): return X[:(u+1)*T] if u>=0 else X[:0]
def _slice_day(X,d): return X[d*T:(d+1)*T]
def seasonal(Z,u,pred): return np.zeros(T) if u<0 else np.nanmedian(Z[:,:u+1],axis=1)
def wape(p,a):
    den=float(np.sum(np.abs(a)))
    return 0.0 if den==0 and float(np.sum(np.abs(p)))==0 else (np.inf if den==0 else float(np.sum(np.abs(p-a))/den))

def choose_and_predict(i,Z,X,gbm_params,ridge_alpha=RIDGE_ALPHA):
    if i==0: return np.zeros(T), "seasonal_naive", None
    vu=i-2; vd=i-1; yv=Z[:,vd]; Xv=_slice_day(X,vd)
    scores={"seasonal_naive": wape(seasonal(Z,vu,vd),yv) if vu>=0 else np.inf}
    Xtr=_slice_tr(X,vu)
    if vu>=0 and Xtr.shape[0]>0:
        ytr=Z[:,:vu+1].T.reshape(-1)
        for name in ("ridge","gbm"):
            try:
                m=Ridge(alpha=ridge_alpha,random_state=SEED) if name=="ridge" else HistGradientBoostingRegressor(**gbm_params)
                m.fit(Xtr,ytr); scores[name]=wape(m.predict(Xv),yv)
            except Exception: scores[name]=np.inf
    else: scores["ridge"]=scores["gbm"]=np.inf
    finite={k:v for k,v in scores.items() if np.isfinite(v)}
    sel=min(finite,key=finite.get) if finite else "seasonal_naive"
    if sel=="seasonal_naive": pred=seasonal(Z,i-1,i)
    else:
        try:
            m=Ridge(alpha=RIDGE_ALPHA,random_state=SEED) if sel=="ridge" else HistGradientBoostingRegressor(**gbm_params)
            m.fit(_slice_tr(X,i-1), Z[:,:i].T.reshape(-1)); pred=m.predict(_slice_day(X,i))
        except Exception: pred=seasonal(Z,i-1,i); sel="seasonal_naive"
    return np.asarray(pred,float), sel, float(finite[sel]) if finite else None

def run_forecast():
    t0=time.time(); os.makedirs(DATA_PROC,exist_ok=True); os.makedirs(TABLES,exist_ok=True)
    ds=pickle.load(open(os.path.join(DATA_PROC,"q2_dataset.pkl"),"rb"))
    dates=list(ds["dates"]); Zl=ds["load"].astype(float); Zg=ds["pv"].astype(float)
    Xl=build_features_v2(Zl,dates); Xg=build_features_v1(Zg,dates)
    Lhat=np.zeros((T,D)); Ghat=np.zeros((T,D)); rec=[]
    for i in range(D):
        if i==0:
            Lhat[:,0]=Ghat[:,0]=0.0
            rec += [[dates[0],"load","seasonal_naive",None,1],[dates[0],"pv","seasonal_naive",None,1]]
            continue
        pl,sl,wl=choose_and_predict(i,Zl,Xl,GBM_V2,10.0)
        pg,sg,wg=choose_and_predict(i,Zg,Xg,GBM_V1,1.0)
        Lhat[:,i]=pl; Ghat[:,i]=pg; warm=1 if dates[i].month==1 else 0
        rec += [[dates[i],"load",sl,wl,warm],[dates[i],"pv",sg,wg,warm]]
        if i%30==0 or i==D-1: print(f"  {dates[i]} i={i} ({time.time()-t0:.0f}s)",flush=True)
    val=pd.DataFrame(rec,columns=["date","series","selected_model","validation_wape","is_warmup"])
    val.to_csv(os.path.join(TABLES,"forecast_validation.csv"),index=False,encoding="utf-8-sig")
    months=np.array([d.month for d in dates]); rows=[]
    for m in range(2,13):
        mask=months==m
        for name,err,act in (("load",np.abs(Lhat-Zl),Zl),("pv",np.abs(Ghat-Zg),Zg)):
            rows.append([m,name,float(np.mean(err[:,mask])),float(np.sum(err[:,mask])/np.sum(np.abs(act[:,mask]))),int(mask.sum())])
    mdf=pd.DataFrame(rows,columns=["month","series","MAE_kwh","WAPE","n_days"])
    mdf.to_csv(os.path.join(TABLES,"forecast_monthly_metrics.csv"),index=False,encoding="utf-8-sig")
    out={"Lhat":Lhat,"Ghat":Ghat,"dates":np.array(dates,dtype=object),"selected_models":val,"monthly_metrics":mdf}
    pickle.dump(out,open(os.path.join(DATA_PROC,"forecasts.pkl"),"wb"),protocol=pickle.HIGHEST_PROTOCOL)
    print("DONE forecast",time.time()-t0,"s",flush=True); return out

if __name__=="__main__":
    run_forecast()
