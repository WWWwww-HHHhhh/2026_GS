# 补充验证（紧急率口径 / 受控 2x2 / 默认参数）

## 1 紧急购电率到底是多少（论文写“日均紧急购电率 0.63%”）

- 逐日日志列名：day_index、date、s0、E_C、CVaR、cost_plan、cost_emergency、cost_total、emergency_rate、unextracted_ratio、curtailment_rate、soc_violate_count、residual_blocks、emergency_kwh、load_kwh、pv_kwh、pv_used_kwh、curtail_kwh、unextracted_kwh、spill_kwh、plan_total_kwh、charge_kwh、discharge_kwh、final_soc、price_mean、price_hat_mean、eq_residual、ub_violation、settlement_method
- 天数：334
- 紧急量列=emergency_kwh，负荷列=load_kwh
- 全年紧急购电量 217118.05 kWh，全年负荷 37008079.49 kWh
- **口径A 全年之和的比值 = 0.5867%**
- **口径B 逐日比值的平均 = 0.5812%**（中位数 0.3529%）

## 2 受控 2x2 四格与派生量

- `V_q2_unknown_q2params_summary.csv` 不存在
- **价格已知 + 自建预报**（V_q2_known_q2params_summary.csv）
  列：tag、pv_source、price_mode、select_rule、import_cap_kw、selected、kappa2_base、selected_M、selected_beta、selected_kappa_mult、report_days、report_total_cost、report_plan_cost、report_emergency_cost、report_emergency_kwh、report_load_kwh、report_plan_kwh、report_unextracted_kwh、report_curtail_kwh、report_pv_kwh、cvar90_daily、max_daily、emergency_rate_pct、final_soc、elapsed_sec、selection_period、state_origin
```
                tag pv_source price_mode select_rule  import_cap_kw                                  selected  kappa2_base  selected_M  selected_beta  selected_kappa_mult  report_days  report_total_cost  report_plan_cost  report_emergency_cost  report_emergency_kwh  report_load_kwh  report_plan_kwh  report_unextracted_kwh  report_curtail_kwh  report_pv_kwh  cvar90_daily    max_daily  emergency_rate_pct  final_soc  elapsed_sec       selection_period                  state_origin
V_q2_known_q2params        q2      known      legacy            NaN {'M': 30, 'beta': 0.2, 'kappa_mult': 1.0}     0.531667          30            0.2                  1.0          334       1.534527e+07      1.447123e
```
- **价格未知 + 附件3预报**（V_official_unknown_q2params_summary.csv）
  列：tag、pv_source、price_mode、select_rule、import_cap_kw、selected、kappa2_base、selected_M、selected_beta、selected_kappa_mult、report_days、report_total_cost、report_plan_cost、report_emergency_cost、report_emergency_kwh、report_load_kwh、report_plan_kwh、report_unextracted_kwh、report_curtail_kwh、report_pv_kwh、cvar90_daily、max_daily、emergency_rate_pct、final_soc、elapsed_sec、selection_period、state_origin
```
                        tag pv_source price_mode select_rule  import_cap_kw                                  selected  kappa2_base  selected_M  selected_beta  selected_kappa_mult  report_days  report_total_cost  report_plan_cost  report_emergency_cost  report_emergency_kwh  report_load_kwh  report_plan_kwh  report_unextracted_kwh  report_curtail_kwh  report_pv_kwh  cvar90_daily     max_daily  emergency_rate_pct  final_soc  elapsed_sec       selection_period                  state_origin
V_official_unknown_q2params  official    unknown      legacy            NaN {'M': 30, 'beta': 0.2, 'kappa_mult': 1.0}     0.531667          30            0.2                  1.0          334       1.572896e+
```
- **价格已知 + 附件3预报**（V_official_known_q2params_summary.csv）
  列：tag、pv_source、price_mode、select_rule、import_cap_kw、selected、kappa2_base、selected_M、selected_beta、selected_kappa_mult、report_days、report_total_cost、report_plan_cost、report_emergency_cost、report_emergency_kwh、report_load_kwh、report_plan_kwh、report_unextracted_kwh、report_curtail_kwh、report_pv_kwh、cvar90_daily、max_daily、emergency_rate_pct、final_soc、elapsed_sec、selection_period、state_origin
```
                      tag pv_source price_mode select_rule  import_cap_kw                                  selected  kappa2_base  selected_M  selected_beta  selected_kappa_mult  report_days  report_total_cost  report_plan_cost  report_emergency_cost  report_emergency_kwh  report_load_kwh  report_plan_kwh  report_unextracted_kwh  report_curtail_kwh  report_pv_kwh  cvar90_daily    max_daily  emergency_rate_pct  final_soc  elapsed_sec       selection_period                  state_origin
V_official_known_q2params  official      known      legacy            NaN {'M': 30, 'beta': 0.2, 'kappa_mult': 1.0}     0.531667          30            0.2                  1.0          334       1.550440e+07   
```


## 3 q4_core.py 里的默认参数

- 含 beta 的行 7 条：
  - L35   "beta": 0.5,
  - L68   alpha = float(p["alpha"]); beta = float(p["beta"]); eps = float(p["eps"])
  - L112  c_obj[ix[t]] += (1.0 - beta) * P_bar[t]     # ← Q2 为 (1-beta)*price[t]
  - L119  c_obj[scen_var(m, "e", t)] += (1.0 - beta) * 5.0 * prob * P[m, t]   # ← 逐场景
  - L120  c_obj[scen_var(m, "q")] += beta * (1.0 / (1.0 - alpha)) * prob
  - L121  c_obj[NZETA] = beta
  - L270  # than the auxiliary LP variables.  This remains meaningful when beta=0,

- q4_2_rolling.py 候选与基线：BETA_CAND = [0.0, 0.01, 0.03, 0.05, 0.10, 0.20, 0.25, 0.50] | BASELINE = {"M": 20, "beta": 0.25, "kappa_mult": 1.0}
