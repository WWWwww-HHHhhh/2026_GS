# -*- coding: utf-8 -*-
"""Q2_yy可移植路径；所有路径由当前文件位置推导。"""
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent          # All_Code/Q2_yy/Model_Establishment+Solution
Q2_ROOT = MODEL_DIR.parent                            # All_Code/Q2_yy
REPO_ROOT = Q2_ROOT.parents[1]                        # 仓库根目录（2026_GS）

Q2_DATA_PROCESSING = Q2_ROOT / "Data_processing"
Q2_TABLES = Q2_ROOT / "Results" / "Tables"

RESULT2_TEMPLATE = REPO_ROOT / "Data" / "附件" / "附件5" / "result2.xlsx"
Q2_RESULT2_SOURCE = Q2_TABLES / "result2.xlsx"
