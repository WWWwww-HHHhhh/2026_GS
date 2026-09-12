"""Q3 公共配置与路径定义。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


T = 144
DT_HOURS = 1.0 / 6.0
OFFICIAL_UPDATE_HOURS = (0, 6, 12, 18)
OFFICIAL_UPDATE_SLOTS = tuple(hour * 6 for hour in OFFICIAL_UPDATE_HOURS)


@dataclass(frozen=True)
class ProjectPaths:
    repo_root: Path
    q3_root: Path
    clean_data: Path
    result_tables: Path
    result_pictures: Path

    @classmethod
    def discover(cls) -> "ProjectPaths":
        q3_root = Path(__file__).resolve().parents[1]
        repo_root = Path(__file__).resolve().parents[3]
        return cls(
            repo_root=repo_root,
            q3_root=q3_root,
            clean_data=repo_root / "All_Code" / "Data_preprocessing" / "Data_clean",
            result_tables=q3_root / "Results" / "Tables",
            result_pictures=q3_root / "Results" / "Pictures",
        )


@dataclass(frozen=True)
class ModelConfig:
    """所有能影响模型口径的参数集中在这里。"""

    eta_charge: float = 0.9
    eta_discharge: float = 0.9
    storage_min_kwh: float = 1200.0
    storage_max_kwh: float = 10800.0
    storage_power_kwh: float = 833.3333333333
    initial_soc_kwh: float = 6000.0
    terminal_target_kwh: float = 6000.0
    terminal_penalty_cny_per_kwh: float = 0.531667
    emergency_multiplier: float = 5.0
    cvar_alpha: float = 0.9
    cvar_weight: float = 0.0
    numerical_tie_breaker: float = 1.0e-8


STRATEGY_UPDATES = {
    "S0": (0,),
    "S06": (0, 6),
    "S012": (0, 12),
    "S018": (0, 18),
    "S0612": (0, 6, 12),
    "Sall": (0, 6, 12, 18),
}
