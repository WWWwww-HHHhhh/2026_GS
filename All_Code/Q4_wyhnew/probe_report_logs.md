# 附件3 那一格 report_logs 的完整结构

## 主模型

- 文件：`All_Code\Q4\Q4_wyh\Data_processing\q4_2_rolling_results.pkl`
- report_logs 长度 334，首元素键 45 个：

| 键 | 类型 | 形状/长度 | 样例 |
| --- | --- | --- | --- |
| `day_index` | int |  | 31 |
| `date` | str |  | 2025-02-01 |
| `s0` | float |  | 6000.000000000022 |
| `E_C` | float |  | 21780.600826784215 |
| `CVaR` | float |  | 26958.937918582982 |
| `cost_plan` | float |  | 20267.707175403302 |
| `cost_emergency` | float |  | 499.02528493191596 |
| `cost_total` | float |  | 20766.732460335217 |
| `emergency_rate` | float |  | 0.0016928696341611468 |
| `unextracted_ratio` | float |  | 0.09666246637856814 |
| `curtailment_rate` | float |  | 0.10678005081169072 |
| `soc_violate_count` | int |  | 0 |
| `residual_blocks` | int |  | 30 |
| `emergency_kwh` | float |  | 129.17476664545734 |
| `load_kwh` | float |  | 76305.20628333333 |
| `pv_kwh` | float |  | 41927.03035 |
| `pv_used_kwh` | float |  | 37450.05991884369 |
| `curtail_kwh` | float |  | 4476.970431156299 |
| `unextracted_kwh` | float |  | 4688.265342621203 |
| `spill_kwh` | float |  | 1008.4063083154606 |
| `plan_total_kwh` | float |  | 48501.40409474052 |
| `charge_kwh` | float |  | 21467.162347156234 |
| `discharge_kwh` | float |  | 17388.401501196546 |
| `final_soc` | float |  | 6000.000000000024 |
| `price_mean` | float |  | 0.6514930555555556 |
| `price_hat_mean` | float |  | 0.7007316944534063 |
| `eq_residual` | float |  | 9.094947017729282e-13 |
| `ub_violation` | float |  | 3.637978807091713e-12 |
| `settlement_method` | str |  | causal_sequential_exact_plan |
| `plan_x` | ndarray | (144,) | 1304.2156 |
| `plan_c` | ndarray | (144,) | 833.3333 |
| `plan_r` | ndarray | (144,) | 0.0000 |
| `plan_s` | ndarray | (145,) | 6000.0000 |
| `settle_y` | ndarray | (144,) | 1255.3637 |
| `settle_e` | ndarray | (144,) | 0.0000 |
| `settle_g` | ndarray | (144,) | 0.0000 |
| `settle_w` | ndarray | (144,) | 0.0000 |
| `settle_spill` | ndarray | (144,) | 0.0000 |
| `settle_s_actual` | ndarray | (145,) | 6000.0000 |
| `price` | ndarray | (144,) | 0.3281 |
| `load_actual` | ndarray | (144,) | 422.0304 |
| `pv_actual` | ndarray | (144,) | 0.0000 |
| `price_scen` | ndarray | (30, 144) | 0.3720 |
| `load_scen` | ndarray | (30, 144) | 473.7591 |
| `pv_scen` | ndarray | (30, 144) | 0.0000 |

- 其中序列型键：plan_x、plan_c、plan_r、plan_s、settle_y、settle_e、settle_g、settle_w、settle_spill、settle_s_actual、price、load_actual、pv_actual、price_scen、load_scen、pv_scen
- 长度为 144 的逐时段键：plan_x、plan_c、plan_r、settle_y、settle_e、settle_g、settle_w、settle_spill、price、load_actual、pv_actual

## 附件3 那一格

- 文件：`All_Code\Q4\Q4_wyh\Data_processing\variants\V_official_unknown_q2params_results.pkl`
- report_logs 长度 334，首元素键 39 个：

| 键 | 类型 | 形状/长度 | 样例 |
| --- | --- | --- | --- |
| `day_index` | int |  | 31 |
| `date` | str |  | 2025-02-01 |
| `s0` | float |  | 6000.0000000000055 |
| `E_C` | float |  | 23362.914814418295 |
| `CVaR` | float |  | 29147.223233457775 |
| `cost_plan` | float |  | 21473.67106075734 |
| `cost_emergency` | float |  | 440.18537498548665 |
| `cost_total` | float |  | 21913.856435742826 |
| `emergency_rate` | float |  | 0.001462446726388673 |
| `unextracted_ratio` | float |  | 0.11165054512467054 |
| `curtailment_rate` | float |  | 0.12128078762268717 |
| `soc_violate_count` | int |  | 0 |
| `emergency_kwh` | float |  | 111.59229913547324 |
| `load_kwh` | float |  | 76305.20628333333 |
| `pv_kwh` | float |  | 41927.03035 |
| `pv_used_kwh` | float |  | 36842.087086471685 |
| `curtail_kwh` | float |  | 5084.943263528309 |
| `unextracted_kwh` | float |  | 5586.754101537184 |
| `spill_kwh` | float |  | 914.3210051936136 |
| `plan_total_kwh` | float |  | 50037.85781161155 |
| `charge_kwh` | float |  | 22027.662142918867 |
| `discharge_kwh` | float |  | 17842.40633576428 |
| `final_soc` | float |  | 6000.000000000006 |
| `price_mean` | float |  | 0.6514930555555556 |
| `eq_residual` | float |  | 1.5347723092418164e-12 |
| `ub_violation` | float |  | 0.0 |
| `plan_x` | ndarray | (144,) | 1301.9068 |
| `plan_c` | ndarray | (144,) | 833.3333 |
| `plan_r` | ndarray | (144,) | 0.0000 |
| `plan_s` | ndarray | (145,) | 6000.0000 |
| `settle_y` | ndarray | (144,) | 1255.3637 |
| `settle_e` | ndarray | (144,) | 0.0000 |
| `settle_g` | ndarray | (144,) | 0.0000 |
| `settle_w` | ndarray | (144,) | 0.0000 |
| `settle_spill` | ndarray | (144,) | 0.0000 |
| `settle_s_actual` | ndarray | (145,) | 6000.0000 |
| `price` | ndarray | (144,) | 0.3281 |
| `load_actual` | ndarray | (144,) | 422.0304 |
| `pv_actual` | ndarray | (144,) | 0.0000 |

- 其中序列型键：plan_x、plan_c、plan_r、plan_s、settle_y、settle_e、settle_g、settle_w、settle_spill、settle_s_actual、price、load_actual、pv_actual
- 长度为 144 的逐时段键：plan_x、plan_c、plan_r、settle_y、settle_e、settle_g、settle_w、settle_spill、price、load_actual、pv_actual
