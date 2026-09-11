# Experiments（探索实验，非正式提交代码）

本目录只存放优化过程中做过、且全部基于真实附件数据回测的对照实验脚本与中间输出，
正式提交代码统一在 `../Model_Establishment` 与 `../Data_processing`。

- `optimize_q2_*.py`：各轮降本对照实验（beta 扫描、场景窗口、残差缩尺、预测组合、kappa2 扫描等）
- `Outputs/_opt_*.json`：对应实验的真实数值输出
- `Inputs/`：题目与论文文本抽取、结果模板标签核对等分析输入

注意：这里不包含原 `All_Code/Q2` 的任何代码，也不影响正式复现。
