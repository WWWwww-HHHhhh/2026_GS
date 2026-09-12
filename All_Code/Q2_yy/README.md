# Q2_yy 严格因果优化版

本目录由 `All_Code/Q2` 派生，保留“两阶段随机线性规划 + CVaR + 跨日滚动 SOC”主体，并统一日前优化与实际执行口径。

## 数据与时间边界

- 电价直接读取附件1；负荷与光伏直接读取附件2，kW 只乘 `1/6` 转为每10分钟 kWh，不插值、不补值。
- 日前预测只能使用截至前一天的数据；场景只能抽取决策日前最近30个已结束日的负荷—光伏联合残差块。
- 参数仅用 2025-01-15 至 2025-01-31 验证，2025-02-01 至 2025-12-31 共334天只作报告，禁止反向选参。
- 实际结算逐10分钟原样执行0:00确定的充放电计划，只使用当前时段已经实现的负荷、光伏和期初SOC，不读取当天未来时段；供给过剩显式记为弃电。
- 跨日状态从题目给定的2025-01-01 0:00、6000 kWh开始连续传递；2025-12-31 24:00硬约束回到6000 kWh，全年费用不依赖耗空期初储能。

## 已验证结果

- 计划购电费：13,885,012.62 元
- 紧急购电费：823,950.87 元
- 实际支付总费用：14,708,963.49 元
- 年末SOC：6,000.00 kWh（硬约束，期末修正为0）
- 原Q2总费用：15,637,529.82 元；原Q2紧急购电费：839,786.46 元

以 `Results/Tables/validation_report.txt` 和 `validated_cost_summary.csv` 为最终证据，不使用废弃的 `run_summary.txt`。

## 复现

使用项目可用的 Python 环境依次运行：`Data_processing/q2_data_prepare.py`、`Model_Establishment+Solution/forecast.py`、三次 `scenarios.py --M 10/20/30`、`rolling.py`、`export.py`、`validate.py`。

## 论文图

出图脚本为 `Results/Pictures/make_figures_q2.py`，只读取上一步产出的 `Data_processing/*.pkl` 与 `Results/Tables/forecast_monthly_metrics.csv`，不重新求解、不调参：

```bash
cd Results/Pictures
python make_figures_q2.py
```

每张图同时输出 PDF（投稿用，TrueType 嵌字、可检索）与 PNG（预览用），共 6 张：

| 文件 | 图型 | 说明 |
| --- | --- | --- |
| `fig_q2_load_pv_fan` | 四联折线 + 场景带 | 两个代表日的负荷/光伏日前预测、实际与 P5–P95 场景区间，各幅标注当日 WAPE |
| `fig_q2_error_monthly` | 哑铃图 | 逐月负荷与光伏 WAPE 并排对比，线段长度即两者差距 |
| `fig_q2_plan_settlement` | 子弹图式渐变对照柱 | 紧急购电最严重日：浅色轨道给出满量程参考，渐变蓝柱为实际提取的日前电、柱顶红段为紧急购电，黑色目标刻线为原计划购电量 |
| `fig_q2_soc_heatmap` | 日内中位曲线 + 分位带 + 状态条 | 储能日内节律：上幅为中位 SOC 与 P10–P90，下幅色条标出各小时充/放方向 |
| `fig_q2_emergency_curtailment` | 上下双面板 + 弃光率色条 | 上幅紧急购电、下幅弃光，两栏各自独立纵轴（量级差约 9 倍，柱高不可跨栏比较）；底部窄色条给出月度弃光率 |
| `fig_q2_cvar_frontier` | 散点图 + 色条 | 参数候选在「验证期总费用—紧急购电费」平面的分布，星标为仅用历史期选中的参数 |

> 注：文件名一律沿用旧版，论文 `\includegraphics` 无需改动，但部分图型已更换——
> `fig_q2_soc_heatmap` 由热力图改为日内节律曲线，`fig_q2_error_monthly` 由折线改为哑铃图，
> `fig_q2_plan_settlement` 由三条重叠折线改为渐变对照柱，`fig_q2_emergency_curtailment`
> 由镜像归一化面积带改为上下双面板 + 弃光率色条（归一化后两半高度不可比，会掩盖 9 倍量级差）。
> 所有大面积色块均用 `tint()` 多层叠加做成矢量渐变，在 PDF 里仍是纯矢量（未光栅化）。
