# -*- coding: utf-8 -*-
"""
可移植路径定义（Q2 -> Q3 数据同步接口）
======================================
依据《Q2到Q3数据同步与自动修改提示词》第三节建立：
禁止继续使用个人 E 盘 / D 盘绝对路径；所有路径均由仓库根目录推导。
本任务新增的 CSV / JSON / XLSX / Markdown 只能写入 Q3_INTERFACE 或 Q3_TABLES，
严禁写入 Q2 的 Data_processing 与 Results/Tables。
"""
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent          # All_Code/Q2/Model_Establishment+Solution
Q2_ROOT = MODEL_DIR.parent                            # All_Code/Q2
REPO_ROOT = Q2_ROOT.parents[1]                        # 仓库根目录（2026_GS）

Q2_DATA_PROCESSING = Q2_ROOT / "Data_processing"
Q2_TABLES = Q2_ROOT / "Results" / "Tables"

Q3_INTERFACE = REPO_ROOT / "All_Code" / "Q3" / "Data_processing" / "Q2_interface"
Q3_TABLES = REPO_ROOT / "All_Code" / "Q3" / "Results" / "Tables"

RESULT2_TEMPLATE = REPO_ROOT / "Data" / "附件" / "附件5" / "result2.xlsx"
Q2_RESULT2_SOURCE = Q2_TABLES / "result2.xlsx"

Q3_INTERFACE.mkdir(parents=True, exist_ok=True)
Q3_TABLES.mkdir(parents=True, exist_ok=True)
