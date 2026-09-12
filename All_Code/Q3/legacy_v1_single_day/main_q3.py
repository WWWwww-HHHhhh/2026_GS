"""Q3 命令行入口。

示例
python main_q3.py --date 2025-03-20 --strategy Sall --quick
python main_q3.py --date 2025-03-20 --compare --quick
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


Q3_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DEPS = Q3_ROOT / ".deps"
if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))

import pandas as pd

from config import STRATEGY_UPDATES, ModelConfig, ProjectPaths
from data import load_dataset
from export import export_day
from rolling import simulate_day
from validate import validate_day


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 Q3 多时点滚动购电模型")
    parser.add_argument("--date", default="2025-03-20", help="仿真日期，格式 YYYY-MM-DD")
    parser.add_argument("--strategy", choices=tuple(STRATEGY_UPDATES), default="Sall")
    parser.add_argument("--scenarios", type=int, default=30)
    parser.add_argument("--storage-step", type=int, default=1, help="每隔多少个区间重算储能")
    parser.add_argument("--beta", type=float, default=0.0, help="CVaR 权重")
    parser.add_argument("--alpha", type=float, default=0.9, help="CVaR 置信水平")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--compare", action="store_true", help="比较全部预设更新策略")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="使用 5 个场景并每 12 个区间重算储能，仅用于烟雾测试",
    )
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    scenario_count = 5 if args.quick else args.scenarios
    storage_step = 12 if args.quick else args.storage_step
    model_config = ModelConfig(cvar_weight=args.beta, cvar_alpha=args.alpha)
    paths = ProjectPaths.discover()
    dataset = load_dataset(paths)
    strategies = tuple(STRATEGY_UPDATES) if args.compare else (args.strategy,)
    summaries = []

    for strategy in strategies:
        simulation = simulate_day(
            dataset=dataset,
            date=args.date,
            strategy=strategy,
            scenario_count=scenario_count,
            storage_reopt_every=storage_step,
            config=model_config,
            seed=args.seed,
        )
        validation = validate_day(simulation, model_config)
        workbook, metadata = export_day(
            simulation,
            validation,
            paths=paths,
            tag="quick" if args.quick else "run",
        )
        summaries.append({**simulation.summary, "校验通过": validation["passed"]})
        print(
            json.dumps(
                {
                    "strategy": strategy,
                    "workbook": str(workbook),
                    "metadata": str(metadata),
                    "summary": simulation.summary,
                    "validation": validation,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    if len(summaries) > 1:
        comparison_path = paths.result_tables / f"Q3_strategy_comparison_{args.date}.xlsx"
        pd.DataFrame(summaries).sort_values("总费用_元").to_excel(
            comparison_path, index=False
        )
        print(f"策略对比已写入 {comparison_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
