from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# All_Code/Q4/Q4_ZJY/Model_Establishment+Solution/q4_data.py
# parents: [0]=Model_Establishment+Solution [1]=Q4_ZJY [2]=Q4 [3]=All_Code [4]=2026_GS
REPO = Path(__file__).resolve().parents[4]
ATTACH4 = REPO / "Data" / "附件" / "附件4.xlsx"
T, D = 144, 365


def load_q4_price() -> np.ndarray:
    """读附件 4 波动电价，返回 shape (144, 365) 的电价矩阵（元/kWh）。

    日期对齐：附件 4 第 day+1 行对应 day（2025-01-01=day0，2025-02-01=day31）。
    按位置取列 iloc[:, 1:145]，跳过最后一列的字符串表头 `0:00+1`。
    """
    df = pd.read_excel(ATTACH4, header=0)
    # 校验日期行
    dates = pd.to_datetime(df.iloc[:, 0])
    assert len(dates) == D, f"附件4 天数 {len(dates)} != {D}"
    assert dates.iloc[0].strftime("%Y-%m-%d") == "2025-01-01"
    assert dates.iloc[-1].strftime("%Y-%m-%d") == "2025-12-31"

    price = df.iloc[:, 1:145].to_numpy(dtype=float).T  # (144, 365)
    assert price.shape == (T, D), f"price shape {price.shape} != ({T},{D})"
    assert np.isfinite(price).all(), "附件4 电价含非有限值"
    assert (price > 0).all(), "附件4 电价含非正值（结算要求正电价）"
    return price


if __name__ == "__main__":
    p = load_q4_price()
    print(f"附件4 波动电价: shape={p.shape}")
    print(f"  范围 [{p.min():.4f}, {p.max():.4f}] 元/kWh, 均值 {p.mean():.4f}")
    print(f"  日均价: min {p.mean(0).min():.4f}  max {p.mean(0).max():.4f}")
    print(f"  日内极差(max-min): 均值 {np.ptp(p, axis=0).mean():.4f}")
