# Q2 → Q3 数据同步与自动修改交接报告

- 生成时间: 2026-09-11 22:08:46
- 源 Git 提交: `131fe990fb2935af255356a00d9d5c6b24405e5b`（本地工作区，未 push）
- 总体结论: **完成：15 项自动校验全部 PASS**

## 1. beta 核验

- 状态: **CONFIRMED**
- 证据 1: `All_Code/Q2/Results/Tables/result2.xlsx` 的 SHA256 = `cfd33c2304096244d27c9575d7bc4335fc052f22158403334fbe4d428e994bf6`，与 result2(7).xlsx 的给定哈希 `cfd33c2304096244d27c9575d7bc4335fc052f22158403334fbe4d428e994bf6` 完全一致。
- 证据 2: 旧缓存 `q2_rolling_results.pkl` 复算 6 个汇总值（计划购电总量/计划购电费/充电量/放电量/紧急购电量/紧急购电记录数）与提示词给定值一致（最大误差 < 1e-6），判定该缓存与 result2(7) 同一次运行。
- 同一次运行参数: beta=0.25, M=20, kappa2=0.132917, alpha=0.9。
- 说明: `run_summary.txt` 中 beta=0.0/M=30 是更早运行的过期记录，不作为 result2(7) 的参数依据。

## 2. 结算修改（M_PLAN 问题）

- `settlement.py` 正式结算改为词典序两阶段：第一阶段 `min sum(5*pi*e)`；第二阶段在紧急购电费不超过第一阶段最优值+容差的前提下最大化计划充放电执行量。
- `M_PLAN=20` 加权目标已从正式结算移除，保留为 `settle_day_weighted_legacy()`，仅用于历史对比。
- 重滚报告期最大紧急购电费差 = 2.262e-05 元，最大容差 = 2.262e-05 元，全部天数满足 gap <= tol + 1e-6。

## 3. 词典序重滚与重新调参

- 从 2025-01 预热期（i=1..30，基准参数 beta=0.5/kappa2_base）重新滚动，02-01 期初 SOC 重新产生；耗时 148.3 秒。
- 重新调参结果: beta=0.25, M=20, kappa2=1.063333 (kappa2_base=0.531667), alpha=0.9, seed=20260101。
- result2(7) 同次运行参数为 beta=0.25/M=20；若重调参后参数发生变化，论文 F1/F2 的参数结论必须按本报告更新，不得沿用旧调参结果。

## 4. 新旧 result2 差异

| 指标 | result2(7)（M_PLAN 加权结算） | 词典序重滚修正版（Q3） |
|---|---:|---:|
| 计划购电总量 kWh | 23473108.29 | 23463854.67 |
| 计划购电费 元 | 14797743.37 | 14781208.04 |
| 充电量 kWh | 6783239.01（计划口径） | 6706101.97（实际口径） |
| 放电量 kWh | 5502760.79（计划口径） | 5430488.91（实际口径） |
| 紧急购电量 kWh | 221843.74 | 164348.37 |
| 紧急购电记录数 | 3421 | 3180 |
| 报告期总费用 元 | — | 15454380.99 |
| 报告期紧急购电率(电量) | — | 0.004441 |

注：旧表充放电量为计划轨迹（plan_c/plan_r），修正版统一改为实际执行轨迹（settle_c_actual/r_actual/s_actual），两者口径不同，不能直接相减比较。

## 5. 时间列问题

- result2 宽表第 2..145 列包含“本日 t=2..144 + 次日 t=1”，而“全天购电量”列是本日 t=1..144 之和，两者天然不相等（如 2025-02-01 差 +117.24 kWh、2025-05-10 差 +1012.44 kWh、2025-12-31 差 -1464.30 kWh，与提示词一致）。
- Q3 接口不通过移动 Excel 列或跨日拼接恢复逐时计划；全部使用内部 `plan_x` 等长表，主键为 `date + interval_index`。
- 项目当前时间约定不变：`interval_index=1..144`，t=1 对应真实 00:00-00:10，t=144 对应 23:50-24:00；附件时间标签为区间结束时刻。

## 6. Q3 接口文件与行数

| 文件 | 行数 | 主键 |
|---|---:|---|
| q2_forecast_10min.csv | 52560 | date+interval_index |
| q2_residual_blocks.csv | 52416 | date+interval_index |
| q2_scenario_manifest.csv | 7280 | target_date+scenario_id |
| q2_plan_reference_long.csv | 48096 | date+interval_index |
| q2_parameters.json | 1 | — |

场景因果检查：manifest 中所有非空 source_residual_date 均严格早于 target_date，source_day_index < target_day_index；残差池为空（i=1）时 source 留空并记为点预测场景。

- 光伏预测物理截断：0 点光伏预测（GBM）出现 14745 个负值格（最大幅度 8.277 kWh，夜间时段），接口中统一截断到 0（与 scenarios.py 的物理截断规则一致）；残差文件同步按截断后预测计算，因此 Q3 重建场景值与原滚动完全一致，不产生数据造假。

## 7. 可供 Q3 使用的数值 / 不能写入论文的数值

- 可用: q2_forecast_10min.csv（负荷预测与 0 点光伏预测）、q2_residual_blocks.csv、q2_scenario_manifest.csv（重建联合误差场景）、q2_parameters.json（核验参数）、Q2_result2_corrected_for_Q3.xlsx（仅结果对照）。
- 仅作交叉核对: q2_plan_reference_long.csv（Q3 零点计划必须按附件 3 的 0 点光伏预报重新求解，不得直接复制 Q2 的 plan_x）。
- 不可使用: 旧缓存中 M_PLAN 加权结算的 settle_* 轨迹、run_summary.txt 的 beta=0.0/M=30 过期参数、result2 宽表的逐时恢复值。

## 8. 15 项自动校验

| 编号 | 检查项 | 结果 | 证据 |
|---|---|---|---|
| 1 | q2_forecast_10min.csv 行数=52560 | PASS | 实际 52560 |
| 2 | 每个 date 恰好 144 个 interval_index | PASS | forecast异常=0, plan异常=0, residual异常=0 |
| 3 | date 与 interval_index 无重复 | PASS | forecast=0, plan=0, residual=0 |
| 4 | 预测与实际数据均为有限数 | PASS | 非有限个数=0 |
| 5 | 负荷与光伏预测不小于0 | PASS | 预测列非负检查（光伏预测已按物理截断规则截断到 >=0，截断格数=14745，最大幅度=8.277 kWh） |
| 6 | 残差恒等式 actual-prediction（误差<1e-8 kWh） | PASS | max_err=4.832e-13, 合并行数=52416 |
| 7 | 场景来源日期严格早于目标日期 | PASS | 违规记录数=0; 点预测场景（残差池为空）记录数=20 |
| 8 | 计划/实际提取/充放电/紧急/弃光均非负 | PASS | 负值个数=0 |
| 9 | 实际提取量 <= 计划购电量 + 1e-6 | PASS | 违规行数=0 |
| 10 | 功率平衡最大绝对误差 <= 1e-5 kWh | PASS | max=6.821e-13 |
| 11 | SOC 递推最大绝对误差 <= 1e-5 kWh | PASS | max=4.093e-12 |
| 12 | SOC 全部位于 [1200,10800] kWh | PASS | 越界行数=0 |
| 13 | 词典序第二阶段紧急购电费 <= 第一阶段最优值+容差 | PASS | 超标天数=0, 结算方法统一=True |
| 14 | result2(7) 汇总值与提示词列出的数值一致 | PASS | SHA256 + 6 个汇总值 + 3 个行内区间差 |
| 15 | All_Code/Q2 下无本任务新增 CSV/JSON/XLSX/MD 接口文件 | PASS | 违规条目: 无（Excel 锁文件 ~$* 已排除，非本任务生成） |

## 9. 输出文件绝对路径

- `E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q3\Results\Tables\Q2_reroll_daily_rolling_log.csv`
- `E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q3\Results\Tables\Q2_reroll_tuning_sensitivity.xlsx`
- `E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q3\Results\Tables\Q2_result2_corrected_for_Q3.xlsx`
- `E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q3\Results\Tables\Q2_to_Q3_handoff_audit.xlsx`
- `E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q3\Data_processing\Q2_interface\q2_forecast_10min.csv`
- `E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q3\Data_processing\Q2_interface\q2_parameters.json`
- `E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q3\Data_processing\Q2_interface\q2_plan_reference_long.csv`
- `E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q3\Data_processing\Q2_interface\q2_residual_blocks.csv`
- `E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q3\Data_processing\Q2_interface\q2_rolling_results_lexicographic.pkl`
- `E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Q3\Data_processing\Q2_interface\q2_scenario_manifest.csv`

## 10. 未解决问题

- `All_Code/Q2/Results/Tables/run_summary.txt` 仍是 beta=0.0 的过期记录，建议在论文定稿前由 Q2 负责人确认是否更新，避免评委读取到矛盾参数。
- Q2 官方 `result2.xlsx` 宽表列错位问题未改动（不擅自改变 Q1/Q2/Q3 全局时间约定），Q3 一律使用长表接口。
- 本次所有新文件均在本地 Q3 目录，尚未 push（按提示词要求，除非用户明确要求不得 push）。

