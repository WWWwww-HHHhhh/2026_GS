# -*- coding: utf-8 -*-
"""重建「场景源隔离」文件（一次性维护脚本，位于 Q4_wyh/others/）。

背景：05_q4_scenarios.py 固定输出 scenarios_M{M}.pkl，无法同时保留两套光伏预报源。
本脚本调用其 build() 分别生成 q2 与 official 两套，并副本命名为：
    scenarios_M{M}_q2.pkl / scenarios_M{M}_official.pkl
最后把主口径 scenarios_M{M}.pkl 还原为 q2 源，保证既有主口径产物与文件一致。

运行：python rebuild_scenario_sources.py
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

WYH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WYH / "Data_processing"))

spec = importlib.util.spec_from_file_location("q4_scen", WYH / "Data_processing" / "05_q4_scenarios.py")
q4_scen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q4_scen)

D = WYH / "Data_processing"
M_LIST = (10, 20, 30)
SOURCES = ("q2", "official")

for src in SOURCES:
    for M in M_LIST:
        cache = q4_scen.build(M, src)
        produced = D / f"scenarios_M{M}.pkl"
        target = D / f"scenarios_M{M}_{src}.pkl"
        shutil.copyfile(produced, target)
        print(f"  [{src:8s} M={M:2d}] -> {target.name}  "
              f"（pv_source={cache['pv_source']}）", flush=True)

# 主口径还原为 q2
for M in M_LIST:
    shutil.copyfile(D / f"scenarios_M{M}_q2.pkl", D / f"scenarios_M{M}.pkl")
print("  主口径 scenarios_M*.pkl 已还原为 q2 源")
