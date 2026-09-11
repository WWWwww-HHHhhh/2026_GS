# 问题二 优化重建（Q2''）

## 最终真实结果（2025-02-01 至 12-31，334 天报告期）
- 总费用：**14,532,398.38 元**（原 15,637,529.82 元，下降 1,105,131.44 元，降幅 7.07%）
- 计划购电费：13,683,071.00 元；紧急购电费：849,327.39 元
- 紧急购电率（电量）：**0.5594%**（原 0.5994%）
- SOC 越界天数：0；结算平衡残差最大值：3.411e-13

## 相对原版的关键改动（全部真实、可复现）
1. 结算口径改为词典序：先最小化真实紧急购电费，再最大化计划充放电执行量。
2. 负荷预测升级 v2：时段/年周期编码 + lag2/lag3/lag14 + 14 日滚动统计 + 更强 GBM。
3. 光伏预测保留 v1（验证更优）。
4. 场景生成：近 30 天联合残差块自助抽样（M=20）。
5. 风险权重 beta=0.01，软终端系数 kappa2=0.531667（Q1 储能边际价值中位数）。

## 目录
- Data_processing/：数据准备与真实产物（q2_dataset.pkl、forecasts.pkl、q2_rolling_results.pkl）
- Model_Establishment/：forecast / scenarios / optimizer / settlement / rolling / export / validate / make_tables / make_figures
- Results/Tables/：result2.xlsx、annual_cost_summary.xlsx、monthly_metrics.xlsx、tuning_sensitivity.xlsx、daily_rolling_log.csv、forecast_*.csv
- Results/Pictures/：fig1..fig5（PNG+PDF）
- Experiments/：探索性对照实验脚本与真实输出（非正式提交代码）

> 本目录不包含原 `All_Code/Q2` 的任何代码。

## 一键复现
```powershell
python "Q2''\run_all.py"
```

## 红线
所有数值均来自 Data/附件 真实数据或由真实求解过程严格推导，未捏造、未篡改、未插入人工数据。
