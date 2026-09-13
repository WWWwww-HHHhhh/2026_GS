# 追查 0.63% 的来源

## 1 q4_2_paper_numbers.csv 里与紧急购电率有关的行

- 稳健性·β,β 扫描 β=0.0（风险中性→保守）：总费用 / CVaR90 / 紧急购电率,"15,380,885 元 / 76,875 元 / 0.685%",q4_2_experiments.csv
- 稳健性·β,β 扫描 β=0.05（风险中性→保守）：总费用 / CVaR90 / 紧急购电率,"15,401,598 元 / 76,834 元 / 0.650%",q4_2_experiments.csv
- 稳健性·β,β 扫描 β=0.1（风险中性→保守）：总费用 / CVaR90 / 紧急购电率,"15,443,453 元 / 77,002 元 / 0.623%",q4_2_experiments.csv
- 稳健性·β,β 扫描 β=0.25（风险中性→保守）：总费用 / CVaR90 / 紧急购电率,"15,590,765 元 / 78,529 元 / 0.577%",q4_2_experiments.csv
- 稳健性·β,β 扫描 β=0.5（风险中性→保守）：总费用 / CVaR90 / 紧急购电率,"15,827,534 元 / 80,922 元 / 0.544%",q4_2_experiments.csv
- 稳健性·M,场景数扫描 M=10：总费用 / 紧急购电率,"15,719,207 元 / 0.767%",q4_2_experiments.csv
- 稳健性·M,场景数扫描 M=20：总费用 / 紧急购电率,"15,550,534 元 / 0.632%",q4_2_experiments.csv
- 稳健性·M,场景数扫描 M=30：总费用 / 紧急购电率,"15,561,930 元 / 0.587%",q4_2_experiments.csv

## 2 q4_2_experiments.csv 的紧急购电率列

- 率相关列：紧急购电率(%)、弃光率(%)
```
                            实验  紧急购电率(%)    弃光率(%)
                主模型 Q4-2（选中配置）  0.586677 10.276798
       B0 完美信息对照方案（当日实际值，逐日求解）       NaN       NaN
   B2 实时市场即时购电（假想：无 0:00 计划承诺）  0.000000       NaN
B2' 无计划·全额紧急购电（题目规则 5× 交易时刻电价） 56.737204       NaN
                  B3 典型日(Q1)策略       NaN       NaN
        B4 全量提取口径（y≡x）—— 不可行诊断       NaN       NaN
                    B1 Q2固定价策略  0.588052 10.382213
           β 扫描 β=0.0（风险中性→保守）  0.685017  9.649037
          β 扫描 β=0.05（风险中性→保守）  0.650345  9.855309
           β 扫描 β=0.1（风险中性→保守）  0.623456 10.018228
          β 扫描 β=0.25（风险中性→保守）  0.576934 10.364098
           β 扫描 β=0.5（风险中性→保守）  0.543828 10.743722
                    场景数扫描 M=10  0.766846 10.110882
                    场景数扫描 M=20  0.631637 10.247389
                    场景数扫描 M=30  0.586677 10.276798
                 价格不确定度注入 ×0.7  0.585202 10.281458
                 价格不确定度注入 ×1.3  0.588537 10.274457
```

## 3 全部 V_* 汇总文件与它们的总费用

| 文件 | 总费用(元) | 紧急购电率(%) |
| --- | --- | --- |
| V_cap8000_summary.csv | 15553009.61 | 0.634 |
| V_official_known_q2params_summary.csv | 15504400.92 | 0.606 |
| V_official_known_summary.csv | 15479035.55 | 0.774 |
| V_official_unknown_q2params_summary.csv | 15728958.76 | 0.654 |
| V_official_unknown_summary.csv | 15621547.97 | 0.774 |
| V_q2_known_q2params_summary.csv | 15345273.08 | 0.581 |
| V_q2_known_summary.csv | 15252994.27 | 0.709 |
| V_q2_unknown_risk_summary.csv | 15444173.44 | 0.723 |

## 4 主模型那一格（价格未知 + 自建预报）的文件名

- `V_official_known_q2params_daily.csv`
- `V_official_known_q2params_summary.csv`
- `V_official_unknown_q2params_daily.csv`
- `V_official_unknown_q2params_summary.csv`
- `V_q2_known_daily.csv`
- `V_q2_known_q2params_daily.csv`
- `V_q2_known_q2params_summary.csv`
- `V_q2_known_summary.csv`
- `V_q2_known_tuning.xlsx`
- `V_q2_unknown_risk_daily.csv`
- `V_q2_unknown_risk_summary.csv`
- `V_q2_unknown_risk_tuning.xlsx`
