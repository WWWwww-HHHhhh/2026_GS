"""Compare the two solved efficiency cases with a compact dumbbell chart."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, ticker

Q1_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Q1_DIR / "Results" / "Pictures"
SOURCE = Q1_DIR / "Results" / "Tables" / "q1_efficiency_sensitivity.json"


def main():
    cases = json.loads(SOURCE.read_text(encoding="utf-8-sig"))["cases"]
    cases = sorted(cases, key=lambda item: item["purchase_cost_yuan"])
    fonts = {font.name for font in font_manager.fontManager.ttflist}
    for name in ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]:
        if name in fonts:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams.update({"axes.unicode_minus": False, "font.size": 11,
                         "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, ax = plt.subplots(figsize=(7.2, 2.35), facecolor="white")
    costs = [case["purchase_cost_yuan"] for case in cases]
    colors = ["#288B87", "#637F9C"]
    ax.plot(costs, [0, 0], color="#C6D4DE", linewidth=3,
            solid_capstyle="round", zorder=2)
    for case, color in zip(cases, colors):
        cost = case["purchase_cost_yuan"]
        ax.scatter(cost, 0, s=135, color=color, edgecolors="white",
                   linewidths=2, zorder=3)
        ax.annotate(f'往返效率 {case["round_trip_efficiency"]:.0%}',
                    (cost, 0), xytext=(0, 22), textcoords="offset points",
                    ha="center", color=color, fontsize=11)
        ax.annotate(f"{cost:,.2f}", (cost, 0), xytext=(0, -24),
                    textcoords="offset points", ha="center", color="#263746",
                    fontsize=12, fontweight="medium")
    ax.set_xlim(33350, 35550)
    ax.set_ylim(-0.65, 0.65)
    ax.set_yticks([])
    ax.set_xticks([33500, 34000, 34500, 35000, 35500])
    ax.xaxis.set_major_formatter(ticker.StrMethodFormatter("{x:,.0f}"))
    ax.tick_params(axis="x", length=3, colors="#788590", labelsize=9, pad=6)
    ax.set_xlabel("购电费用 / 元", color="#536471", fontsize=10, labelpad=10)
    for side in ["left", "right", "top"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#D8E0E6")
    fig.subplots_adjust(left=0.05, right=0.98, bottom=0.29, top=0.96)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for extension in ["pdf", "png"]:
        path = OUTPUT_DIR / f"q1_efficiency_comparison.{extension}"
        fig.savefig(path, dpi=300, facecolor="white", bbox_inches="tight")
        print(path)
    plt.close(fig)


if __name__ == "__main__":
    main()
