"""Q4-3 波动电价下的滚动购电优化：复用 Q3 模型，仅把电价向量换成附件 4 的每日波动电价。

复用方式：import Q3 的 q3_core（SourceData/PVForecast/scenarios/solve_window/execute_slot）
与 run_q3.backtest_strategy（六策略全年滚动回测驱动）。唯一改动是构造 SourceData 后
用附件 4 的波动电价替换 price 字段；负荷/光伏实际（附件2）、光伏预报（附件3）、
负荷预测与残差（Q2_yy）、模型与参数（M=30,α=0.9,β=0.2,κ₂）全部与 Q3 一致，保证可比。

电价信息假设：附件 4 为日前价格，0:00 制定计划时当日 144 时段电价已知（确定量，非随机）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
# All_Code/Q4/Q4_ZJY/Model_Establishment+Solution → All_Code/Q3/Model_Establishment+Solution
Q3_CODE = HERE.parents[2] / "Q3" / "Model_Establishment+Solution"
sys.path.insert(0, str(Q3_CODE))

from q3_core import PVForecast, SourceData, STRATEGIES  # noqa: E402
from run_q3 import backtest_strategy, sha256, verify_sources  # noqa: E402

from q4_data import ATTACH4, load_q4_price  # noqa: E402

OUT = HERE.parent / "Results" / "Tables"
Q3_FIXED_PRICE_TOTAL = 14517640.171605363  # Q3 固定电价 Sall 总费用（对比基线）


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategies", nargs="+", choices=tuple(STRATEGIES), default=list(STRATEGIES))
    parser.add_argument("--start", default="2025-02-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--settlement", choices=["net", "gross"], default="net")
    parser.add_argument("--outdir", type=Path, default=OUT)
    args = parser.parse_args()

    started = time.perf_counter()
    data = SourceData.load_verified()  # 附件2负荷/光伏 + 附件3预报 + Q2_yy预测/残差（price 暂为附件1）
    data.price = load_q4_price()       # Q4 唯一改动：替换为附件4波动电价

    start_day = data.dates.index(args.start)
    end_day = data.dates.index(args.end) + 1
    forecast = PVForecast(data, "linear_endpoint")
    args.outdir.mkdir(parents=True, exist_ok=True)
    source_hashes = verify_sources(data)  # Q2 result2 + 附件1/2/3 的哈希
    source_hashes["attachment4_sha256"] = sha256(ATTACH4)  # Q4 新增：附件4 波动电价

    summaries = []
    for name in args.strategies:
        s = backtest_strategy(data, forecast, name, args.outdir, start_day, end_day,
                              settlement=args.settlement)
        summaries.append(s)

    pd.DataFrame(summaries).to_csv(args.outdir / "strategy_summary.csv", index=False, encoding="utf-8-sig")
    meta = {
        "problem": "Q4-3 波动电价下的问题三（复用 Q3 模型，仅替换电价向量）",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "price_source": "附件4 每日波动电价（日前价格，0:00 已知）",
        "settlement": args.settlement, "forecast_method": "linear_endpoint",
        "report_start": args.start, "report_end": args.end, "strategies": args.strategies,
        "source_hashes": source_hashes,
        "q3_fixed_price_Sall_total_yuan": Q3_FIXED_PRICE_TOTAL,
        "elapsed_seconds": time.perf_counter() - started,
    }
    (args.outdir / "run_metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"elapsed_seconds": meta["elapsed_seconds"],
                      "summaries": [{k: s[k] for k in ("strategy", "total_cost_yuan", "emergency_kwh",
                                                       "curtail_kwh")} for s in summaries]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
