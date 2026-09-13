from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from config import ProjectPaths
from rolling import DaySimulation


def export_day(
    simulation: DaySimulation,
    validation: dict[str, float | int | bool],
    paths: ProjectPaths | None = None,
    tag: str = "smoke",
) -> tuple[Path, Path]:
    paths = paths or ProjectPaths.discover()
    paths.result_tables.mkdir(parents=True, exist_ok=True)
    stem = f"Q3_{tag}_{simulation.date}_{simulation.strategy}"
    workbook_path = paths.result_tables / f"{stem}.xlsx"
    metadata_path = paths.result_tables / f"{stem}.json"

    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        simulation.intervals.to_excel(writer, sheet_name="逐时结果", index=False)
        simulation.updates.to_excel(writer, sheet_name="官方更新", index=False)
        pd.DataFrame([simulation.summary]).to_excel(writer, sheet_name="汇总", index=False)
        pd.DataFrame([validation]).to_excel(writer, sheet_name="校验", index=False)

    payload = {
        "summary": simulation.summary,
        "validation": validation,
        "note": "本文件是代码烟雾测试输出，不作为论文最终数值，最终数值须完成全年策略回测后确定。",
    }
    metadata_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return workbook_path, metadata_path
