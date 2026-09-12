# 问题三论文表格

本文件夹集中保存问题三指定日期的论文用表格。

- `q3_paper_tables.tex`，可直接插入论文的紧凑 LaTeX 表格，共三张。表1同时列出0:00计划值和日内最终调整值。
- `q3_paper_tables.xlsx`，与 LaTeX 表格对应的数据底稿，另设“补充表_调整购电”工作表便于单独核对。
- `make_q3_paper_tables.mjs`，数据底稿的生成脚本。

数据来源为 `../Tables/result3.xlsx`。

数值口径如下。

- 计划购电量来自“计划购电量”工作表。
- 最终调整购电量来自“调整购电量”工作表。
- 储能结果来自“充放电量”工作表。
- 紧急购电结果来自“紧急购电量”工作表，相邻十分钟记录已在原结果中合并。

LaTeX 文件使用 `\resizebox`、`\rowcolor` 和 `[H]`，主文件需要加载 `graphicx`、`xcolor`、`colortbl` 和 `float` 宏包。
