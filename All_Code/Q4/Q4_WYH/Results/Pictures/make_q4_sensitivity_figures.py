from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "附件汇总" / "Q" / "q4_2_experiments.csv"
OUT = ROOT / "figures"
OUT.mkdir(parents=True, exist_ok=True)


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.sans-serif": [
                "Microsoft YaHei",
                "SimHei",
                "Noto Sans CJK SC",
                "Arial Unicode MS",
                "DejaVu Sans",
            ],
            "axes.unicode_minus": False,
            "font.size": 11,
            "axes.titlesize": 13.5,
            "axes.labelsize": 12,
            "xtick.labelsize": 10.5,
            "ytick.labelsize": 10.5,
            "legend.fontsize": 10.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "#FAFBFC",
            "savefig.facecolor": "white",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def annotate(ax, xs, ys, color, fmt, offsets=None) -> None:
    offsets = offsets or [(0, 8)] * len(xs)
    for x, y, offset in zip(xs, ys, offsets):
        ax.annotate(
            fmt.format(y),
            (x, y),
            xytext=offset,
            textcoords="offset points",
            ha="center",
            va="bottom" if offset[1] >= 0 else "top",
            color=color,
            fontsize=9.5,
            fontweight="semibold",
        )


def finish(fig, stem: str) -> None:
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def beta_figure(df: pd.DataFrame) -> None:
    rows = df[df["实验"].str.startswith("β 扫描")].copy()
    rows["beta"] = rows["实验"].str.extract(r"β=([0-9.]+)")[0].astype(float)

    selected = df[df["实验"].eq("主模型 Q4-2（选中配置）")].iloc[0]
    selected_row = pd.DataFrame(
        {
            "beta": [0.20],
            "总费用(元)": [selected["总费用(元)"]],
            "紧急购电率(%)": [selected["紧急购电率(%)"]],
        }
    )
    rows = pd.concat(
        [rows[["beta", "总费用(元)", "紧急购电率(%)"]], selected_row],
        ignore_index=True,
    ).sort_values("beta")

    x = rows["beta"].to_numpy()
    cost = rows["总费用(元)"].to_numpy() / 1e4
    emergency = rows["紧急购电率(%)"].to_numpy()
    cost_color = "#D05A3A"
    risk_color = "#167D8D"

    fig, ax = plt.subplots(figsize=(9.2, 5.7))
    ax2 = ax.twinx()
    ax2.spines["right"].set_visible(True)

    ax.plot(x, cost, color=cost_color, marker="o", linewidth=2.7,
            markersize=7, label="全年总费用")
    ax2.plot(x, emergency, color=risk_color, marker="s", linewidth=2.7,
             markersize=6.5, label="紧急购电率")
    ax.axvline(0.20, color="#667085", linestyle="--", linewidth=1.2, alpha=0.8)
    ax.scatter([0.20], [cost[x.tolist().index(0.20)]], s=150, marker="*",
               color="#F4B942", edgecolor="#7A5A00", zorder=6)
    ax2.scatter([0.20], [emergency[x.tolist().index(0.20)]], s=115, marker="*",
                color="#F4B942", edgecolor="#7A5A00", zorder=6)

    fig.suptitle("风险权重增大可降低缺口风险，但会推高总费用",
                 y=0.985, fontsize=15, fontweight="bold")
    ax.set_title("自建预测对照口径 · 2025年2—12月",
                 pad=12, color="#667085", fontsize=10)
    ax.set_xlabel(r"风险权重 $\beta$")
    ax.set_ylabel("全年总费用（万元）", color=cost_color)
    ax2.set_ylabel("紧急购电率（%）", color=risk_color)
    ax.tick_params(axis="y", colors=cost_color)
    ax2.tick_params(axis="y", colors=risk_color)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{v:.2f}" for v in x])
    ax.grid(axis="y", color="#D0D5DD", linewidth=0.8, alpha=0.55)

    annotate(ax, x, cost, cost_color, "{:.1f}", [(0, 8)] * len(x))
    annotate(ax2, x, emergency, risk_color, "{:.3f}%", [(0, -12)] * len(x))
    ax.annotate(r"采用 $\beta=0.20$", xy=(0.20, 0.94),
                xycoords=("data", "axes fraction"), ha="center", va="top",
                color="#735600", fontsize=10,
                bbox={"boxstyle": "round,pad=0.25", "fc": "#FFF4C2", "ec": "none"})

    handles = ax.get_lines()[:1] + ax2.get_lines()[:1]
    ax.legend(handles, [h.get_label() for h in handles], loc="upper left", frameon=False, ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    finish(fig, "fig_q4_beta_sensitivity")


def beta_compact_figure(df: pd.DataFrame) -> None:
    """Compact version designed for a 0.64-textwidth minipage."""
    rows = df[df["实验"].str.startswith("β 扫描")].copy()
    rows["beta"] = rows["实验"].str.extract(r"β=([0-9.]+)")[0].astype(float)
    selected = df[df["实验"].eq("主模型 Q4-2（选中配置）")].iloc[0]
    rows = pd.concat(
        [
            rows[["beta", "总费用(元)", "紧急购电率(%)"]],
            pd.DataFrame(
                {
                    "beta": [0.20],
                    "总费用(元)": [selected["总费用(元)"]],
                    "紧急购电率(%)": [selected["紧急购电率(%)"]],
                }
            ),
        ],
        ignore_index=True,
    ).sort_values("beta")

    x = rows["beta"].to_numpy()
    cost = rows["总费用(元)"].to_numpy() / 1e4
    emergency = rows["紧急购电率(%)"].to_numpy()
    cost_color = "#D05A3A"
    risk_color = "#167D8D"
    chosen = x.tolist().index(0.20)

    fig, ax = plt.subplots(figsize=(6.4, 4.25))
    ax2 = ax.twinx()
    ax2.spines["right"].set_visible(True)
    line1 = ax.plot(x, cost, color=cost_color, marker="o", linewidth=2.5,
                    markersize=6, label="总费用")[0]
    line2 = ax2.plot(x, emergency, color=risk_color, marker="s", linewidth=2.5,
                     markersize=5.8, label="紧急购电率")[0]
    ax.axvline(0.20, color="#667085", linestyle="--", linewidth=1.1, alpha=0.8)
    ax.scatter([0.20], [cost[chosen]], s=125, marker="*", color="#F4B942",
               edgecolor="#7A5A00", zorder=6)
    ax2.scatter([0.20], [emergency[chosen]], s=105, marker="*", color="#F4B942",
                edgecolor="#7A5A00", zorder=6)

    ax.set_xlabel(r"风险权重 $\beta$", fontsize=12)
    ax.set_ylabel("总费用（万元）", color=cost_color, fontsize=11.5)
    ax2.set_ylabel("紧急购电率（%）", color=risk_color, fontsize=11.5)
    ax.tick_params(axis="y", colors=cost_color)
    ax2.tick_params(axis="y", colors=risk_color)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{v:.2f}" for v in x])
    ax.grid(axis="y", color="#D0D5DD", linewidth=0.8, alpha=0.55)
    ax.legend([line1, line2], ["总费用", "紧急购电率"],
              loc="lower center", bbox_to_anchor=(0.5, 1.005),
              frameon=False, ncol=2, fontsize=10)

    for idx in (0, chosen, len(x) - 1):
        cost_offset = (8, 7) if idx == 0 else (0, 7)
        cost_align = "left" if idx == 0 else "center"
        ax.annotate(f"{cost[idx]:.1f}", (x[idx], cost[idx]), xytext=cost_offset,
                    textcoords="offset points", ha=cost_align, color=cost_color,
                    fontsize=9.5, fontweight="bold")
        ax2.annotate(f"{emergency[idx]:.3f}%", (x[idx], emergency[idx]),
                     xytext=(0, -11), textcoords="offset points", ha="center",
                     va="top", color=risk_color, fontsize=9.5, fontweight="bold")
    ax.text(0.20, 0.91, r"采用 $\beta=0.20$", transform=ax.get_xaxis_transform(),
            ha="center", va="top", color="#735600", fontsize=10,
            bbox={"boxstyle": "round,pad=0.22", "fc": "#FFF4C2", "ec": "none"})
    fig.tight_layout(pad=0.8)
    finish(fig, "fig_q4_beta_sensitivity_compact")


def scenario_figure(df: pd.DataFrame) -> None:
    rows = df[df["实验"].str.startswith("场景数扫描")].copy()
    rows["M"] = rows["实验"].str.extract(r"M=([0-9]+)")[0].astype(int)
    rows = rows.sort_values("M")

    x = rows["M"].to_numpy()
    cost = rows["总费用(元)"].to_numpy() / 1e4
    emergency = rows["紧急购电率(%)"].to_numpy()
    cost_color = "#D05A3A"
    risk_color = "#167D8D"

    fig, ax = plt.subplots(figsize=(9.2, 5.7))
    ax2 = ax.twinx()
    ax2.spines["right"].set_visible(True)

    bars = ax.bar(x - 1.15, cost, width=2.3, color=cost_color, alpha=0.88,
                  label="全年总费用", zorder=3)
    ax2.plot(x, emergency, color=risk_color, marker="o", linewidth=2.8,
             markersize=7, label="紧急购电率", zorder=4)
    ax.axvspan(18.5, 31.5, color="#E8F3EF", alpha=0.75, zorder=0)
    ax.scatter([30], [cost[-1]], s=150, marker="*", color="#F4B942",
               edgecolor="#7A5A00", zorder=6)
    ax2.scatter([30], [emergency[-1]], s=115, marker="*", color="#F4B942",
                edgecolor="#7A5A00", zorder=6)

    fig.suptitle("场景数达到20后费用趋稳，增加场景仍可降低缺口风险",
                 y=0.985, fontsize=15, fontweight="bold")
    ax.set_title("自建预测对照口径 · 2025年2—12月",
                 pad=12, color="#667085", fontsize=10)
    ax.set_xlabel("场景数 $M$")
    ax.set_ylabel("全年总费用（万元）", color=cost_color)
    ax2.set_ylabel("紧急购电率（%）", color=risk_color)
    ax.tick_params(axis="y", colors=cost_color)
    ax2.tick_params(axis="y", colors=risk_color)
    ax.set_xticks(x)
    ax.set_ylim(min(cost) - 12, max(cost) + 12)
    ax.grid(axis="y", color="#D0D5DD", linewidth=0.8, alpha=0.55, zorder=0)

    for bar, value in zip(bars, cost):
        ax.annotate(f"{value:.1f}",
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 6), textcoords="offset points", ha="center",
                    color=cost_color, fontsize=10, fontweight="semibold")
    annotate(ax2, x, emergency, risk_color, "{:.3f}%", [(0, 8), (0, -12), (0, 8)])
    handles = [bars, ax2.get_lines()[0]]
    ax.legend(handles, ["全年总费用", "紧急购电率"], loc="upper right", frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    finish(fig, "fig_q4_scenario_count_sensitivity")


def main() -> None:
    configure_style()
    df = pd.read_csv(DATA)
    beta_figure(df)
    beta_compact_figure(df)
    scenario_figure(df)


if __name__ == "__main__":
    main()
