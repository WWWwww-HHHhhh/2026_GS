# Q4 正式版本与历史产物清单

## 判定原则

Q4 文件不能仅按修改时间判断新旧。
正式版本必须同时满足以下条件。

1. 与当前论文中的主要数值一致。
2. 与正式 `result4-2.xlsx` 或 `result4-3.xlsx` 的数据链一致。
3. 具有对应的汇总文件、运行元数据和校验结果。
4. 参数、初始储电量、报告期和结算口径与正文一致。

## Q4-2 正式结果链

正式主结果为 `Q4_wyh/Results/Tables/result4-2.xlsx`。
该结果对应报告期总费用 15561929.84 元，计划购电费用 14670390.10 元，紧急购电费用 891539.74 元，紧急购电量 217118.05 kWh，期末储电量 6000 kWh。

下列文件与该结果属于同一正式数据链。

- `Q4_wyh/Data_processing/q4_2_rolling_results.pkl`
- `Q4_wyh/Results/Tables/q4_2_daily_rolling_log.csv`
- `Q4_wyh/Results/Tables/q4_2_experiments.csv` 中的“主模型”行
- `Q4_wyh/Results/Tables/q4_2_paper_numbers.csv`
- `Q4_wyh/Results/Tables/q4_2_paper_numbers.md`
- `Q4_wyh/Results/Tables/q4_2_structural_checks.csv`
- `Q4_wyh/Results/Tables/q4_2_validation_report.md`
- `Q4_wyh/Results/Pictures/fig_q4_*.pdf`

`Q4_wyh/Results/Tables/result4-2_风险感知选参.xlsx` 不是正式提交版本。
它对应风险感知重新选参实验，计划购电量、紧急购电量和报告期初始储电量均与正文主模型不同，应归入灵敏度或历史对照材料。

`V_*.csv`、`V_*_tuning.xlsx`、`q4_2_variant_matrix.csv` 和 `q4_2_baselines.csv` 均为受控实验或基线结果，不属于旧版主模型，也不能替代正式结果文件。

## Q4-3 正式结果链

正式主结果为 `Q4_ZJY/Results/Tables/result4-3.xlsx`。
对应运行元数据记录的生成时间为 2026-09-12 23:22 北京时间，采用 `M=30`、`alpha=0.9`、`beta=0.2`、`kappa2=0.5316667`，正式采纳策略为 `Sall`。

下列文件与该结果属于同一正式数据链。

- `Q4_ZJY/Results/Tables/strategy_summary.csv`
- `Q4_ZJY/Results/Tables/compare_fluc_vs_fixed.csv`
- `Q4_ZJY/Results/Tables/run_metadata.json`
- `Q4_ZJY/Results/Tables/validation_report.json`
- `Q4_ZJY/Results/Tables/S0` 至 `Sall` 六个策略目录
- `Q4_ZJY/README.md`

正式六策略总费用依次为 15746005.83 元、15511017.44 元、15526460.89 元、15753029.39 元、15358037.80 元和 15355290.65 元。
当前论文中的六策略表与该组数值一致。

## Q4-3 旧版或失效内容

`Q4_ZJY/HANDOVER.md` 中引用了更早一轮结果，其中 S6_12 的费用约为 1513.72 万元，并被判定为最优策略。
该数值与当前 `strategy_summary.csv`、`run_metadata.json` 和 `result4-3.xlsx` 不一致，因此该文档只能作为历史记录，不能作为论文取数依据。

以下两张费用图生成于正式 Q4-3 回测完成之前，图中数据与当前正式汇总不一致，不能直接用于论文。

- `Q4_ZJY/Results/Pictures/q4_fig2_strategy_cost.*`
- `Q4_ZJY/Results/Pictures/q4_fig3_update_value.*`

`q4_fig1_price_curves.*` 只展示附件电价特征，不依赖六策略费用，因此数据本身仍然有效。

## 当前唯一取数顺序

论文与提交文件应按照以下优先级取数。

1. 正式 `result4-2.xlsx` 和 `result4-3.xlsx`
2. 与工作簿对应的汇总文件和运行元数据
3. 当前 `Paper/10.Q4/content.tex`
4. 附录和支撑材料
5. README、HANDOVER 与历史说明文档

若同一指标出现冲突，应以正式工作簿能够追溯到的汇总文件和运行元数据为准，不采用文件修改时间较晚但参数口径不同的结果。
