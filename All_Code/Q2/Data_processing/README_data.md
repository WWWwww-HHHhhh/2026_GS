# q2_dataset.pkl 字段说明

- 数据来源: E:\2.University_materials\4.University_life\6.Study_materials\others\freshman_year(secong semester)\2026_GS\All_Code\Data_preprocessing\Data_transformation（负荷/光伏已换算 kWh，电价 元/kWh）
- dates / date_str: 日期 2025-01-01..12-31（共 365 天）
- price: (144 x 365) 固定日内电价矩阵，元/kWh，来源附件1，全年复用
- load: (144 x 365) 负荷电量 kWh（已换算）
- pv: (144 x 365) 光伏电量 kWh（已换算）
- time_mapping: internal_idx/time_labels/template_col/template_labels
- kappa2_base / kappa2_stats: 软终端罚系数基准与统计量
- constants: T/D/Delta_t/充放电上限/效率/SOC 边界/初始 SOC
