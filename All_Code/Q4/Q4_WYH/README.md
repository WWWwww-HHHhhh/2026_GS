# Q4_WYH：问题四第二问的唯一正式工作区（自包含可运行）

本目录专门用于问题四**第二小问**，已完成三件事：

1. **主口径为附件3 光伏预报**（题目第 4 问原文指定的数据源），自建因果光伏预测降为受控对照；
2. **可独立运行**：`q4_common.py` 的 `find_repo_root()` 会把本目录认作仓库根，全部关键输入都在本目录内部，无需改动任何源码；
3. **唯一正式结果**：`Results/Tables/result4-2.xlsx` 由新主口径那一格重导出，8 项回读校验全部 PASS。

本目录由原 `All_Code/Q4_wyhnew` 整理迁入，作为问题四第二问的正式代码与取数来源。

## 目录结构

| 路径 | 内容 |
| --- | --- |
| `Data/附件/` | 仓库根原始附件（`find_repo_root()` 依赖它） |
| `All_Code/Data_preprocessing/Data_transformation/` | 全局变换 parquet 与时间映射（`03_q4_dataset.py` 读取） |
| `All_Code/Data_preprocessing/Data_clean/` | 清洗后的明细 csv |
| `All_Code/Q2_yy/Data_processing/` | Q2 已定稿产物 `q2_dataset.pkl` 与 `forecasts.pkl` |
| `All_Code/Q1/Results/Tables/result1.xlsx` | B3 基线（典型日策略）的数据源 |
| `Data_processing/` | Q4-2 脚本与数据（数据集、价格预测、场景、变体结果） |
| `Model_Establishment+Solution/` | Q4-2 模型、变体、实验、诊断、导出、验证脚本 |
| `Results/Tables/` | 结果表（先看 `口径说明.md` 判断每张表属于哪套口径） |
| `Results/Pictures/` | Q4-2 的图（代表日图已是新口径版本） |
| `others/原始附件_CUMCM2026_C/` | 题目原文与附件（`ATTACH_RAW` 依赖） |
| `others/` | 工作文档（建模思路、口径对齐、结果报告、审计方案等） |
| `audit/` | 本次核查用的只读脚本与全部审计报告 |
| `figures/` | 论文 10.5.1 直接引用的代表日图（新版） |
| `MANIFEST.md` | 全目录文件清单（大小与 sha256 前 12 位） |

`All_Code/Q4/Q4_ZJY` 属队友的问题四第三问，本次未改动，也不在本目录内。

## 主口径的关键数字

新主口径：附件3 光伏预报、价格零点未知、M=30、β=0.20、κ×1.0，报告期 2025-02-01 至 12-31 共 334 天。

| 指标 | 数值 |
| --- | --- |
| 报告期总费用 | 15,728,958.76 元（计划 14,762,076.40，紧急 966,882.36） |
| 计划购电量 | 22,885,559.26 kWh |
| 紧急购电量 | 242,133.03 kWh，占总负荷 0.654% |
| 计划购电平均单价 | 0.6450 元/kWh，比报告期市场均价 0.7575 低 14.85% |
| 择时集中度 | 计划 40.86%、充电 48.16% 落在最便宜 25%，放电 72.26% 落在最贵 25% |
| 累计未提取量 | 1,763,979.96 kWh，占计划量 7.71% |
| 与 B0 的差额 | 22.60% |
| 代表日（紧急购电最多） | 2025-07-01，紧急购电 11,049.14 kWh |

逐项推导与新旧对照见 `official_cell_numbers.md`。

## 如何运行

数据处理与模型脚本需要 `D:\Anaconda\python.exe`（pandas 2.3.3、openpyxl 3.1.5）。
PATH 上的 `python` 是 msys64 版本，不含 pandas。

按依赖顺序：

```
D:\Anaconda\python.exe Data_processing\03_q4_dataset.py
D:\Anaconda\python.exe Data_processing\04_q4_price_forecast.py
D:\Anaconda\python.exe Data_processing\05_q4_scenarios.py --M 30 --pv-source official
D:\Anaconda\python.exe "Model_Establishment+Solution\q4_2_rolling.py" --mode full
D:\Anaconda\python.exe "Model_Establishment+Solution\q4_2_variants.py" --pv-source official --price-mode unknown --select legacy --tag V_official_unknown_q2params
D:\Anaconda\python.exe "Model_Establishment+Solution\q4_2_experiments.py"
D:\Anaconda\python.exe "Model_Establishment+Solution\q4_2_diagnostics.py" --b1
D:\Anaconda\python.exe "Model_Establishment+Solution\validate_q4_2.py"
```

重导出正式工作簿（新主口径那一格，落到官方模板名）：

```
D:\Anaconda\python.exe export_result4_official.py --results Data_processing\variants\V_official_unknown_q2params_results.pkl --out Results\Tables\result4-2.xlsx
```

重绘代表日图与复算论文数字（不跑模型）：

```
D:\Anaconda\python.exe make_figure_representative_official.py
D:\Anaconda\python.exe compute_official_cell_numbers.py
```

## 入 git 与不入 git

`.gitignore` 已配好：代码、文档、结果表、图与可复现所需的输入副本入库；
大体量且可重新生成的中间产物（`scenarios_M*.pkl` 合计约 228 MB、`q4_2_rolling_results.pkl` 38 MB、非正式的变体 pkl）不入库；
**附件3 口径那一格的 `V_official_unknown_q2params_results.pkl` 例外入库**，它是新主口径的正式结果来源。

提醒：不要用 `git add -A` 整体提交本目录，先看 `git status` 里是否有大于 50 MB 的文件。

## 与旧工作区的关系

| 目录 | 定位 |
| --- | --- |
| `All_Code/Q4/Q4_WYH`（本目录） | 问题四第二问的正式工作区，论文取数来源 |
| `All_Code/Q4/Q4_ZJY` | 队友的问题四第三问工作区，本次未改动 |

## 审计与核查记录

- `audit/verify_checklists_round2.md`：桌面两份核对清单的逐条复验
- `audit/audit_q4_stale_assets.md`：旧版图与陈旧数字排查
- `verify_wyh_checklist_round3.md`：按 `WYH_Q4_2_核对清单.md` 的第二轮复核（含仍未达标项）
- `dependency_inventory.md`：独立运行依赖清点
- `path_resolution_check.md`：路径解析自检（结论：全部落在本目录内部）
- `audit/cjk_in_math.md`：`Paper/7.Q1` 把“元”写成 `\mathrm{元}` 导致 PDF 缺字的定位

## 已知未修项

1. 旧工作区 `Results/Tables/q4_2_validation_report.md` 的 B1 紧急购电费写 887318.97 元，正确值为 1,748,828.89 元（论文用的是正确值）。
2. `Model_Establishment+Solution/q4_core.py` 第 35 行默认 `"beta": 0.5`，正式入口会覆盖，单独调用有误用风险。
3. 论文第四问仍有 12 处红字占位（9 条附录占位、2 条支撑文件说明、1 处行内），待附录定稿后删除。
4. 问题四第三问的论文公式与代码不一致等问题按用户指示冻结，未处理。
