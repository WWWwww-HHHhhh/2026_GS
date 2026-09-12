"""Evaluate official issue-time PV forecasts without using formal days to tune them."""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

from q3_core import ISSUES, PVForecast, SourceData

HERE=Path(__file__).resolve().parent


def main() -> None:
    data=SourceData.load_verified()
    records=[]
    for method in ("linear_endpoint","step"):
        converter=PVForecast(data,method)
        for issue in ISSUES:
            pred=np.stack([converter.get(day,issue) for day in range(31,365)])
            actual=data.pv[issue:,31:].T
            error=pred-actual
            records.append({"conversion":method,"issue_hour":issue//6,
                            "days":334,"future_slots_per_day":144-issue,
                            "MAE_kwh_per_slot":float(np.mean(np.abs(error))),
                            "WAPE":float(np.sum(np.abs(error))/np.sum(actual)),
                            "bias_kwh_per_slot":float(np.mean(error))})
    pd.DataFrame(records).to_csv(HERE/"results"/"forecast_conversion_audit.csv",
                                 index=False,encoding="utf-8-sig")
    print(pd.DataFrame(records).to_string(index=False))


if __name__=="__main__":
    main()
