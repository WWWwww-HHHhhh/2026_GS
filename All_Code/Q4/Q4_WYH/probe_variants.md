# variants 目录与逐时段数据探查

## 1 `All_Code\Q4\Q4_wyh\Data_processing\variants`

- `V_cap8000_results.pkl`  4.98 MB
- `V_official_known_q2params_results.pkl`  4.98 MB
- `V_official_known_results.pkl`  4.99 MB
- `V_official_unknown_q2params_results.pkl`  4.98 MB
- `V_official_unknown_results.pkl`  4.99 MB
- `V_q2_known_q2params_results.pkl`  4.98 MB
- `V_q2_known_results.pkl`  4.99 MB
- `V_q2_unknown_risk_results.pkl`  4.99 MB

## 2 主模型滚动结果的结构（作为对照，看有哪些键）

- 已导入 load_pickle_compat

### 主模型 q4_2_rolling_results.pkl

- 顶层键：problem、params、kappa2_base、selection_period、report_period、state_origin、terminal_constraint、baseline_config_for_eligibility、full_logs、report_logs、tuning、elapsed_sec
  - `problem`：str
  - `params`：dict
  - `kappa2_base`：float
  - `selection_period`：str
  - `report_period`：str
  - `state_origin`：str
  - `terminal_constraint`：str
  - `baseline_config_for_eligibility`：dict
  - `full_logs`：list len=365 首元素键=day_index、date、s0、E_C、CVaR、cost_plan、cost_emergency、cost_total、emergency_rate、unextracted_ratio、curtailment_rate、soc_violate_count
  - `report_logs`：list len=334 首元素键=day_index、date、s0、E_C、CVaR、cost_plan、cost_emergency、cost_total、emergency_rate、unextracted_ratio、curtailment_rate、soc_violate_count
  - `tuning`：DataFrame shape=(96, 11)
  - `elapsed_sec`：float

### 变体 V_official_known_q2params_results.pkl

- 顶层键：summary、report_logs、tuning、params、kappa2_base
  - `summary`：dict
  - `report_logs`：list len=334 首元素键=day_index、date、s0、E_C、CVaR、cost_plan、cost_emergency、cost_total、emergency_rate、unextracted_ratio、curtailment_rate、soc_violate_count
  - `tuning`：DataFrame shape=(0, 0)
  - `params`：dict
  - `kappa2_base`：float

### 变体 V_official_known_results.pkl

- 顶层键：summary、report_logs、tuning、params、kappa2_base
  - `summary`：dict
  - `report_logs`：list len=334 首元素键=day_index、date、s0、E_C、CVaR、cost_plan、cost_emergency、cost_total、emergency_rate、unextracted_ratio、curtailment_rate、soc_violate_count
  - `tuning`：DataFrame shape=(96, 10)
  - `params`：dict
  - `kappa2_base`：float

### 变体 V_official_unknown_q2params_results.pkl

- 顶层键：summary、report_logs、tuning、params、kappa2_base
  - `summary`：dict
  - `report_logs`：list len=334 首元素键=day_index、date、s0、E_C、CVaR、cost_plan、cost_emergency、cost_total、emergency_rate、unextracted_ratio、curtailment_rate、soc_violate_count
  - `tuning`：DataFrame shape=(0, 0)
  - `params`：dict
  - `kappa2_base`：float

### 变体 V_official_unknown_results.pkl

- 顶层键：summary、report_logs、tuning、params、kappa2_base
  - `summary`：dict
  - `report_logs`：list len=334 首元素键=day_index、date、s0、E_C、CVaR、cost_plan、cost_emergency、cost_total、emergency_rate、unextracted_ratio、curtailment_rate、soc_violate_count
  - `tuning`：DataFrame shape=(96, 10)
  - `params`：dict
  - `kappa2_base`：float
