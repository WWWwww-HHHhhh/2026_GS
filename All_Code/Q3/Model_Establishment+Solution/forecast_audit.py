from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from q3_core import ISSUES, PVForecast, SourceData

HERE = Path(__file__).resolve().parent
TABLES = HERE.parent / "Results" / "Tables"


def audit(data: SourceData, day_range) -> pd.DataFrame:
    days = list(day_range)
    lo = days[0]
    records = []
    for method in ("linear_endpoint", "step"):
        converter = PVForecast(data, method)
        for issue in ISSUES:
            pred = np.stack([converter.get(day, issue) for day in days])
            actual = data.pv[issue:, lo:lo + len(days)].T
            error = pred - actual
            records.append({
                "conversion": method, "issue_hour": issue // 6,
                "days": len(days), "future_slots_per_day": 144 - issue,
                "MAE_kwh_per_slot": float(np.mean(np.abs(error))),
                "WAPE": float(np.sum(np.abs(error)) / np.sum(actual)),
                "bias_kwh_per_slot": float(np.mean(error)),
            })
    return pd.DataFrame(records)


def main() -> None:
    data = SourceData.load_verified()
    TABLES.mkdir(parents=True, exist_ok=True)

    # Selection evidence: January history (day 1-30), strictly before the formal window.
    jan = audit(data, range(1, 31))
    jan.to_csv(TABLES / "forecast_conversion_audit_jan.csv", index=False, encoding="utf-8-sig")

    # Diagnosis only: formal Feb-Dec backtest period (day 31-364); NOT used for selection.
    formal = audit(data, range(31, 365))
    formal.to_csv(TABLES / "forecast_conversion_audit.csv", index=False, encoding="utf-8-sig")

    print("== January selection window (method-choice evidence) ==")
    print(jan.to_string(index=False))
    print("\n== Formal Feb-Dec diagnostic window ==")
    print(formal.to_string(index=False))


if __name__ == "__main__":
    main()
