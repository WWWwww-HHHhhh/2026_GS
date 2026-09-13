from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
Q3_CODE = HERE.parents[2] / "Q3" / "Model_Establishment+Solution"
sys.path.insert(0, str(Q3_CODE))
TABLES = HERE.parent / "Results" / "Tables"
TEMPLATE = HERE.parents[3] / "Data" / "附件" / "附件5" / "result4-3.xlsx"
OUT_XLSX = TABLES / "result4-3.xlsx"
PY = sys.executable


def select_strategy() -> str:
    """Use the lowest validated realized cost, not a stale hard-coded label."""
    summary = pd.read_csv(TABLES / "strategy_summary.csv")
    if set(summary["strategy"]) != set(("S0", "S6", "S12", "S18", "S6_12", "Sall")):
        raise RuntimeError("strategy summary is incomplete")
    return str(summary.loc[summary["total_cost_yuan"].idxmin(), "strategy"])


def fix_metadata(selected_strategy: str) -> None:
    """确保 run_metadata.json 含 validate_q3.py 需要的 source_hashes 与 strategies。"""
    from q3_core import STRATEGIES, SourceData  # noqa: E402
    from run_q3 import sha256, verify_sources  # noqa: E402
    from q4_data import ATTACH4  # noqa: E402

    meta_path = TABLES / "run_metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    if "source_hashes" not in meta:
        data = SourceData.load_verified()
        sh = verify_sources(data)
        sh["attachment4_sha256"] = sha256(ATTACH4)
        meta["source_hashes"] = sh
    meta.setdefault("strategies", list(STRATEGIES))
    meta["selected_strategy"] = selected_strategy
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[fix_metadata] run_metadata.json 已含 source_hashes 与 strategies")


def run(script: Path, *args) -> None:
    cmd = [PY, str(script)] + [str(a) for a in args]
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    selected_strategy = select_strategy()
    fix_metadata(selected_strategy)
    run(HERE / "validate_q4.py", "--folder", TABLES)
    run(HERE / "prepare_result4.py", "--folder", TABLES, "--strategy", selected_strategy)
    run(Q3_CODE / "build_result3.py", "--folder", TABLES, "--template", TEMPLATE, "--out", OUT_XLSX)
    run(HERE / "validate_result4_workbook.py", "--strategy", selected_strategy)
    print(f"\nresult4-3.xlsx 已生成并通过工作簿校验，策略: {selected_strategy}，文件: {OUT_XLSX}")


if __name__ == "__main__":
    main()
