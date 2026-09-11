# Q1 代码说明

问题 1：确定电价/负载 + 光伏预测下的日前计划购电连续 LP（HiGHS 求解）。主程序先求最低真实购电费，再在费用容差内最小化储能吞吐量；影子价格从纯购电费用 LP 提取。

## 运行环境与依赖

- Python 3.13（其他 3.10+ 版本未逐一验证，理论上可用）
- 依赖：`numpy pandas scipy openpyxl matplotlib`
- 安装：`pip install numpy pandas scipy openpyxl matplotlib`

## 输入数据

- `Data/附件/附件1.xlsx`：144 个 10 min 时段的电价（元/kWh）、小区负载（kW）、光伏预测功率（kW）
- `Data/附件/附件5/result1.xlsx`：官方结果模板

## 运行方法与输出

```bash
cd All_Code/Q1/Model_Establishment
python q1_model.py     # 求解 LP + 校验 + 导出结果
python q1_switching_check.py  # 可选：同等费用下的最少模式切换 MILP
python q1_efficiency_sensitivity.py  # 可选：复核“90%效率”的两种解释
cd ../Results/Pictures
python q1_figures.py   # 生成 4 张论文插图（依赖上一步的 CSV）
python q1_figures.py --figure 1   # 可选：只重画第 1 张
```

输出：

| 文件 | 位置 | 说明 |
|---|---|---|
| `result1.xlsx` | `Tables/` | 按官方模板填充的计划购电量与充放电量（提交用） |
| `q1_timeseries.csv` | `Tables/` | 144 时段全量结果（含对偶变量），论文数值溯源用 |
| `q1_storage_marginal_value_for_q2.csv` | `Tables/` | Q1 确定性储能边际价值基准，供 Q2 读取与对照 |
| `q1_storage_marginal_value_for_q2.xlsx` | `Tables/` | 面向建模队员的边际价值汇总与 144 时段明细表 |
| `q1_summary.json` | `Tables/` | 汇总指标与校验结果 |
| `q1_time_mapping.csv` | `Tables/` | 源时间、内部区间与官方模板标签的映射核对 |
| `q1_switching_summary.json` | `Tables/` | 可选 MILP 切换校验结果 |
| `q1_efficiency_sensitivity.json` | `Tables/` | 单向效率 90% 与往返效率 90% 的口径对照 |
| `q1_fig1~4.pdf` / `.png` | `Pictures/` | 图1 电价—小区负载—光伏—净负荷 双轴折线（左轴功率、右轴电价，光伏用渐变面积，高电价时段铺底纹）；图2 供电来源堆叠；图3 SOC 轨迹与可行域；图4 储能边际价值对电价的散点关系图（含 `v=电价`、`v=0.9×电价` 参考线，SOC 触界点单独标注）。PDF 供投稿、PNG 供预览，四图共用统一配色与版式 |

## 主要结果（2026-09-10 运行）

- 第一阶段最低购电费用约 **35126.95 元**；二级稳定解仅允许极小费用容差
- 无储能基线 48052.05 元 → 节省 26.90%
- 校验：平衡残差 2.3e-13 kWh；SOC ∈ [1200, 10800]；s(0:00)=s(24:00)=6000 kWh

## 口径备注

- 功率 × 1/6 转为 10 min 时段电量（kWh）后进入模型，全程不混用 kW/kWh
- 附件 1 时间标签视为时段结束时刻。官方 result1 模板的时段文字整体后移 10 min；代码保持源数据顺序填充且不改模板表头，完整映射见 `q1_time_mapping.csv`
- 第一阶段目标只含真实购电费；第二阶段在 `C1 <= C1* + 0.0001 元` 下最小化充放电吞吐量，避免正价格被人为吞吐系数改变
- 储能边际价值按 `v_t=-mu_soc_t` 定义，单位为元/kWh，是 Q1 最优基附近“向 SOC 注入 1 kWh 免费可用电量”的局部价值。Q2 不应直接把这 144 个数固定进目标函数，而应在每个净负荷场景中重新求 SOC 对偶值，再计算 `E[v_t]` 与 P10/P50/P90；Q1 表只作基准、初始化或合理性核验
- DP 离散化不是主模型的必要校验，当前不纳入正式代码；MILP 仅用于同等费用下的模式切换对照
