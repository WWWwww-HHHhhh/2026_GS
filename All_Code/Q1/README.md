# Q1 代码说明

问题 1：确定电价/负载 + 光伏预测下的日前计划购电连续 LP（HiGHS 求解）。

## 运行环境与依赖

- Python 3.13（其他 3.10+ 版本未逐一验证，理论上可用）
- 依赖：`numpy pandas scipy openpyxl matplotlib`
- 安装：`pip install numpy pandas scipy openpyxl matplotlib`

## 输入数据

- `Data/附件/附件1.xlsx`：144 个 10 min 时段的电价（元/kWh）、小区负载（kW）、光伏预测功率（kW）
- `Data/附件/附件5/result1.xlsx`：官方结果模板

## 运行方法与输出

```bash
cd All_Code/Q1/Model_Establishment+Solution
python q1_model.py     # 求解 LP + 校验 + 导出结果
cd ../Pictures
python q1_figures.py   # 生成 4 张论文插图（依赖上一步的 CSV）
```

输出：

| 文件 | 位置 | 说明 |
|---|---|---|
| `result1.xlsx` | `Tables/` | 按官方模板填充的计划购电量与充放电量（提交用） |
| `q1_timeseries.csv` | `Tables/` | 144 时段全量结果（含对偶变量），论文数值溯源用 |
| `q1_summary.json` | `Tables/` | 汇总指标与校验结果 |
| `q1_fig1~4.pdf` | `Pictures/` | 时序 / 调度组合 / SOC 轨迹 / 电价与储能边际价值 |

## 主要结果（2026-09-10 运行）

- 全天购电费用 **35126.95 元**，全天购电量 59482.70 kWh，弃光 0 kWh
- 无储能基线 48052.05 元 → 节省 26.90%
- 校验：平衡残差 2.3e-13 kWh；SOC ∈ [1200, 10800]；s(0:00)=s(24:00)=6000 kWh

## 口径备注

- 功率 × 1/6 转为 10 min 时段电量（kWh）后进入模型，全程不混用 kW/kWh
- 附件 1 时间标签视为时段结束时刻；result1 模板按同序逐行映射填充，模板表头未改动
- 目标含 ε=0.001 元/kWh 的储能吞吐惩罚（排除无意义同时充放电）；报告费用不含该项
