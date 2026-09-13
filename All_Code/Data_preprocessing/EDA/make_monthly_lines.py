from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
CLEAN = HERE.parent / "Data_clean"
OUT = HERE.parents[2] / "Figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["pdf.fonttype"] = 42


def monthly_mean(filename: str) -> np.ndarray:
    df = pd.read_csv(CLEAN / filename)
    months = pd.to_datetime(df.iloc[:, 0]).dt.month
    values = df.iloc[:, 1:].astype(float)
    return np.array(
        [values.loc[months.eq(month)].to_numpy().mean() for month in range(1, 13)]
    )


months = np.arange(1, 13)
series = [
    (monthly_mean("附件2_load_clean.csv"), "(a) 负荷", "月均功率（kW）", "#3F72AF"),
    (monthly_mean("附件2_pv_clean.csv"), "(b) 光伏", "月均功率（kW）", "#2F8F67"),
    (monthly_mean("附件4_clean.csv"), "(c) 电价", "月均电价（元/kWh）", "#D05A4E"),
]

fig, axes = plt.subplots(1, 3, figsize=(10.0, 3.0))

for ax, (values, title, ylabel, color) in zip(axes, series):
    value_range = float(values.max() - values.min())
    lower = float(values.min() - 0.22 * value_range)
    upper = float(values.max() + 0.25 * value_range)

    ax.set_facecolor("#FAFBFC")
    ax.fill_between(months, lower, values, color=color, alpha=0.11, zorder=1)
    line, = ax.plot(
        months,
        values,
        color=color,
        linewidth=2.15,
        marker="o",
        markersize=5.2,
        markerfacecolor="white",
        markeredgecolor=color,
        markeredgewidth=1.6,
        zorder=3,
    )
    line.set_path_effects([
        pe.SimpleLineShadow(offset=(1.2, -1.2), alpha=0.18),
        pe.Normal(),
    ])

    maximum = int(np.argmax(values))
    minimum = int(np.argmin(values))
    fmt = "{:.2f}" if "电价" in title else "{:.0f}"
    for index in (minimum, maximum):
        ax.scatter(
            months[index], values[index], s=48, color=color,
            edgecolor="white", linewidth=1.1, zorder=4,
        )
        offset = 8 if index == maximum else -13
        va = "bottom" if index == maximum else "top"
        ax.annotate(
            fmt.format(values[index]),
            (months[index], values[index]),
            xytext=(0, offset),
            textcoords="offset points",
            ha="center",
            va=va,
            fontsize=8,
            fontweight="bold",
            color="#263238",
        )

    ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold", pad=8)
    ax.set_ylabel(ylabel, fontsize=8.5)
    ax.set_xlabel("月份", fontsize=8.5)
    ax.set_xlim(0.6, 12.4)
    ax.set_ylim(lower, upper)
    ax.set_xticks([1, 3, 5, 7, 9, 11, 12])
    ax.tick_params(axis="both", labelsize=7.5, length=0)
    ax.grid(axis="y", color="#CAD3D6", linewidth=0.6, alpha=0.7)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#AEB8BA")

fig.suptitle("负荷、光伏与电价的月均变化", x=0.065, ha="left", fontsize=12)
fig.subplots_adjust(left=0.07, right=0.995, bottom=0.20, top=0.78, wspace=0.34)

output = OUT / "fig_monthly_features.pdf"
fig.savefig(output, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(output)
