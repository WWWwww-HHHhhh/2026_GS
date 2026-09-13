# Q4_wyhnew 路径解析自检

按 `q4_common.py` 的定位规则解析出的关键路径：

| 常量 | 解析结果（相对 Q4_wyhnew） | 存在 |
| --- | --- | --- |
| `REPO（仓库根）` | `.` | 是 |
| `WYH（工作区）` | `.` | 是 |
| `TRANS` | `All_Code\Data_preprocessing\Data_transformation` | 是 |
| `Q2_DIR` | `All_Code\Q2_yy\Data_processing` | 是 |
| `ATTACH_RAW` | `others\原始附件_CUMCM2026_C\附件` | 是 |
| `OUT_DATA` | `Data_processing` | 是 |
| `TABLES` | `Results\Tables` | 是 |
| `PICTURES` | `Results\Pictures` | 是 |
| `MODELDIR` | `Model_Establishment+Solution` | 是 |

## 关键输入文件是否齐备

| 文件 | 大小 |
| --- | --- |
| `Data_processing\q4_dataset.pkl` | 2.43 MB |
| `Data_processing\price_forecast.pkl` | 0.83 MB |
| `Data_processing\scenarios_M30_official.pkl` | 37.29 MB |
| `Data_processing\scenarios_M30_q2.pkl` | 37.29 MB |
| `Data_processing\scenarios_M30.pkl` | 37.29 MB |
| `Data_processing\variants\V_official_unknown_q2params_results.pkl` | 4.98 MB |
| `Data_processing\q4_2_rolling_results.pkl` | 38.06 MB |
| `Results\Tables\result4-2.xlsx` | 0.64 MB |
| `Results\Pictures\fig_q4_representative_day.pdf` | 0.05 MB |
| `All_Code\Data_preprocessing\Data_transformation\df_load.parquet` | 0.50 MB |
| `All_Code\Data_preprocessing\Data_transformation\time_map.csv` | 0.01 MB |
| `All_Code\Q2_yy\Data_processing\q2_dataset.pkl` | 1.22 MB |
| `All_Code\Q2_yy\Data_processing\forecasts.pkl` | 0.83 MB |
| `others\原始附件_CUMCM2026_C\附件\附件1.xlsx` | 0.02 MB |
| `others\原始附件_CUMCM2026_C\附件\附件4.xlsx` | 0.39 MB |
| `All_Code\Q1\Results\Tables\result1.xlsx` | 0.01 MB |

## 结论

- 全部关键路径都落在 Q4_wyhnew 内部：**是**
- 脚本的 `find_repo_root()` 会把 Q4_wyhnew 认作仓库根，因此无需改动任何源码即可在本目录独立运行。
- 本次未运行任何模型或数据处理脚本（按要求先不写代码）。