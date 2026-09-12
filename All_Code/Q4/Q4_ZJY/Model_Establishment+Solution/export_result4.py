"""Q4-3 导出驱动：修正 metadata → 复核 → payload → 写 result4-3.xlsx → 工作簿校验。

复用 Q3 导出链（validate_q3 / prepare_result3 / build_result3），模板换 result4-3.xlsx，
工作簿校验用 Q4 的 validate_result4_workbook.py。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q3_CODE = HERE.parents[2] / "Q3" / "Model_Establishment+Solution"
sys.path.insert(0, str(Q3_CODE))
TABLES = HERE.parent / "Results" / "Tables"
TEMPLATE = HERE.parents[3] / "Data" / "附件" / "附件5" / "result4-3.xlsx"
OUT_XLSX = TABLES / "result4-3.xlsx"
PY = sys.executable


def fix_metadata() -> None:
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
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[fix_metadata] run_metadata.json 已含 source_hashes 与 strategies")


def run(script: Path, *args) -> None:
    cmd = [PY, str(script)] + [str(a) for a in args]
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    fix_metadata()
    run(HERE / "validate_q4.py", "--folder", TABLES)
    run(HERE / "prepare_result4.py", "--folder", TABLES, "--strategy", "S6_12")
    run(Q3_CODE / "build_result3.py", "--folder", TABLES, "--template", TEMPLATE, "--out", OUT_XLSX)
    run(HERE / "validate_result4_workbook.py")
    print(f"\nresult4-3.xlsx 已生成并通过工作簿校验: {OUT_XLSX}")


if __name__ == "__main__":
    main()
