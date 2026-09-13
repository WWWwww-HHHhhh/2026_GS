# 附件3 那一格的数据可用性探查

## 1 Data_processing 下的 pkl 与相关文件

- `03_q4_dataset.py`  0.01 MB
- `04_q4_price_forecast.py`  0.01 MB
- `05_q4_scenarios.py`  0.01 MB
- `price_forecast.pkl`  0.83 MB
- `q4_2_rolling_results.pkl`  38.06 MB
- `q4_common.py`  0.01 MB
- `q4_dataset.pkl`  2.43 MB
- `scenario_demo_M10.csv`  0.09 MB
- `scenario_demo_M10_official.csv`  0.09 MB
- `scenario_demo_M10_q2.csv`  0.09 MB
- `scenario_demo_M20.csv`  0.19 MB
- `scenario_demo_M20_official.csv`  0.19 MB
- `scenario_demo_M20_q2.csv`  0.19 MB
- `scenario_demo_M30.csv`  0.28 MB
- `scenario_demo_M30_official.csv`  0.28 MB
- `scenario_demo_M30_q2.csv`  0.28 MB
- `scenarios_M10.pkl`  13.23 MB
- `scenarios_M10_official.pkl`  13.23 MB
- `scenarios_M10_q2.pkl`  13.23 MB
- `scenarios_M20.pkl`  25.26 MB
- `scenarios_M20_official.pkl`  25.26 MB
- `scenarios_M20_q2.pkl`  25.26 MB
- `scenarios_M30.pkl`  37.29 MB
- `scenarios_M30_official.pkl`  37.29 MB
- `scenarios_M30_q2.pkl`  37.29 MB

## 2 V_official_unknown_q2params_summary.csv 全字段

- `tag` = V_official_unknown_q2params
- `pv_source` = official
- `price_mode` = unknown
- `select_rule` = legacy
- `import_cap_kw` = nan
- `selected` = {'M': 30, 'beta': 0.2, 'kappa_mult': 1.0}
- `kappa2_base` = 0.5316666666666666
- `selected_M` = 30
- `selected_beta` = 0.2
- `selected_kappa_mult` = 1.0
- `report_days` = 334
- `report_total_cost` = 15728958.764653768
- `report_plan_cost` = 14762076.400236407
- `report_emergency_cost` = 966882.3644173744
- `report_emergency_kwh` = 242133.03046168108
- `report_load_kwh` = 37008079.48925
- `report_plan_kwh` = 22885559.264465027
- `report_unextracted_kwh` = 1763979.956266064
- `report_curtail_kwh` = 1938149.382715674
- `report_pv_kwh` = 19068889.99428332
- `cvar90_daily` = 79105.31960221527
- `max_daily` = 103954.57809343148
- `emergency_rate_pct` = 0.6542707262937413
- `final_soc` = 6000.000000000004
- `elapsed_sec` = 142.8991765975952
- `selection_period` = 2025-01-15..2025-01-31
- `state_origin` = 2025-01-01 00:00 SOC=6000 kWh

## 3 V_official_unknown_q2params_daily.csv 的列与首行

- 行数 334，列：day_index、date、s0、E_C、CVaR、cost_plan、cost_emergency、cost_total、emergency_rate、unextracted_ratio、curtailment_rate、soc_violate_count、emergency_kwh、load_kwh、pv_kwh、pv_used_kwh、curtail_kwh、unextracted_kwh、spill_kwh、plan_total_kwh、charge_kwh、discharge_kwh、final_soc、price_mean、eq_residual、ub_violation

```
 day_index       date     s0           E_C          CVaR     cost_plan  cost_emergency    cost_total  emergency_rate  unextracted_ratio  curtailment_rate  soc_violate_count  emergency_kwh      load_kwh      pv_kwh  pv_used_kwh  curtail_kwh  unextracted_kwh   spill_kwh  plan_total_kwh   charge_kwh  discharge_kwh  final_soc  price_mean  eq_residual  ub_violation
        31 2025-02-01 6000.0  23362.914814  29147.223233  21473.671061      440.185375  21913.856436        0.001462           0.111651          0.121281                  0     111.592299  76305.206283 41927.03035 36842.087086  5084.943264      5586.754102  914.321005    50037.857812 22027.662143   17842.406336     6000.0    0.651493 1.534772e-12  0.000000e+00
        32 2025-02-02 6000.0 108031.079068 128858.764438 103954.578093        0.000000 103954.578093        0.000000           0.322107          0.135874                  0       0.000000 121705.972650 43349.69470 37459.581993  5890.112707     43076.430293 1215.031250   133733.378007 27344.872668   22149.346861     6000.0    0.836388 2.273737e-13  1.455192e-11
```

## 4 主模型 daily 与它的差别（列对比）

- 主模型 daily 列：day_index、date、s0、E_C、CVaR、cost_plan、cost_emergency、cost_total、emergency_rate、unextracted_ratio、curtailment_rate、soc_violate_count、residual_blocks、emergency_kwh、load_kwh、pv_kwh、pv_used_kwh、curtail_kwh、unextracted_kwh、spill_kwh、plan_total_kwh、charge_kwh、discharge_kwh、final_soc、price_mean、price_hat_mean、eq_residual、ub_violation、settlement_method
- 仅主模型有：residual_blocks、price_hat_mean、settlement_method
- 仅该格有：无

## 5 变体脚本持久化了什么

- L22   python q4_2_variants.py --pv-source official --price-mode unknown --select risk_aware --tag V_official_unknown
- L24   Data_processing/variants/<tag>_results.pkl
- L25   Results/Tables/<tag>_tuning.xlsx、<tag>_daily.csv、<tag>_summary.csv
- L42   from q4_common import D, OUT_DATA, T, TABLES, load_dataset  # noqa: E402
- L59   p = OUT_DATA / f"scenarios_M{M}_{pv_source}.pkl"
- L85   save_detail=False, hard_terminal_day=None, tag=""):
- L137  if tag and n and n % 60 == 0:
- L138  print(f"      {tag} {ds['date_str'][i]} ({n}/{len(days)})", flush=True)
- L157  ap.add_argument("--tag", required=True)
- L171  outdir = OUT_DATA / "variants"
- L174  print(f"[{args.tag}] pv={args.pv_source} price={args.price_mode} "
- L179  price_mode=args.price_mode, x_cap=x_cap, tag=args.tag)
- L221  tune.to_excel(TABLES / f"{args.tag}_tuning.xlsx", index=False)
- L236  hard_terminal_day=D - 1, tag=args.tag)
- L240  "tag": args.tag, "pv_source": args.pv_source, "price_mode": args.price_mode,
- L260  with open(outdir / f"{args.tag}_results.pkl", "wb") as fh:
- L261  pickle.dump({"summary": summary, "report_logs": report_logs,
- L268  pd.DataFrame([{k: r[k] for k in scalar} for r in report_logs]).to_csv(
- L269  TABLES / f"{args.tag}_daily.csv", index=False, encoding="utf-8-sig")
- L270  pd.DataFrame([summary]).to_csv(TABLES / f"{args.tag}_summary.csv", index=False,
- L279  print(f"[{args.tag}] 失败：{exc}")

## 6 论文里 41.17/48.22/71.95 与 0.6433 是怎么算出来的

### q4_2_paper_numbers.py

- L31   timing = pd.read_csv(TABLES / "q4_2_timing_main_vs_b1.csv", encoding="utf-8-sig")
- L32   plan_t = pd.read_csv(TABLES / "q4_2_plan_timing.csv", encoding="utf-8-sig")
- L33   bands = pd.read_csv(TABLES / "q4_2_band_allocation.csv", encoding="utf-8-sig")
- L56   add("主模型", "其中计划购电费（元）", f"{plan_cost:,.2f}", "q4_2_plan_timing.csv")
- L58   add("主模型", "计划购电量（kWh）", f"{plan_kwh:,.2f}", "q4_2_plan_timing.csv")
- L60   add("主模型", "平均购电单价（元/kWh）", f"{plan_cost / plan_kwh:.4f}", "计划费 ÷ 计划量")
- L61   add("主模型", "计划量落在当日最便宜 25% 时段占比", f"{float(plan_t[plan_t['指标'].str.contains('最便宜 25%')]['数值'].iloc[0].rstrip('%')):.2f}%",
- L62   "q4_2_plan_timing.csv")
- L63   add("主模型", "紧急购电平均单价（元/kWh）", f"{emg_cost / emg_kwh:.4f}", "紧急费 ÷ 紧急量")
- L78   b1_plan = float(timing[timing["方案"].str.startswith("B1")]["计划购电费(实际波动价,元)"].iloc[0])
- L81   add("基线", "B1 计划购电费（元）", f"{b1_plan:,.2f}", "q4_2_timing_main_vs_b1.csv")
- L83   add("基线", "B1 平均购电单价（元/kWh）", f"{float(timing[timing['方案'].str.startswith('B1')]['平均购电单价(元/kWh)'].iloc[0]):.4f}",
- L84   "q4_2_timing_main_vs_b1.csv")
- L85   add("基线", "B1 紧急购电平均单价（元/kWh）", f"{b1_emg_cost / b1_emg_kwh:.4f}", "紧急费 ÷ 紧急量")

### q4_2_diagnostics.py

- L4    回答一个问题：Q4-2 的日前计划到底有没有把钱花在便宜的时候？
- L5    D1 平均购电单价 = Σλ_t x_t / Σx_t，与全年均价、当日均价对比；
- L6    D2 低价时段集中度：把当日 144 个时段按价格分成 4 档，统计计划量落在最便宜一档的占比
- L33   def timing_metrics(plans: list, price: np.ndarray, charges: list | None = None,
- L93   unext_band = np.zeros(4)   # 未提取量按当日价格档
- L94   emg_band = np.zeros(4)
- L95   curt_band = np.zeros(4)
- L104  q[order] = np.minimum(3, (np.arange(T) * 4) // T)   # 0=最便宜 25%，3=最贵 25%
- L112  unext_band[k] += float(un[q == k].sum())
- L113  emg_band[k] += float(e[q == k].sum())
- L114  curt_band[k] += float(w[q == k].sum())
- L120  ["平均购电单价（元/kWh）", f"{tot_plan_cost / tot_x:.4f}"],
- L125  ["计划量落在当日最便宜 25% 时段的占比（均匀=25%）",
- L127  ["充电量落在最便宜 25% 时段的占比", f"{np.nanmean(cheap_charge) * 100:.2f}%"],
- L128  ["放电量落在最贵 25% 时段的占比", f"{np.nanmean(expensive_discharge) * 100:.2f}%"],
- L130  band_df = pd.DataFrame({
- L131  "价格档（当日）": ["最便宜25%", "次便宜25%", "次贵25%", "最贵25%"],
- L132  "未提取计划量(kWh)": unext_band,
- L133  "紧急购电量(kWh)": emg_band,
- L134  "弃光量(kWh)": curt_band,
- L136  band_df["未提取占比(%)"] = band_df["未提取计划量(kWh)"] / band_df["未提取计划量(kWh)"].sum() * 100
- L137  band_df["紧急购电占比(%)"] = band_df["紧急购电量(kWh)"] / band_df["紧急购电量(kWh)"].sum() * 100
- L144  m1 = timing_metrics(bx, price, bc, br)
- L147  "计划购电费(实际波动价,元)": tot_plan_cost, "平均购电单价(元/kWh)": tot_plan_cost / tot_x,
- L148  "最便宜25%时段占比(%)": float(np.mean(cheap_share_all)) * 100,
- L149  "充电落在最便宜25%(%)": float(np.nanmean(cheap_charge)) * 100,
- L150  "放电落在最贵25%(%)": float(np.nanmean(expensive_discharge)) * 100},
- L152  "计划购电费(实际波动价,元)": m1["plan_cost"], "平均购电单价(元/kWh)": m1["avg_price"],
- L153  "最便宜25%时段占比(%)": m1["cheap_share"] * 100,
- L154  "充电落在最便宜25%(%)": m1["charge_cheap"] * 100,
- L155  "放电落在最贵25%(%)": m1["discharge_expensive"] * 100},
- L157  cmp_df.to_csv(TABLES / "q4_2_timing_main_vs_b1.csv", index=False, encoding="utf-8-sig")
- L162  TABLES / "q4_2_plan_timing.csv", index=False, encoding="utf-8-sig")
- L163  band_df.to_csv(TABLES / "q4_2_band_allocation.csv", index=False, encoding="utf-8-sig")
- L171  lines += ["", "## 分档分布（按当日价格四分位）", "",
- L174  for _, r in band_df.iterrows():
- L178  "1. 「平均购电单价 < 全年均价」的差额，就是日前计划**择时能力**的直接证据：",
- L180  "2. 「计划量落在最便宜 25% 时段的占比」与均匀投放的 25% 比较，量化集中度。",
- L182  "   时间对齐（在哪里买）与价格水平（单价高低）。前者由波动电价优化贡献，后者是市场给定的。",
- L183  "4. 紧急购电若集中在最贵档，说明价格高企时预测误差的代价被 5 倍罚价放大，"
- L187  "| 方案 | 计划购电量(kWh) | 计划购电费(元) | 平均购电单价(元/kWh) | 最便宜25%时段占比(%) | 充电落在最便宜25%(%) | 放电落在最贵25%(%) |",
- L191  f"{r['平均购电单价(元/kWh)']:.4f} | {r['最便宜25%时段占比(%)']:.2f} | "
- L192  f"{r['充电落在最便宜25%(%)']:.2f} | {r['放电落在最贵25%(%)']:.2f} |")
- L195  "若平均购电单价接近，说明该题结构下日内价格形状的可预测性很高，"
- L197  (TABLES / "q4_2_plan_timing_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
- L202  print(band_df.to_string(index=False))
- L203  print(f"\n  报告: {TABLES / 'q4_2_plan_timing_report.md'}")

### q4_2_rolling.py

