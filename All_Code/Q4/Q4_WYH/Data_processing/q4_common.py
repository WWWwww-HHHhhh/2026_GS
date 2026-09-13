from __future__ import annotations

import hashlib
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- 口径常量
T = 144                      # 每自然日 10 分钟时段数（不可改为 145）
D = 365                      # 2025 全年天数
DELTA_T = 1.0 / 6.0          # 每时段小时数
ETA_C = ETA_R = 0.9          # 充/放效率
SOC_MIN, SOC_MAX = 1200.0, 10800.0
SOC0 = 6000.0                # 2025-01-01 00:00 初始储电量
CHARGE_CAP = 5000.0 * DELTA_T  # 833.3333... kWh/时段
HISTORY_WINDOW = 30          # 场景残差块的回看天数（严格早于决策日）

REPORT_START, REPORT_END = "2025-02-01", "2025-12-31"
CALIB_START, CALIB_END = "2025-01-15", "2025-01-31"

T_COLS = [f"T{i:03d}" for i in range(1, T + 1)]
FH_COLS = [f"fh_{i:02d}" for i in range(1, 25)]
SEED = 20260101

# 储能六段（自然日口径，不做跨行移位）
BAND_SLICES = [(0, 24), (24, 48), (48, 72), (72, 96), (96, 120), (120, 144)]
BAND_LABELS = ["0:00-4:00", "4:00-8:00", "8:00-12:00", "12:00-16:00", "16:00-20:00", "20:00-24:00"]


# ---------------------------------------------------------------- 路径
def find_repo_root() -> Path:
    """向上查找同时含 Data/附件 与 All_Code/Data_preprocessing 的仓库根。"""
    here = Path(__file__).resolve()
    for cand in [here, *here.parents]:
        if (cand / "Data" / "附件").is_dir() and (cand / "All_Code" / "Data_preprocessing").is_dir():
            return cand
    raise FileNotFoundError("无法定位仓库根（需同时存在 Data/附件 与 All_Code/Data_preprocessing）")


REPO = find_repo_root()
WYH = Path(__file__).resolve().parents[1]          # All_Code/Q4/Q4_WYH
TRANS = REPO / "All_Code" / "Data_preprocessing" / "Data_transformation"
Q2_DIR = REPO / "All_Code" / "Q2_yy" / "Data_processing"
ATTACH_RAW = WYH / "others" / "原始附件_CUMCM2026_C" / "附件"
OUT_DATA = WYH / "Data_processing"
TABLES = WYH / "Results" / "Tables"
PICTURES = WYH / "Results" / "Pictures"
MODELDIR = WYH / "Model_Establishment+Solution"


# ---------------------------------------------------------------- 工具
def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_pickle_compat(path: Path):
    """读取可能由旧版 pandas 写出的 pickle；失败时才打补丁，成功后校验。"""
    path = Path(path)
    try:
        with open(path, "rb") as fh:
            return pickle.load(fh)
    except (TypeError, AttributeError, ValueError):
        pass

    from pandas.core.internals import blocks as _blocks
    from pandas.core.internals.blocks import BlockPlacement

    orig = _blocks.new_block

    def patched(values, placement, ndim=2, refs=None):
        if isinstance(placement, slice):
            placement = BlockPlacement(placement)
        elif not isinstance(placement, BlockPlacement):
            try:
                placement = BlockPlacement(list(placement))
            except Exception:  # noqa: BLE001
                placement = BlockPlacement(slice(0, len(values)))
        return orig(values, placement, ndim=ndim, refs=refs)

    _blocks.new_block = patched
    try:
        import pandas.core.internals.managers as _mgr
        if hasattr(_mgr, "new_block"):
            _mgr.new_block = patched
    except Exception:  # noqa: BLE001
        pass
    with open(path, "rb") as fh:
        return pickle.load(fh)


def wide_to_matrix(df: pd.DataFrame) -> np.ndarray:
    """标准宽表 (D, 1+144) -> (144, D)：列 T001..T144 对应物理区间 0:00-0:10 .. 23:50-24:00。"""
    missing = [c for c in T_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"缺少时段列: {missing[:5]}")
    return df[T_COLS].to_numpy(dtype=float).T


def interval_labels() -> list[str]:
    """144 个物理区间标签（右端点规则）：0:00-0:10 … 23:50-24:00。"""
    labels = []
    for t in range(T):
        a, b = t * 10, (t + 1) * 10
        fmt = lambda m: f"{m // 60}:{m % 60:02d}" if m < 1440 else "24:00"  # noqa: E731
        labels.append(f"{fmt(a)}-{fmt(b)}")
    return labels


def load_dataset() -> dict:
    """读取 03_q4_dataset.py 产出的数据集，并做最小完整性校验。"""
    p = OUT_DATA / "q4_dataset.pkl"
    if not p.exists():
        raise FileNotFoundError(f"缺少数据集 {p}，请先运行 Data_processing/03_q4_dataset.py")
    ds = load_pickle_compat(p)
    need = ["load", "pv", "price", "Lhat", "Ghat", "Ghat_official", "report_idx", "calib_idx", "constants"]
    missing = [k for k in need if k not in ds]
    if missing:
        raise KeyError(f"数据集缺少字段: {missing}")
    for k in ["load", "pv", "price", "Lhat", "Ghat", "Ghat_official"]:
        if ds[k].shape != (T, D):
            raise ValueError(f"{k} 形状异常 {ds[k].shape}，应为 ({T},{D})")
    return ds
