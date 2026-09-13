# Q4 陈旧资产审计（只读）

生成时间：2026-09-13 13:13:03

## A 时间线：图文件 vs 官方结果文件

注意：本仓库刚做过 git reset，被重写的文件修改时间会变成 reset 时刻，因此时间只能作为参考，不能单独定性。

### A1 问题四第三问（队友工作区）的图

| 文件 | 修改时间 | 大小 |
| --- | --- | --- |
| Results\Pictures\q4_fig1_price_curves.pdf | 09-12 20:15:07 | 39156 B |
| Results\Pictures\q4_fig1_price_curves.png | 09-12 20:15:07 | 373939 B |
| Results\Pictures\q4_fig1_price_curves.svg | 09-12 20:15:07 | 112954 B |
| Results\Pictures\q4_fig2_strategy_cost.pdf | 09-12 20:15:07 | 20718 B |
| Results\Pictures\q4_fig2_strategy_cost.png | 09-12 20:15:07 | 75273 B |
| Results\Pictures\q4_fig2_strategy_cost.svg | 09-12 20:15:07 | 51066 B |
| Results\Pictures\q4_fig3_update_value.pdf | 09-12 20:15:07 | 24465 B |
| Results\Pictures\q4_fig3_update_value.png | 09-12 20:15:07 | 72637 B |
| Results\Pictures\q4_fig3_update_value.svg | 09-12 20:15:07 | 53683 B |

### A2 问题四第三问的官方结果

| 文件 | 修改时间 | 大小 |
| --- | --- | --- |
| Results/Tables/strategy_summary.csv | 09-13 01:08:53 | 2079 B |
| Results/Tables/run_metadata.json | 09-13 01:08:53 | 1721 B |
| Results/Tables/validation_report.json | 09-13 01:08:53 | 2342 B |
| Results/Tables/result4-3.xlsx | 09-13 01:08:53 | 1160675 B |
| Results/Tables/Sall/summary.json | 09-13 01:08:53 | 778 B |
| Results/Tables/Sall/daily.csv | 09-13 01:08:53 | 124231 B |

### A3 问题四第二问（本工作区）的图与官方结果

| 文件 | 修改时间 | 大小 |
| --- | --- | --- |
| Pictures/fig_q4_frontier_baseline.pdf | 09-12 20:20:55 | 47115 B |
| Pictures/fig_q4_main_vs_b1_cost_structure.pdf | 09-12 20:20:55 | 62795 B |
| Pictures/fig_q4_monthly_cost.pdf | 09-12 20:20:54 | 19273 B |
| Pictures/fig_q4_plan_vs_extract.pdf | 09-12 20:20:54 | 18313 B |
| Pictures/fig_q4_price_forecast.pdf | 09-12 20:20:53 | 39329 B |
| Pictures/fig_q4_representative_day.pdf | 09-12 20:20:54 | 49690 B |
| Pictures/fig_q4_scenario_fan.pdf | 09-12 20:20:55 | 42467 B |
| Results/Tables/result4-2.xlsx | 09-12 19:25:01 | 673459 B |
| Results/Tables/q4_2_daily_rolling_log.csv | 09-12 19:24:45 | 164821 B |
| Results/Tables/q4_2_experiments.csv | 09-12 22:32:20 | 4303 B |
| Results/Tables/q4_2_paper_numbers.csv | 09-12 22:33:15 | 5500 B |
| Data_processing/q4_2_rolling_results.pkl | 09-12 19:24:45 | 39908072 B |

## B 图脚本读的是什么数据

### Q4_ZJY 的 make_q4_figures.py

```
read_excel
read_excel
read_csv
read_csv
read_csv
read_csv
```
脚本里出现的输入文件名：

- `strategy_summary.csv`
- `附件1.xlsx`
- `附件4.xlsx`

### Q4_wyh 的 make_figures_q4_2.py

```
load(
load(
load(
load(
load(
read_csv
read_csv
read_csv
load(
```
脚本里出现的输入文件名：

- `price_forecast.pkl`
- `q4_2_baselines.csv`
- `q4_2_experiments.csv`
- `q4_2_fig_main_vs_b1_data.csv`
- `q4_2_rolling_results.pkl`
- `q4_2_timing_main_vs_b1.csv`
- `q4_dataset.pkl`
- `scenarios_M{M}.pkl`

## C 工作文档里的旧版数字与 HANDOVER 引用（残留排查）

- `All_Code\Q4\Q4_ZJY\HANDOVER.md` L53 命中 `HANDOVER`：├── HANDOVER.md                        # 本文件
- `All_Code\Q4\Q4_ZJY\Model_Establishment+Solution\make_q4_figures.py` L83 命中 `q4_fig2`：fig.savefig(FIGURES / f"q4_fig2_strategy_cost.{ext}", dpi=220)
- `All_Code\Q4\Q4_ZJY\Model_Establishment+Solution\make_q4_figures.py` L111 命中 `q4_fig3`：fig.savefig(FIGURES / f"q4_fig3_update_value.{ext}", dpi=220)
- `All_Code\Q4\Q4_ZJY\README.md` L6 命中 `HANDOVER`：> 📋 **接手者请先读 [`HANDOVER.md`](HANDOVER.md)**（任务上下文、待办、陷阱清单、论文写作要点）。
- `All_Code\Q4\Q4_wyh\others\04_Q4双工作区P0审计与修改方案.md` L30 命中 `HANDOVER`：| Q4_ZJY | 附件4 视为**日前发布电价**，每天 0:00 当日 144 时段电价**已知**，价格是**确定性向量** | `README.md` 第 11 行、`HANDOVER.md` §3.1、`run_q4.py` docstring |
- `All_Code\Q4\Q4_wyh\others\04_Q4双工作区P0审计与修改方案.md` L86 命中 `HANDOVER`：2. **两问预报源不同**：Q4_ZJY 的 `HANDOVER.md` §7 已把它列为"预期差异"，并明确警告"论文里若要对比 Q4-2 与 Q4-3，必须注明差异含预报精度与更新两部分，不能直接下结论"。这与 P0-1 叠加，使两问彻底不可比。
- `All_Code\Q4\Q4_wyh\others\04_Q4双工作区P0审计与修改方案.md` L145 命中 `HANDOVER`：- 而 Q4_ZJY 的 `HANDOVER.md` §3.2 写的是"**日末回到日初值**"。
- `All_Code\Q4\Q4_wyh\others\04_Q4双工作区P0审计与修改方案.md` L150 命中 `HANDOVER`：- S6_12 = 15,137,156.79 元 vs Sall = 15,138,138.52 元，**差 981.73 元 = 0.0065%**；`README.md` 据此写"Sall 比 S6_12 贵 982 元，0.006%"，`HANDOVE
- `All_Code\Q4\Q4_wyh\others\04_Q4双工作区P0审计与修改方案.md` L152 命中 `HANDOVER`：- 另有一处数字不一致：`README.md` 第 80 行写"节省 360,920 元"（= S0 − Sall），`HANDOVER.md` §4.3 更正为 **361,902 元**（= S0 − S6_12）。论文必须用后者。
- `All_Code\Q4\Q4_wyh\others\04_Q4双工作区P0审计与修改方案.md` L153 命中 `HANDOVER`：- 方案：① 论文措辞改为"18 点更新的边际收益在波动电价下降至 0.006%，不具统计意义，故采纳更少更新次数的 S6_12"；② 补多种子/多场景数稳定性（其 `HANDOVER.md` 已把它列为可选项），用区间而非点值下结论；③ 论文里统一用 361
- `All_Code\Q4\Q4_wyh\others\05_方案C双口径与敏感性方案.md` L105 命中 `HANDOVER`：1. Q4_ZJY 全链 `import` `All_Code/Q3/Model_Establishment+Solution/{q3_core,run_q3,build_result3}`，其 `HANDOVER.md` 明确标红"**不要动 Q3 下任何文
- `All_Code\Q4\Q4_wyh\others\05_方案C双口径与敏感性方案.md` L154 命中 `HANDOVER`：> ⚠️ Q4_ZJY 的 `HANDOVER.md` §3.2 写作"日末回到日初值"，与本文一手数据解析结果（53/334 天偏离 >1 kWh）不一致，**需以代码为准统一表述**。
- `All_Code\Q4\Q4_wyh\others\05_方案C双口径与敏感性方案.md` L158 命中 `HANDOVER`：- 统一数字：S0 − S6_12 = 15,499,059.00 − 15,137,156.79 = **361,902.21 元**（`README.md` 里的 360,920 是拿 Sall 算的，已由 `HANDOVER.md` §4.3 更正，论文
- `All_Code\Q4\Q4_wyh\others\08_Q4附录候选清单.md` L226 命中 `q4_fig2`：5. **问题四第三问的三张图未被正文引用**：队友工作区已产出 `q4_fig1_price_curves.pdf`（电价曲线）、`q4_fig2_strategy_cost.pdf`（六策略费用）、`q4_fig3_update_value.pdf`（更新

## D 论文 Q4 正文数字 vs 官方结果

官方六策略（万元，来自 strategy_summary.csv）与论文引用对照：

| 策略 | 官方(万元) | 论文是否出现该数字 |
| --- | --- | --- |
| S0 | 1574.60 | 是 |
| S6 | 1551.10 | 是 |
| S12 | 1552.65 | 是 |
| S18 | 1575.30 | 是 |
| S6_12 | 1535.80 | 是 |
| Sall | 1535.53 | 是 |

旧版数字是否出现在论文正文：

- `1549.9`：出现（需处理）
- `1531.4`：未出现（正常）
- `1527.8`：未出现（正常）
- `1513.7`：未出现（正常）
- `1513.72`：未出现（正常）

派生量复核：

- 更新价值 S0−Sall = 390715.19 元 = 39.07 万元，降幅 2.48%，论文写 39.07 万元与 2.48%
- S18−S0 = 7023.56 元 = 0.70 万元，论文写比 S0 高 0.70 万元
- S6,12−Sall = 2747.16 元 = 0.27 万元，占 0.0179%，论文写 0.27 万元与 0.018%

## E 直接读取图中的数字（判定新旧）

可用 PDF 文本库：无
