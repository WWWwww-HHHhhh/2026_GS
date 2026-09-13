from pathlib import Path
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

Q1_DIR = Path(__file__).resolve().parents[1]
FIG = Q1_DIR / "Pictures"
FIG.mkdir(exist_ok=True)
d = pd.read_csv(Q1_DIR / "Tables" / "q1_timeseries.csv")

# ---------------------------------------------------------------- 统一视觉规范
plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei"],
    "axes.unicode_minus": False,
    "font.size": 9.5, "axes.linewidth": 0.6,
    "figure.dpi": 200, "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
    "savefig.facecolor": "white",
    "pdf.fonttype": 42, "ps.fonttype": 42,
})

# 暖调低饱和配色（与图2 堆叠配色同源，四图共用）
C_PRICE = "#C15F3C"   # 赤陶橙：电价
C_LOAD = "#283C4A"    # 深靛：小区负载
C_PV = "#E7C478"      # 麦黄：光伏
C_NET = "#76B3A6"     # 青绿：净负荷
C_SOC = "#5B7B8C"     # 石板蓝：SOC
C_MARG = "#3F6E8C"    # 深蓝：储能边际价值
C_BOUND = "#C15F3C"   # 上下限虚线
C_UP = "#A87A16"      # SOC 触上限描边（深金）
C_DOWN = "#8E3F24"    # SOC 触下限描边（深赤陶）
C_GRID = "#E7ECF0"
C_SPINE = "#B5C0C8"
C_TICK = "#A6B1BA"
C_TEXT = "#283C4A"

hours = (np.arange(144) + 0.5) / 6.0  # 时段中点（h）
DT = 1 / 6

S_MIN_KWH, S_MAX_KWH, S0_KWH = 1200.0, 10800.0, 6000.0


def tidy(ax, grid_axis="y", time_axis=True):
    """统一坐标区样式：浅网格 + 浅轴脊 + 无上/右框。

    time_axis=True 时把横轴固定成 0~24 h 的时刻轴（图1~3 用）；
    图4 的横轴是电价，需传 time_axis=False。
    """
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=C_GRID, linewidth=0.7)
    ax.tick_params(axis="both", length=3, color=C_TICK, labelsize=9,
                   labelcolor=C_TEXT)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(C_SPINE)
    if time_axis:
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 4))


def mask_runs(mask, dt=DT):
    """把布尔掩码压成连续 True 区间 [(起, 止), ...]，单位 h。"""
    out, start = [], None
    for i, flag in enumerate(mask):
        if flag and start is None:
            start = i
        if not flag and start is not None:
            out.append((start * dt, i * dt))
            start = None
    if start is not None:
        out.append((start * dt, len(mask) * dt))
    return out


def gradient_fill(ax, x, y, base, color, n=70, a_lo=0.05, a_hi=0.55, zorder=1):
    """曲线与基线之间做自上而下的渐变填充。

    用 n 层水平色带叠加实现，全程矢量输出（比 imshow 光栅渐变更适合投稿 PDF）。
    """
    levels = np.linspace(base, float(np.max(y)), n + 1)
    for i in range(n):
        lo, hi = levels[i], levels[i + 1]
        upper = np.clip(y, lo, hi)
        ax.fill_between(x, upper, lo, where=y > lo, color=color, lw=0,
                        alpha=a_lo + (a_hi - a_lo) * i / (n - 1),
                        interpolate=True, zorder=zorder)


def save(fig, stem, png=True):
    """同时输出 PDF（投稿用）与 PNG（预览用）。"""
    fig.savefig(FIG / f"{stem}.pdf")
    if png:
        fig.savefig(FIG / f"{stem}.png", dpi=300)
    plt.close(fig)


parser = argparse.ArgumentParser(description="生成问题一结果图")
parser.add_argument("--figure", type=int, choices=[1, 2, 3, 4, 5], help="仅生成指定图片")
args = parser.parse_args()

if args.figure in (None, 1):
    # 图1：电价—小区负载—光伏—净负荷 同轴折线（单幅面板）。
    # 左轴功率、右轴电价，两侧轴标题各自上色，读者一眼知道哪条线读哪根轴；
    # 高电价时段铺淡暖底纹，把"晚峰电价与净负荷同步冲高、午间光伏压低净负荷"
    # 这两条关系直接显出来。
    load = (d.L_kwh / DT / 1000).to_numpy()
    pv = (d.G_kwh / DT / 1000).to_numpy()
    net = ((d.L_kwh - d.G_kwh) / DT / 1000).to_numpy()
    price = d.price.to_numpy()

    fig, ax1 = plt.subplots(figsize=(6.9, 3.6))
    ax2 = ax1.twinx()

    # 高电价时段底纹：价格高峰与净负荷高峰的时间对齐关系
    hi_price = mask_runs(price > 0.9)
    for lo, hi in hi_price:
        ax1.axvspan(lo, hi, color=C_PRICE, alpha=0.07, lw=0, zorder=0)

    # 光伏：渐变面积（底层）+ 细线勾边
    gradient_fill(ax1, hours, pv, 0.0, C_PV, zorder=1)
    ax1.plot(hours, pv, color=C_PV, lw=1.1, zorder=2)
    # 净负荷：午间光伏盈余时段（净负荷 < 0）单独铺青绿，突出反送
    ax1.fill_between(hours, net, 0, where=net < 0, color=C_NET, alpha=0.32,
                     lw=0, interpolate=True, zorder=2)
    ax1.plot(hours, net, color=C_NET, lw=1.8, zorder=4)
    # 负载：最重的一笔，白色描边保证压在光伏渐变上仍然清晰
    ax1.plot(hours, load, color=C_LOAD, lw=2.0, zorder=5,
             path_effects=[pe.Stroke(linewidth=3.4, foreground="white"), pe.Normal()])
    ax1.axhline(0, color=C_SPINE, lw=0.7, zorder=3)
    # 电价：右轴折线
    ax2.plot(hours, price, color=C_PRICE, lw=1.7, zorder=3)

    i_pk, i_tr = int(np.argmax(price)), int(np.argmin(price))
    for idx, txt, off, ha in ((i_pk, f"峰价 {price[i_pk]:.3f}", (0, 9), "center"),
                              (i_tr, f"谷价 {price[i_tr]:.3f}", (-7, 8), "right")):
        ax2.plot([hours[idx]], [price[idx]], marker="o", ms=4.2, mfc="white",
                 mec=C_PRICE, mew=1.2, zorder=6)
        ax2.annotate(txt, xy=(hours[idx], price[idx]), xytext=off,
                     textcoords="offset points", ha=ha, fontsize=8, color=C_PRICE)

    ax1.set_xlabel("时刻 / h", color=C_TEXT)
    ax1.set_ylabel("功率 / MW", color=C_LOAD)
    ax2.set_ylabel("电价 / (元/kWh)", color=C_PRICE)
    ax1.set_ylim(-2.9, 8.4)
    ax1.set_yticks(range(-2, 9, 2))
    ax2.set_ylim(0, 1.72)
    ax2.set_yticks(np.arange(0.0, 1.61, 0.4))
    tidy(ax1)
    ax2.tick_params(axis="y", length=3, color=C_TICK, labelsize=9,
                    labelcolor=C_PRICE)
    for side in ["top", "left"]:
        ax2.spines[side].set_visible(False)
    ax2.spines["right"].set_color(C_SPINE)
    ax2.spines["right"].set_linewidth(0.6)

    handles = [
        Line2D([], [], color=C_LOAD, lw=2.0, label="小区负载"),
        Patch(facecolor=C_PV, alpha=0.75, edgecolor=C_PV, label="光伏预测"),
        Line2D([], [], color=C_NET, lw=2.0, label="净负荷"),
        Line2D([], [], color=C_PRICE, lw=1.8, label="电价"),
    ]
    fig.legend(handles=handles, ncol=4, frameon=False, fontsize=8.5,
               loc="upper center", bbox_to_anchor=(0.5, 1.0), handlelength=1.7,
               columnspacing=1.9, borderaxespad=0)
    # 底纹就地标注，省掉一条图例，也省掉读者回头对图例的动作
    if hi_price:
        mid = max(hi_price, key=lambda se: se[1] - se[0])
        ax1.annotate("高电价时段", xy=((mid[0] + mid[1]) / 2, 7.75), ha="center",
                     va="center", fontsize=8, color=C_PRICE)
    fig.subplots_adjust(left=0.095, right=0.905, bottom=0.135, top=0.855)
    save(fig, "q1_fig1_timeseries")

if args.figure in (None, 2):
    # 图2：单幅供电来源堆叠面积图，顶部与负荷之差为充电量
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    grid = d.x_plan_kwh.to_numpy()
    pv = (d.G_kwh - d.w_curtail_kwh).to_numpy()
    discharge = d.r_discharge_kwh.to_numpy()
    load = d.L_kwh.to_numpy()
    charge = d.c_charge_kwh.to_numpy()
    assert np.allclose(grid + pv + discharge, load + charge, atol=1e-8, rtol=0)
    edges = np.arange(len(d) + 1) * DT
    # 重复最后一个值，以阶梯方式准确覆盖各十分钟区间，不平滑优化结果。
    extend = lambda values: np.r_[values, values[-1]]
    ax.stackplot(
        edges, extend(grid), extend(pv), extend(discharge),
        step="post", colors=["#8BAFC9", "#E7C478", "#76B3A6"],
        labels=["外网购电", "光伏利用", "储能放电"],
        linewidth=0, alpha=0.95, zorder=2,
    )
    ax.step(
        edges, extend(load), where="post", color="#283C4A", lw=1.5,
        label="小区负荷", zorder=4,
        path_effects=[pe.Stroke(linewidth=2.8, foreground="white"), pe.Normal()],
    )
    ax.set_xlabel("时刻 / h")
    ax.set_ylabel("时段电量 / kWh")
    ax.set_xlim(0, 24)
    ax.set_ylim(0, (grid + pv + discharge).max() * 1.06)
    ax.set_xticks(range(0, 25, 4))
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#E7ECF0", linewidth=0.6)
    ax.tick_params(axis="both", length=3, color="#A6B1BA")
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color("#B5C0C8")
    ax.legend(ncol=4, frameon=False, fontsize=9, loc="lower center",
              bbox_to_anchor=(0.5, 1.01), borderaxespad=0, handlelength=1.6)
    fig.subplots_adjust(left=0.10, right=0.99, bottom=0.19, top=0.85)
    save(fig, "q1_fig2_dispatch")

if args.figure in (None, 3):
    # 图3：SOC 轨迹、可行域与上下限。曲线在上下限处的水平段即触界区间，无需另加底纹。
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    x = np.arange(145) / 6.0
    soc = np.concatenate([[S0_KWH], d.soc_kwh.to_numpy()]) / 1000.0
    s_lo, s_hi, s0 = S_MIN_KWH / 1000, S_MAX_KWH / 1000, S0_KWH / 1000

    ax.axhspan(s_lo, s_hi, color=C_SOC, alpha=0.08, lw=0, zorder=0.8)
    ax.fill_between(x, s_lo, soc, where=soc >= s_lo, color=C_SOC, alpha=0.22,
                    lw=0, interpolate=True, zorder=1)
    ax.plot(x, soc, color=C_SOC, lw=1.8, zorder=3)
    ax.axhline(s_hi, color=C_BOUND, lw=0.9, ls="--", zorder=2)
    ax.axhline(s_lo, color=C_BOUND, lw=0.9, ls="-.", zorder=2)

    # 起止储电量标记（问题1 硬周期边界 s(0:00)=s(24:00)=6000 kWh）
    ax.plot([0, 24], [s0, s0], marker="o", ms=4.6, mfc="white", mec=C_SOC,
            mew=1.3, ls="none", zorder=4)
    ax.annotate("起止 6.0 MWh", xy=(0, s0), xytext=(7, -17),
                textcoords="offset points", fontsize=8, color=C_SOC)

    i_min = int(np.argmin(d.soc_kwh.to_numpy()))
    # 下限水平段紧贴下界，注记放在 0~1.2 MWh 的空白带里，避免压住 SOC 曲线
    ax.annotate(f"最低 {s_lo:.1f} MWh", xy=(hours[i_min], 0.58), ha="center",
                va="center", fontsize=8, color=C_BOUND)
    ax.set_ylabel("储电量 / MWh", color=C_TEXT)
    ax.set_xlabel("时刻 / h", color=C_TEXT)
    ax.set_ylim(0, 12.6)
    ax.set_yticks(range(0, 13, 2))
    tidy(ax)

    handles = [
        Line2D([], [], color=C_SOC, lw=1.9, label="SOC"),
        Line2D([], [], color=C_BOUND, lw=1.0, ls="--", label="上限 10.8 MWh"),
        Line2D([], [], color=C_BOUND, lw=1.0, ls="-.", label="下限 1.2 MWh"),
    ]
    ax.legend(handles=handles, ncol=3, frameon=False, fontsize=8.5,
              loc="lower center", bbox_to_anchor=(0.5, 1.01), borderaxespad=0,
              handlelength=1.9, columnspacing=2.2)
    fig.subplots_adjust(left=0.085, right=0.985, bottom=0.155, top=0.875)
    save(fig, "q1_fig3_soc")

if args.figure in (None, 4):
    # 图4：储能边际价值对电价的散点关系图（非折线）。
    # 若边际价值只是电价的等比例折算，散点应贴住 y=0.9x 参考线；偏离参考线的点
    # 即 SOC 触界、影子价格被上下限截断的时段。点色编码时刻，保留日内先后顺序。
    from matplotlib.colors import LinearSegmentedColormap, Normalize

    price = d.price.to_numpy()
    value = (-d.mu_soc).to_numpy()
    soc = d.soc_kwh.to_numpy()
    up = np.abs(soc - S_MAX_KWH) < 1e-6
    lo = np.abs(soc - S_MIN_KWH) < 1e-6

    day = LinearSegmentedColormap.from_list(
        "day", ["#2E4A5B", "#6E93A8", "#D9C48A", "#C9825A", "#2E4A5B"])
    tnorm = Normalize(0.0, 24.0)

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    # 只画到数据范围：电价 0.371~1.395、边际价值 0.471~1.130，
    # 按 0~1.5 铺满会让 144 个点挤在左下角一小块里看不清。
    xlim, ylim = (0.33, 1.45), (0.41, 1.24)
    ref = np.array([0.0, 1.5])   # 参考线仍按过原点的整条直线画，视野内自然截断
    ax.plot(ref, ref, ls="--", lw=1.0, color=C_SPINE, zorder=1,
            label="参考 v = 电价")
    ax.plot(ref, 0.9 * ref, ls="--", lw=1.1, color=C_NET, zorder=1,
            label="参考 v = 0.9 × 电价")

    # 每个点都保留时刻填充；SOC 触界点叠在上一层，用「形状 + 描边色」双重区分。
    # （不要用 facecolor="none" 的空心标记——密集处会变成一堆空框，
    #   既看不出时刻、也数不清有几个点。）
    sc = ax.scatter(price, value, c=hours, cmap=day, norm=tnorm, s=27,
                    alpha=0.88, edgecolors="white", linewidths=0.35, zorder=3)
    ax.scatter(price[up], value[up], c=hours[up], cmap=day, norm=tnorm, s=36,
               marker="s", edgecolors=C_UP, linewidths=1.3, alpha=0.95, zorder=4)
    ax.scatter(price[lo], value[lo], c=hours[lo], cmap=day, norm=tnorm, s=36,
               marker="o", edgecolors=C_DOWN, linewidths=1.3, alpha=0.95, zorder=4)

    ax.set_xlabel("电价 / (元/kWh)", color=C_TEXT)
    ax.set_ylabel("储能边际价值 / (元/kWh)", color=C_TEXT)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xticks(np.arange(0.4, 1.41, 0.2))
    ax.set_yticks(np.arange(0.4, 1.21, 0.2))
    tidy(ax, grid_axis="both", time_axis=False)

    cbar = fig.colorbar(sc, ax=ax, pad=0.02, fraction=0.045)
    cbar.set_ticks([0, 6, 12, 18, 24])
    cbar.set_label("时刻 / h", color=C_TEXT, fontsize=8.5)
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(length=2, width=0.5, color=C_TICK, labelsize=8,
                        labelcolor=C_TEXT)

    handles = [
        Line2D([], [], ls="--", lw=1.0, color=C_SPINE, label="参考 v = 电价"),
        Line2D([], [], ls="--", lw=1.1, color=C_NET, label="参考 v = 0.9 × 电价"),
        Line2D([], [], marker="s", ls="none", ms=6.5, mfc="#C9C2AC",
               mec=C_UP, mew=1.4, label="SOC 触上限"),
        Line2D([], [], marker="o", ls="none", ms=6.5, mfc="#C9C2AC",
               mec=C_DOWN, mew=1.4, label="SOC 触下限"),
    ]
    ax.legend(handles=handles, ncol=4, frameon=False, fontsize=8,
              loc="lower center", bbox_to_anchor=(0.5, 1.005), borderaxespad=0,
              handlelength=1.6, columnspacing=1.4)
    fig.subplots_adjust(left=0.10, right=0.99, bottom=0.125, top=0.865)
    save(fig, "q1_fig4_marginal_value")

if args.figure in (None, 5):
    # 图5（论文正文用合并图）：上panel 输入特性、下panel 调度结果，共享时刻轴。
    # 合并目的：论文 6.2 只需一张图即可同时交代输入特性与调度结果，
    # 省掉一套图注与一套横轴刻度；正文以 (a)、(b) 分别引用两个面板。
    load = (d.L_kwh / DT / 1000).to_numpy()
    pv = (d.G_kwh / DT / 1000).to_numpy()
    net = ((d.L_kwh - d.G_kwh) / DT / 1000).to_numpy()
    price = d.price.to_numpy()

    grid = d.x_plan_kwh.to_numpy()
    pv_use = (d.G_kwh - d.w_curtail_kwh).to_numpy()
    discharge = d.r_discharge_kwh.to_numpy()
    load_kwh = d.L_kwh.to_numpy()
    charge = d.c_charge_kwh.to_numpy()
    edges = np.arange(len(d) + 1) * DT
    extend = lambda values: np.r_[values, values[-1]]

    fig, (axa, axb) = plt.subplots(
        2, 1, figsize=(7.0, 4.5), sharex=True,
        gridspec_kw={"height_ratios": [1.12, 1.0], "hspace": 0.26})

    # ------------------------------------------------ (a) 输入特性
    axa2 = axa.twinx()
    hi_price = mask_runs(price > 0.9)
    for lo, hi in hi_price:
        axa.axvspan(lo, hi, color=C_PRICE, alpha=0.07, lw=0, zorder=0)

    gradient_fill(axa, hours, pv, 0.0, C_PV, zorder=1)
    axa.plot(hours, pv, color=C_PV, lw=1.1, zorder=2)
    axa.fill_between(hours, net, 0, where=net < 0, color=C_NET, alpha=0.32,
                     lw=0, interpolate=True, zorder=2)
    axa.plot(hours, net, color=C_NET, lw=1.8, zorder=4)
    axa.plot(hours, load, color=C_LOAD, lw=2.0, zorder=5,
             path_effects=[pe.Stroke(linewidth=3.4, foreground="white"), pe.Normal()])
    axa.axhline(0, color=C_SPINE, lw=0.7, zorder=3)
    axa2.plot(hours, price, color=C_PRICE, lw=1.7, zorder=3)

    i_pk, i_tr = int(np.argmax(price)), int(np.argmin(price))
    for idx, txt, off, ha in ((i_pk, f"峰价 {price[i_pk]:.3f}", (0, 9), "center"),
                              (i_tr, f"谷价 {price[i_tr]:.3f}", (-7, 8), "right")):
        axa2.plot([hours[idx]], [price[idx]], marker="o", ms=4.2, mfc="white",
                  mec=C_PRICE, mew=1.2, zorder=6)
        axa2.annotate(txt, xy=(hours[idx], price[idx]), xytext=off,
                      textcoords="offset points", ha=ha, fontsize=8, color=C_PRICE)

    axa.set_ylabel("功率 / MW", color=C_LOAD)
    axa2.set_ylabel("电价 / (元/kWh)", color=C_PRICE)
    axa.set_ylim(-2.9, 8.4)
    axa.set_yticks(range(-2, 9, 2))
    axa2.set_ylim(0, 1.72)
    axa2.set_yticks(np.arange(0.0, 1.61, 0.4))
    tidy(axa)
    axa2.tick_params(axis="y", length=3, color=C_TICK, labelsize=9,
                     labelcolor=C_PRICE)
    for side in ["top", "left"]:
        axa2.spines[side].set_visible(False)
    axa2.spines["right"].set_color(C_SPINE)
    axa2.spines["right"].set_linewidth(0.6)

    handles_a = [
        Line2D([], [], color=C_LOAD, lw=2.0, label="小区负载"),
        Patch(facecolor=C_PV, alpha=0.75, edgecolor=C_PV, label="光伏预测"),
        Line2D([], [], color=C_NET, lw=2.0, label="净负荷"),
        Line2D([], [], color=C_PRICE, lw=1.8, label="电价"),
    ]
    axa.legend(handles=handles_a, ncol=4, frameon=False, fontsize=8.5,
               loc="lower center", bbox_to_anchor=(0.5, 1.005), borderaxespad=0,
               handlelength=1.7, columnspacing=1.9)
    if hi_price:
        mid = max(hi_price, key=lambda se: se[1] - se[0])
        axa.annotate("高电价时段", xy=((mid[0] + mid[1]) / 2, 7.75), ha="center",
                     va="center", fontsize=8, color=C_PRICE)

    # ------------------------------------------------ (b) 调度结果
    axb.stackplot(
        edges, extend(grid), extend(pv_use), extend(discharge),
        step="post", colors=["#8BAFC9", "#E7C478", "#76B3A6"],
        labels=["外网购电", "光伏利用", "储能放电"],
        linewidth=0, alpha=0.95, zorder=2,
    )
    axb.step(
        edges, extend(load_kwh), where="post", color="#283C4A", lw=1.5,
        label="小区负荷", zorder=4,
        path_effects=[pe.Stroke(linewidth=2.8, foreground="white"), pe.Normal()],
    )
    axb.set_ylabel("时段电量 / kWh")
    axb.set_ylim(0, (grid + pv_use + discharge).max() * 1.06)
    tidy(axb)
    axb.legend(ncol=4, frameon=False, fontsize=9, loc="lower center",
               bbox_to_anchor=(0.5, 1.005), borderaxespad=0, handlelength=1.6)
    axb.set_xlabel("时刻 / h", color=C_TEXT)

    for ax, tag in ((axa, "(a)"), (axb, "(b)")):
        ax.annotate(tag, xy=(0.006, 0.965), xycoords="axes fraction",
                    ha="left", va="top", fontsize=9.5, color=C_TEXT)

    fig.subplots_adjust(left=0.095, right=0.905, bottom=0.095, top=0.955)
    save(fig, "q1_fig_input_dispatch")

print("已生成图片：", args.figure if args.figure else "全部", "，目录：", FIG)
