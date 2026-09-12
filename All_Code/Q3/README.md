# Q3 代码说明

问题三：基于 0:00 / 6:00 / 12:00 / 18:00 光伏滚动预报的微网购电滚动优化（含 0.5 倍违约、1.5 倍超量与 5 倍紧急购电结算）。

## 目录结构

```
All_Code/Q3/
├── Model_Establishment+Solution/
│   ├── q3_core.py                   # 核心：数据读取、情景生成、单窗口随机 LP、结算函数
│   ├── run_q3.py                    # 全年回测驱动器（六种策略；写 daily/intervals/updates/summary）
│   ├── validate_q3.py               # 独立复核（重算能量、费用、SOC、因果性，不信任求解器目标值）
│   ├── forecast_audit.py            # 整点预报 → 10 分钟转换误差审计（线性插值 vs 阶梯保持）
│   ├── prepare_result3.py           # 由回测产物生成 result3.xlsx 写入载荷
│   ├── build_result3.py             # 按官方模板写出 result3.xlsx（纯 Python，可移植）
│   ├── validate_result3_workbook.py # 工作簿级校验（结构、跨行恒等、汇总口径、SOC 跨日）
│   └── make_q3_figures.py           # 论文插图（读 Results/Tables，写 Results/Pictures）
├── Results/
│   ├── Tables/                      # 六策略 summary/daily/updates + 采纳策略(Sall) 的 intervals
│   │   ├── result3.xlsx             # 提交用结果文件（4 个工作表）
│   │   ├── result3_payload.json     # 结果表写入载荷（可追溯）
│   │   ├── strategy_summary.csv     # 六策略费用分解
│   │   ├── validation_report.json   # 独立复核结论（status=PASS）
│   │   ├── forecast_conversion_audit.csv  # 整点预报→10 分钟转换误差（正式期诊断，不用于选方法）
│   │   ├── forecast_conversion_audit_jan.csv  # 1 月选择窗口的插值对比（方法选择证据）
│   │   ├── seed_stability.json        # 多种子稳定性验证（3 种子下 Sall<S0 排名稳定）
│   │   ├── settlement_gross/          # 备选结算口径（原价照付+违约）重跑的复核证据（summary+daily）
│   │   └── repro_check_Sall_summary.json  # 复现验证运行记录
│   └── Pictures/                    # 论文插图（q3_fig1 ~ q3_fig6，PDF+PNG+SVG）
├── Data_processing/Q2_interface/    # 冻结的 Q2 交接数据（预测、残差块、参数）
└── legacy_v1_single_day/            # 早期单日试算版（已废弃，仅留档，结果不可引用）
```

## 运行环境与依赖

- Python 3.12（3.10+ 未逐一验证）；依赖 `numpy pandas scipy`，绘图另需 `matplotlib`
- 写出工作簿需 Node.js（`build_result3.mjs`）
- 求解器：`scipy.optimize.linprog(method="highs")`，稀疏矩阵组装

## 输入数据（均为仓库内既有文件，脚本只读）

- `Data/附件/附件1.xlsx`：典型日电价（元/kWh）
- `Data/附件/附件2.xlsx`：全年实际负载与光伏（kW）
- `Data/附件/附件3.xlsx`：每日 0:00/6:00/12:00/18:00 发布的未来 24 h 整点光伏预报（kW）
- `All_Code/Q2_yy/`：Q2 负荷预测与残差块（冻结接口）
- `All_Code/Q3/Data_processing/Q2_interface/`：Q2→Q3 交接缓存（含 `q2_rolling_results_lexicographic.pkl`）

## 运行方法

```bash
cd All_Code/Q3/Model_Establishment+Solution

# 1) 全年回测（六策略全跑约 13 分钟；单策略 Sall 约 3 分钟）
python run_q3.py --strategies S0 S6 S12 S18 S6_12 Sall --outdir ../Results/Tables

# 1b) 备选结算口径（原价照付+违约/超量）重跑，用于口径敏感性
python run_q3.py --strategies S0 S6 S12 S18 S6_12 Sall --settlement gross --outdir ../Results/Tables/settlement_gross

# 2) 独立复核
python validate_q3.py --strategies S0 S6 S12 S18 S6_12 Sall --outdir ../Results/Tables

# 3) 预报转换误差审计
python forecast_audit.py

# 4) 生成 result3.xlsx（先出载荷，再按官方模板写入）
python prepare_result3.py --folder ../Results/Tables
python build_result3.py

# 5) 工作簿校验 + 论文插图
python validate_result3_workbook.py
python make_q3_figures.py
```

> 早期版本另有 `build_result3.mjs`（Node + Codex 运行时内部包 `@oai/artifact-tool`），
> 路径与依赖都不通用，已移入 `legacy_v1_single_day/`；`build_result3.py` 是等价的可移植实现，
> 两者产出的工作表数值经逐单元格比对完全一致（4 张表 0 差异）。

## 复现与校验证据（2026-09-12 复核）

| 检查 | 方法与结果 |
|---|---|
| 全年回测可复现 | 从仓库路径重跑 `run_q3.py --strategies Sall`，173 s，总费用 `14517640.171605363` 元，与原结果逐位一致 |
| 独立复核（六策略） | `validate_q3.py` 重算能量/费用/SOC/因果性：`validation_report.json` 中 `status = PASS`，六策略 `all_checks_passed = true` |
| 工作簿独立审计 | `validate_result3_workbook.py`：334 个日期、96192 个购电格、2004 行储能记录、3818 条紧急购电事件、跨行映射与费用勾稽全部通过 |
| 结果表写入一致性 | Python 写出器与早期 Node 实现逐单元格对比：计划购电量/调整购电量/充放电量/紧急购电量四表**0 差异** |
| 论文编译 | `Paper/main.tex` 在本机 MiKTeX（xelatex）下编译通过，27 页，0 错误、0 未定义引用 |
| 备选口径敏感性 | `run_q3.py --settlement gross` 重跑六策略：Sall=14,739,051 元，仍比 S0（14,861,386 元）省 122,335 元；主结论在两种口径下一致 |
| 多种子稳定性 | 3 个种子重算 S0/Sall：节省 31.7 万–34.4 万元，`Sall<S0` 排名在全部种子下稳定（`seed_stability.json`） |

## 主要结果（2025-02-01 至 2025-12-31，334 天 / 48,096 个 10 分钟时段）

| 策略 | 全年实际费用 / 元 | 紧急购电 / kWh | 弃光 / kWh |
|---|---:|---:|---:|
| S0（仅 0:00 预报） | 14,861,385.82 | 214,020.65 | 2,014,105 |
| S6 | 14,686,099.81 | 163,570.07 | 1,793,550 |
| S12 | 14,655,735.82 | 178,625.60 | 1,822,617 |
| S18 | 14,875,907.77 | 211,753.94 | 2,007,694 |
| S6+12 | 14,517,696.85 | 154,316.09 | 1,669,819 |
| **S6+12+18（采纳）** | **14,517,640.17** | **154,171.38** | **1,669,593** |

- 相对 Q2 点预测基线 14,708,963.49 元，Sall 节省 191,323.32 元（1.30%）
- 相对仅用 0:00 预报，Sall 节省 343,745.65 元（2.31%），紧急购电下降 27.96%
- 独立复核：六策略全部 PASS；功率平衡最大残差 1.9e-9 kWh；SOC 跨日衔接偏差 0；同时充放 0 次

## 关键口径（必须与论文一致）

1. **时间**：附件时刻为十分钟区间的**右端点**，`0:00+1` 即当日 24:00；自然日 = 144 个区间。
2. **模板跨行**：`result3.xlsx` 的“计划购电量/调整购电量”按官方模板跨行展示——普通日期行前 143 格属本日区间 2–144，最后一格为**次日首区间**；因此行内 144 格之和 ≠ 该行“全天购电量”（后者按完整自然日统计），最后一行最后一格为空。
3. **结算基准**：最终调整购电量与**当日 0:00 计划**一次性比较结算，不逐次累计；计划高于调整的部分按 0.5 倍电价、调整高于计划的部分按 1.5 倍电价，二者在正价格下为凸分段线性，可用 LP 精确表达。题面"计划购电费用"另有"原价照付、差额另付违约/超量"的解读（备选口径，`--settlement gross`），重跑后结论一致（见 `settlement_gross/` 与论文表 10）。
4. **重解规则（更新时点）**：在策略允许的发布时刻，以该时刻已发布的最新预报、已结束时段的真实 SOC 与同一组残差场景，对未执行时段重解并直接生效；由于允许调整的可行域包含维持现方案的可行域，重解目标不劣于原方案，故无需另设采纳门槛，也不虚构调整手续费。
5. **非预期性**：各时刻只使用该时刻及以前的真实信息；已执行时段冻结（0:00–6:00 的最终计划恒等于 0:00 计划）。
6. **参数**：α=0.9、β=0.2、场景数 M=30、软终端罚系数 κ=0.5317 元/kWh（取自问题一储能边际价值中位数）、随机种子 20260101。
7. **预报转换**：附件 3 整点预报按线性插值降到 10 分钟。线性插值依据光伏功率的物理连续性预先选定，1 月历史窗口独立验证其优于阶梯保持（0 点 WAPE 8.16% vs 16.22%），正式期误差仅作诊断。

## 与早期版本的关系

`legacy_v1_single_day/` 是题三早期单日试算实现（`main_q3.py` / `optimizer.py` / `rolling.py` 等），模型口径已与当前版本不同，其 `Q3_quick_*.xlsx` 仅为当日冒烟测试，**不可作为论文数值来源**；论文数值一律以 `Results/Tables/` 下的回测产物为准。
