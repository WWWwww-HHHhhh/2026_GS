# Q4-3 代码说明：波动电价下的滚动购电优化

问题四（优化部分）：用**附件 4 的每日波动电价**替换附件 1 的固定电价，重算问题三（多时点光伏预报驱动的滚动购电优化），产出 `result4-3.xlsx`。
另一半（波动电价下的问题二 → `result4-2.xlsx`）由同学完成，本目录不涉及。

> 📋 **接手者请先读 [`HANDOVER.md`](HANDOVER.md)**（任务上下文、待办、陷阱清单、论文写作要点）。
> 本文件聚焦技术细节（建模决策、运行方法、结果）。

## 关键建模决策：电价信息假设

附件 4 为 2025 全年每天 144 个 10 分钟时段的**实际电价**（365×144，均值 0.7662 与附件 1 一致，是其"每日波动版"）。本模型将其视为**日前发布电价**：**每天 0:00 制定计划时，当日 144 时段电价已知**，因此电价是确定性向量（非随机量），模型只需对光伏/负荷的不确定性做场景，**不构成未来信息泄露**。备选理解（实时价、0:00 未知需预测电价）作为论文讨论，不进主模型。

## 与 Q3 的复用关系（核心思路）

Q4-3 不重建模型，只把 `price` 从"附件 1 固定曲线"换成"附件 4 每日波动曲线"，其余全部复用 Q3 已验证代码（`import` Q3 的 `q3_core` / `run_q3` / 导出链，不改 Q3 本身）：

| 组件 | 来源 | 说明 |
|---|---|---|
| **电价** | **附件 4（新）** | `q4_data.load_q4_price()` → (144,365)，替换 `SourceData.price` |
| 负荷/光伏实际 | 附件 2（Q3 沿用） | `SourceData.load/pv` |
| 光伏预报 | 附件 3（Q3 沿用） | `PVForecast` 线性插值 |
| 负荷预测+残差 | Q2_yy（Q3 沿用） | `SourceData.load_hat` + 历史残差块 |
| 模型/参数 | Q3（`q3_core`） | solve_window/scenarios/execute_slot，M=30,α=0.9,β=0.2,κ₂=0.5317 |
| 导出链 | Q3（validate/prepare/build） | 模板换 result4-3.xlsx，采纳策略 S6_12 |

## 目录结构（输出按类型分类）

```
Q4_ZJY/
├── Model_Establishment+Solution/   # 代码
│   ├── q4_data.py                  # 附件4 波动电价接入（含日期对齐/表头跳过/校验）
│   ├── run_q4.py                   # 六策略全年回测（复用 Q3 backtest_strategy，替换 price）
│   ├── compare_q4_vs_q3.py         # 波动 vs 固定电价六策略对比分析
│   ├── prepare_result4.py          # 生成写入载荷（参数化采纳策略，默认 S6_12）
│   ├── export_result4.py           # 导出驱动：复核→载荷→写 result4-3.xlsx→工作簿校验
│   └── validate_result4_workbook.py# result4-3.xlsx 工作簿独立审计
├── Results/
│   ├── Tables/                     # 结果表
│   │   ├── result4-3.xlsx          # 提交用结果文件（四表，结构同 result3）
│   │   ├── strategy_summary.csv    # 波动电价六策略费用分解
│   │   ├── compare_fluc_vs_fixed.csv # 波动 vs 固定电价六策略对比
│   │   ├── validation_report.json  # 六策略独立复核（PASS）
│   │   ├── run_metadata.json       # 回测元数据（含附件4哈希、口径）
│   │   └── {S0..Sall}/             # 各策略 summary/daily/updates/manifest/intervals
│   └── Pictures/                   # 论文插图
├── Data_processing/                # 数据处理产物与说明
│   ├── data_processing.md          # 附件4 → price 矩阵的处理流程/对齐/校验
│   └── q4_price_matrix.npy         # 附件4 (144,365) 电价矩阵缓存
└── README.md
```

## 运行方法

```bash
cd All_Code/Q4/Q4_ZJY/Model_Establishment+Solution

# 1) 全量六策略回测（波动电价，约 18 分钟）
python run_q4.py --strategies S0 S6 S12 S18 S6_12 Sall

# 2) 波动 vs 固定电价对比
python compare_q4_vs_q3.py

# 3) 导出 result4-3.xlsx（含六策略复核 + 工作簿校验）
python export_result4.py
```

## 主要结果（2025-02-01 ~ 2025-12-31，334 天）

| 策略 | 固定电价总费用/元 | 波动电价总费用/元 | 差/元 |
|---|---:|---:|---:|
| S0（仅 0:00） | 14,861,386 | 15,499,059 | +637,673 |
| S6 | 14,686,100 | 15,314,156 | +628,056 |
| S12 | 14,655,736 | 15,278,434 | +622,699 |
| S18 | 14,875,908 | 15,507,243 | +631,335 |
| **S6_12（波动最优）** | 14,517,697 | **15,137,157** | +619,460 |
| Sall（固定最优） | **14,517,640** | 15,138,139 | +620,498 |

**关键结论**：
1. 波动电价使各策略全年费用普遍上升约 62 万元（约 +4.2%）——日内电价峰谷差大，高价时段购电更贵。
2. **滚动更新的价值在波动电价下反而增大**（S0−最优：固定 343,746 元 → 波动 360,920 元）——电价波动越大，依据新预报调整购电的收益越高。
3. **最优策略由 Sall 变为 S6_12**：波动电价下 18 点更新从无价值变为略微有害（Sall 比 S6_12 贵 982 元，0.006%），"引入 6/12 点、不引入 18 点"的结论在两种电价下一致且更明确。
4. 采纳策略 **S6_12**（波动电价最优），导出 `result4-3.xlsx`。

## 校验

- 电价接入：`price[:,day]` 逐日比对附件4（day0/day31/day364 全过），无错位；0 缺失、全部 >0
- 六策略独立复核：`validate_q3.py` 重算能量/费用/SOC/因果性，`validation_report.json` 全 PASS
- 工作簿审计：`validate_result4_workbook.py` 校验 result4-3.xlsx 的四表结构、跨行映射、费用勾稽、SOC 跨日
