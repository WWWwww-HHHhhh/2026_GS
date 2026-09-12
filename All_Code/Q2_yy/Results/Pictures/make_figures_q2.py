# -*- coding: utf-8 -*-
"""由 Q2_yy 已校验缓存生成论文图，不再次调参、不重新求解。

输入：Data_processing/*.pkl、Results/Tables/forecast_monthly_metrics.csv
运行：python make_figures_q2.py
输出：Results/Pictures/ 下 6 张图，每张同时输出 PDF（投稿用）与 PNG（预览用）

六张图的图型说明（与旧版相比的改动）：
    fig_q2_load_pv_fan      四联折线 + 场景带     —— 保留图型，只做美化
    fig_q2_error_monthly    月度 WAPE 折线        —— 换成哑铃图（负荷/光伏同排对比）
    fig_q2_plan_settlement  三条折线重叠          —— 换成子弹图式渐变对照柱（轨道+实柱+目标刻线）
    fig_q2_soc_heatmap      144×334 热力图        —— 换成日内中位曲线 + P10–P90 带 + 充放状态条
    fig_q2_emergency_curtailment 分组柱状图       —— 换成并排水平渐变条 + 月均参考线
    fig_q2_cvar_frontier    参数候选散点          —— 保留图型，只做美化

视觉规范：无上/右轴脊、浅色网格、图例去边框置于坐标区上方、低饱和暖调配色；
大面积色块一律用 tint() 叠多层做成渐变，避免纯色块的扁平观感；
文字以 TrueType 嵌入 PDF（pdf.fonttype=42），可直接投稿。
"""
from pathlib import Path
import pickle

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.patheffects import Normal, Stroke

PICS = Path(__file__).resolve().parent
Q2_ROOT = PICS.parents[1]
DATA = Q2_ROOT / "Data_processing"
TABLES = Q2_ROOT / "Results" / "Tables"
T = 144
SOC_MIN, SOC_MAX = 1200.0, 10800.0      # kWh，题给的储能上下限

# ---------------------------------------------------------------- 统一视觉规范
INK = "#283C4A"       # 主文字 / 深色参照
MUTED = "#6B7B87"     # 次要文字
GRID = "#E7ECF0"
SPINE = "#B5C0C8"
TICK = "#A6B1BA"
BLUE = "#4E7C9B"      # 日前预测 / 计划
SKY = "#A9C6D6"       # 场景区间 / 未提取
AMBER = "#E7C478"     # 光伏
GOLD = "#D9A03C"      # 弃光条（比 AMBER 深一档，避免大面积渐变被冲淡）
ORANGE = "#D98A45"    # 实际
RED = "#C15F3C"       # 紧急购电 / 风险
TEAL = "#76B3A6"      # SOC
COOL = "#BFD6E2"      # 充电状态条
WARM = "#F0C9A8"      # 放电状态条
IDLE = "#EDF1F4"      # 平段状态条

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei"],
    "axes.unicode_minus": False,
    "font.size": 9.5, "axes.linewidth": 0.6,
    "figure.dpi": 200, "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
    "savefig.facecolor": "white",
    "pdf.fonttype": 42, "ps.fonttype": 42,
})


def load(name):
    try:
        with open(DATA / name, "rb") as fh:
            return pickle.load(fh)
    except TypeError as exc:
        if "BlockPlacement" not in str(exc):
            raise
        import pandas.core.internals.blocks as blocks
        from pandas._libs.internals import BlockPlacement
        original_new_block = blocks.new_block

        def compatible_new_block(values, placement, *, ndim, refs=None):
            if isinstance(placement, slice):
                placement = BlockPlacement(placement)
            return original_new_block(values, placement=placement, ndim=ndim, refs=refs)

        blocks.new_block = compatible_new_block
        try:
            with open(DATA / name, "rb") as fh:
                return pickle.load(fh)
        finally:
            blocks.new_block = original_new_block


def save(fig, name):
    """同时输出 PDF（投稿）与 PNG（预览）。"""
    stem = name[:-4] if name.endswith(".png") else name
    fig.savefig(PICS / f"{stem}.pdf")
    fig.savefig(PICS / f"{stem}.png", dpi=300)
    plt.close(fig)


def tidy(ax, grid_axis="y", time_axis=False):
    """统一坐标区样式：浅网格 + 浅轴脊 + 去上/右框。"""
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.7)
    ax.tick_params(axis="both", length=3, color=TICK, labelsize=9, labelcolor=INK)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(SPINE)
    if time_axis:
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 4))


def hourly_sum(a):
    """最后一维由 144 个 10 分钟量合并为 24 个逐小时电量。"""
    a = np.asarray(a, dtype=float)
    return a.reshape(*a.shape[:-1], 24, 6).sum(axis=-1)


def runs_of(mask):
    """布尔掩码 -> 连续 True 的 (起, 止) 区间列表，用于铺时段底纹。"""
    out, start = [], None
    for i, flag in enumerate(mask):
        if flag and start is None:
            start = i
        if not flag and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(mask)))
    return out


def tint(color, factor):
    """把颜色朝白色方向稀释：factor=1 原色，factor=0 纯白。"""
    r, g, b = to_rgb(color)
    return (1 - (1 - r) * factor, 1 - (1 - g) * factor, 1 - (1 - b) * factor)


def gradient_barh(ax, ys, values, height, color, bands=46, tint_lo=0.34,
                  zorder=3):
    """水平渐变条：沿长度方向由浅到深，末端补一圈同色描边收边。"""
    values = np.asarray(values, dtype=float)
    ys = np.asarray(ys, dtype=float)
    for k in range(bands):
        f0, f1 = k / bands, (k + 1) / bands
        factor = tint_lo + (1.0 - tint_lo) * ((k + 0.5) / bands)
        ax.barh(ys, values * (f1 - f0), height=height, left=values * f0,
                color=tint(color, factor), edgecolor="none", linewidth=0,
                zorder=zorder)
    ax.barh(ys, values, height=height, left=0, color="none",
            edgecolor=tint(color, 0.72), linewidth=0.6, zorder=zorder + 1)


def gradient_col(ax, xs, values, width, color, bottom=0.0, bands=40,
                 tint_lo=0.42, outline=True, zorder=3):
    """垂直渐变柱：底部饱和、顶部提亮，模拟受光，消除纯色块的塑料感。"""
    values = np.asarray(values, dtype=float)
    base = np.broadcast_to(np.asarray(bottom, dtype=float), values.shape)
    for k in range(bands):
        f0, f1 = k / bands, (k + 1) / bands
        factor = 1.0 - (1.0 - tint_lo) * ((k + 0.5) / bands)
        ax.bar(xs, values * (f1 - f0), width=width, bottom=base + values * f0,
               color=tint(color, factor), edgecolor="none", linewidth=0,
               zorder=zorder)
    if outline:
        ax.bar(xs, values, width=width, bottom=base, color="none",
               edgecolor=tint(color, 0.70), linewidth=0.55, zorder=zorder + 1)


# ------------------------------------------------------------------ 图1 预测扇形
def figure_forecast_fan(ds, fc, sc):
    """四联折线 + 场景带：保留原图型，只做美化（配色、网格、轴脊、误差标注）。"""
    fig, axes = plt.subplots(2, 2, figsize=(11.6, 7.0))
    x = np.arange(T)
    for row, date in enumerate(("2025-07-15", "2025-11-20")):
        i = ds["date_str"].tolist().index(date)
        for col, (key, pred_key, scen_key, title) in enumerate((
                ("load", "Lhat", "L_all", "负荷"),
                ("pv", "Ghat", "G_all", "光伏"))):
            ax = axes[row, col]
            lo, hi = np.percentile(sc[scen_key][i], [5, 95], axis=0)
            pred, actual = fc[pred_key][:, i], ds[key][:, i]
            ax.fill_between(x, lo, hi, color=SKY, alpha=0.5, lw=0,
                            label="场景 P5–P95", zorder=1)
            ax.plot(x, pred, color=BLUE, lw=1.6, label="日前预测", zorder=3)
            ax.plot(x, actual, color=ORANGE, lw=1.3, label="实际", zorder=4)
            wape = np.abs(actual - pred).sum() / actual.sum() * 100
            ax.annotate(f"当日 WAPE {wape:.1f}%", xy=(0.985, 0.955),
                        xycoords="axes fraction", ha="right", va="top",
                        fontsize=8.5, color=MUTED)
            ax.set_title(f"{date}  {title}", loc="left", fontsize=11, color=INK, pad=8)
            ax.set_xlabel("10分钟时段", color=INK)
            ax.set_ylabel("电量 / kWh", color=INK)
            ax.set_xticks(range(0, 145, 24))
            tidy(ax, time_axis=False)
    handles = [
        Patch(facecolor=SKY, alpha=0.5, edgecolor="none", label="场景 P5–P95"),
        Line2D([], [], color=BLUE, lw=1.8, label="日前预测"),
        Line2D([], [], color=ORANGE, lw=1.5, label="实际"),
    ]
    fig.legend(handles=handles, ncol=3, frameon=False, fontsize=9.5,
               loc="upper center", bbox_to_anchor=(0.5, 1.0), handlelength=1.8,
               columnspacing=2.0, borderaxespad=0)
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.085, top=0.905,
                        hspace=0.34, wspace=0.19)
    save(fig, "fig_q2_load_pv_fan.png")


# ------------------------------------------------------------------ 图2 WAPE 哑铃
def figure_error_dumbbell():
    """哑铃图取代双折线：同一个月负荷/光伏误差并排对比，差值一眼可见。"""
    fm = pd.read_csv(TABLES / "forecast_monthly_metrics.csv")
    months = list(range(2, 13))
    load_v = np.array([100 * float(fm[(fm.series == "load") & (fm.month == m)].WAPE.iloc[0])
                       for m in months])
    pv_v = np.array([100 * float(fm[(fm.series == "pv") & (fm.month == m)].WAPE.iloc[0])
                     for m in months])
    y = np.arange(len(months))

    fig, ax = plt.subplots(figsize=(8.4, 5.9))
    ax.hlines(y, load_v, pv_v, color=GRID, lw=3.0, zorder=1)
    ax.scatter(load_v, y, s=95, color=BLUE, edgecolors="white", linewidths=1.5,
               zorder=3, label="负荷预测")
    ax.scatter(pv_v, y, s=95, color=AMBER, edgecolors="white", linewidths=1.5,
               zorder=3, label="光伏预测")
    for yi, lv, pv in zip(y, load_v, pv_v):
        # 标签一律放在两端的外侧：谁是左点谁向左标，避免 10 月这种
        # 「光伏低于负荷」的月份两个数字叠在一起。
        lv_left = lv <= pv
        for value, color, to_left in ((lv, BLUE, lv_left),
                                      (pv, "#9C7722", not lv_left)):
            ax.annotate(f"{value:.1f}", xy=(value, yi),
                        xytext=(-9 if to_left else 9, 0),
                        textcoords="offset points",
                        ha="right" if to_left else "left", va="center",
                        fontsize=8, color=color)
    ax.set_yticks(y, [f"{m}月" for m in months])
    ax.invert_yaxis()
    ax.set_xlabel("WAPE / %", color=INK)
    ax.set_xlim(1.6, 9.8)
    tidy(ax, grid_axis="x")
    gap = (pv_v - load_v).mean()
    ax.annotate(f"光伏误差全年平均比负荷高 {gap:.1f} 个百分点",
                xy=(0.985, 0.045), xycoords="axes fraction", ha="right",
                va="bottom", fontsize=8.5, color=MUTED)
    ax.legend(ncol=2, frameon=False, fontsize=9.5, loc="lower center",
              bbox_to_anchor=(0.5, 1.01), borderaxespad=0, handlelength=1.4,
              columnspacing=2.2, markerscale=1.0)
    fig.subplots_adjust(left=0.095, right=0.975, bottom=0.105, top=0.885)
    save(fig, "fig_q2_error_monthly.png")


# ------------------------------------------------------------------ 图3 结算偏差
def figure_settlement(worst):
    """子弹图式对照柱：每小时的浅色轨道 + 渐变实柱 + 计划目标刻线。

    取代原来的直角坐标堆叠柱。三层结构（轨道/实柱/目标线）把「计划多少、
    实际用了多少、其中多少是紧急补购」压进同一根柱子里，浅色轨道给出满量程
    参考，柱体做垂直渐变以消除纯色块的扁平感。
    """
    hours = np.arange(24)
    plan = hourly_sum(worst["plan_x"])
    used = hourly_sum(worst["settle_y"])
    emerg = hourly_sum(worst["settle_e"])
    total = used + emerg
    ymax = float(max(total.max(), plan.max())) * 1.14

    fig, ax = plt.subplots(figsize=(11.8, 5.0))
    ax.set_facecolor("#FAFBFC")
    ax.bar(hours, ymax, width=0.86, bottom=0, color="#F3F6F9",
           edgecolor="none", zorder=1)
    gradient_col(ax, hours, used, 0.60, BLUE, zorder=3)
    gradient_col(ax, hours, emerg, 0.60, RED, bottom=used, tint_lo=0.80,
                 zorder=5)

    # 计划目标刻线：比柱略宽并铺白描边，压在柱顶也认得出
    ax.hlines(plan, hours - 0.47, hours + 0.47, color="white", lw=4.4, zorder=7)
    ax.hlines(plan, hours - 0.47, hours + 0.47, color=INK, lw=2.0, zorder=8)

    ax.set_xlabel("小时", color=INK)
    ax.set_ylabel("逐小时电量 / kWh", color=INK)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlim(-0.75, 23.75)
    ax.set_ylim(0, ymax)
    tidy(ax)

    # 只在紧急购电最多的那个小时做一次就地说明，避免满图标注
    peak_h = int(np.argmax(emerg))
    ax.annotate(f"紧急购电最多：{emerg[peak_h]/1000:.1f} MWh",
                xy=(peak_h, total[peak_h]), xytext=(0, 26),
                textcoords="offset points", ha="center", fontsize=8.5,
                color=RED,
                arrowprops=dict(arrowstyle="-", color=RED, lw=0.8,
                                shrinkA=0, shrinkB=2))

    total_plan, total_emerg = plan.sum(), emerg.sum()
    ax.set_title(f"{worst['date']} 逐小时购电结构：计划 {total_plan/1000:.1f} MWh，"
                 f"另需紧急购电 {total_emerg/1000:.1f} MWh（+{total_emerg/total_plan:.0%}）",
                 loc="left", fontsize=11.5, color=INK, pad=34)
    handles = [
        Patch(facecolor=tint(BLUE, 0.75), edgecolor="none", label="实际提取日前电"),
        Patch(facecolor=tint(RED, 0.85), edgecolor="none", label="紧急购电"),
        Line2D([], [], color=INK, lw=2.0, label="原计划购电"),
    ]
    ax.legend(handles=handles, ncol=3, frameon=False, fontsize=9.5,
              loc="lower center", bbox_to_anchor=(0.5, 1.005), borderaxespad=0,
              handlelength=1.6, columnspacing=2.4)
    fig.subplots_adjust(left=0.072, right=0.985, bottom=0.135, top=0.80)
    save(fig, "fig_q2_plan_settlement.png")


# ------------------------------------------------------------------ 图4 SOC 日节律
def _phase_ribbon(med):
    """由中位曲线的小时增量判定每个小时的充/放状态。

    返回长度 24 的数组：+1 充电、-1 放电、0 平台。先按阈值取符号，
    再把被单小时平台隔开的同一段合并（否则「回充—平台—回充」会被切成两截）。
    """
    delta = np.diff(med)
    phase = np.zeros(24)
    phase[:23] = np.where(delta > 0.45, 1, np.where(delta < -0.45, -1, 0))
    for i in range(1, 23):
        if phase[i] == 0 and phase[i - 1] == phase[i + 1] != 0:
            phase[i] = phase[i - 1]
    return phase


def _mean_daily_cycles(soc):
    """平均每天「完整充放」轮数。

    完整一轮定义为：SOC 先跌破量程 25% 分位，再回充到 75% 分位以上。
    用迟滞（双阈值）而不是直接数导数变号，否则平台期上的微小抖动会把
    一轮拆成好几轮（实测直接数变号会虚高到 5.0 轮）。
    """
    lo = SOC_MIN + 0.25 * (SOC_MAX - SOC_MIN)
    hi = SOC_MIN + 0.75 * (SOC_MAX - SOC_MIN)
    counts = []
    for j in range(soc.shape[1]):
        col = soc[:, j]
        high = col[0] > hi
        n = 0
        for value in col:
            if not high and value > hi:
                high, n = True, n + 1
            elif high and value < lo:
                high = False
        counts.append(n)
    return float(np.mean(counts))


def figure_soc_profile(logs):
    """日内中位 SOC + P10–P90 带 + 底部充放状态条，取代 144×334 热力图。

    热力图纵向是 334 天重复纹理，既看不出规律也没法读数；储能真正要说明的是
    「日内节律」——每天在上下限之间来回充放几轮。因此上幅画 SOC 水平与日间
    离散度，下幅用一条窄状态条标出充/放方向，两者共用时间轴。
    """
    soc = np.vstack([np.asarray(x["settle_s_actual"])[:T] for x in logs]).T
    byh = soc.reshape(24, 6, -1).mean(axis=1)          # 24 × 天数
    hours = np.arange(24)
    med = np.median(byh, axis=1) / 1000
    p10 = np.percentile(byh, 10, axis=1) / 1000
    p90 = np.percentile(byh, 90, axis=1) / 1000
    phase = _phase_ribbon(med)

    fig = plt.figure(figsize=(10.6, 5.0))
    gs = fig.add_gridspec(2, 1, height_ratios=[5.0, 0.40], hspace=0.20)
    ax = fig.add_subplot(gs[0])
    rb = fig.add_subplot(gs[1], sharex=ax)

    ax.fill_between(hours, p10, p90, color=TEAL, alpha=0.24, lw=0,
                    label="P10–P90", zorder=1)
    ax.plot(hours, med, color=TEAL, lw=2.2, zorder=3,
            path_effects=[Stroke(linewidth=3.6, foreground="white"), Normal()],
            label="中位 SOC")
    ax.axhline(SOC_MAX / 1000, color=RED, lw=0.9, ls="--", zorder=2)
    ax.axhline(SOC_MIN / 1000, color=RED, lw=0.9, ls="-.", zorder=2)
    ax.annotate(f"上限 {SOC_MAX/1000:.1f} MWh", xy=(23.7, SOC_MAX / 1000),
                xytext=(0, 5), textcoords="offset points", ha="right",
                fontsize=8, color=RED)
    ax.annotate(f"下限 {SOC_MIN/1000:.1f} MWh", xy=(23.7, SOC_MIN / 1000),
                xytext=(0, -13), textcoords="offset points", ha="right",
                fontsize=8, color=RED)
    ax.set_ylabel("储电量 / MWh", color=INK)
    ax.set_ylim(0, 12.8)
    ax.set_yticks(range(0, 13, 2))
    tidy(ax, time_axis=True)
    ax.tick_params(labelbottom=False)

    # 底部状态条：窄幅色块标出每个小时在充电还是放电
    rib_color = {1: COOL, -1: WARM, 0: IDLE}
    for h in range(24):
        rb.add_patch(Rectangle((h, 0), 1.0, 1.0, facecolor=rib_color[phase[h]],
                               edgecolor="white", linewidth=0.7, zorder=2))
    for sign, label, color in ((1, "充电", "#2F6280"), (-1, "放电", "#9A5A22")):
        for lo, hi in runs_of(phase == sign):
            if hi - lo >= 2:
                rb.text((lo + hi) / 2, 0.5, label, ha="center", va="center",
                        fontsize=8, color=color, zorder=3)
    rb.set_ylim(0, 1)
    rb.set_yticks([])
    rb.set_xlabel("时刻 / h", color=INK)
    rb.set_xlim(0, 24)
    rb.set_xticks(range(0, 25, 4))
    for side in ["top", "right", "left"]:
        rb.spines[side].set_visible(False)
    rb.spines["bottom"].set_color(SPINE)
    rb.tick_params(axis="x", length=3, color=TICK, labelsize=9, labelcolor=INK)

    handles = [
        Line2D([], [], color=TEAL, lw=2.2, label="中位 SOC"),
        Patch(facecolor=TEAL, alpha=0.24, edgecolor="none", label="P10–P90"),
        Patch(facecolor=rib_color[1], edgecolor="none", label="充电时段"),
        Patch(facecolor=rib_color[-1], edgecolor="none", label="放电时段"),
    ]
    ax.legend(handles=handles, ncol=4, frameon=False, fontsize=9,
              loc="lower center", bbox_to_anchor=(0.5, 1.02), borderaxespad=0,
              handlelength=1.7, columnspacing=1.8)
    cycles = _mean_daily_cycles(soc)
    hit = int(((soc.max(axis=0) >= SOC_MAX - 1)
               & (soc.min(axis=0) <= SOC_MIN + 1)).sum())
    fig.text(0.5, 0.005,
             f"报告期 {soc.shape[1]} 天中有 {hit} 天同时触到上下限，"
             f"平均每天完成约 {cycles:.1f} 轮完整充放",
             ha="center", color=MUTED, fontsize=8.5)
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.155, top=0.885)
    save(fig, "fig_q2_soc_heatmap.png")


# ------------------------------------------------------- 图5 月度紧急购电与弃光
def figure_monthly_outcomes(logs):
    """并排水平渐变条：12 个月各占一行，条长即该月累计电量。

    取代原来的上下分面柱状图。水平布局让月份与数值都有舒展的落位，条体做
    浅到深的横向渐变、并叠一层月均参考线，避免纯色块的扁平观感。紧急购电与
    弃光相差约一个量级，两栏各自独立横轴刻度，不共用长度基准。
    """
    monthly = pd.DataFrame({
        "month": [int(x["date"][5:7]) for x in logs],
        "emergency": [x["emergency_kwh"] for x in logs],
        "curtail": [x["curtail_kwh"] for x in logs],
    }).groupby("month").sum()
    months = monthly.index.to_numpy()
    specs = [
        ("emergency", "紧急购电", "计划不足被迫高价补购", RED),
        ("curtail", "弃光", "光伏出力无法消纳", GOLD),
    ]
    y = np.arange(len(months))

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 6.2))
    for ax, (key, name, sub, color) in zip(axes, specs):
        values = monthly[key].to_numpy() / 1000
        ax.set_facecolor("#FAFBFC")
        gradient_barh(ax, y, values, 0.60, color)

        peak = int(np.argmax(values))
        for yi, value in zip(y, values):
            is_peak = yi == peak
            # 白描边保证数值压在月均虚线上也读得清
            ax.annotate(f"{value:.1f}", xy=(value, yi), xytext=(7, 0),
                        textcoords="offset points", ha="left", va="center",
                        fontsize=8.5, color=INK if is_peak else MUTED,
                        fontweight="bold" if is_peak else "normal", zorder=10,
                        path_effects=[Stroke(linewidth=2.6, foreground="white"),
                                      Normal()])

        avg = float(values.mean())
        ax.axvline(avg, color=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=9)
        ax.annotate(f"月均 {avg:.0f}", xy=(avg, -0.58),
                    xytext=(4, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=8.5, color=MUTED)

        ax.set_yticks(y, [f"{m}月" for m in months])
        ax.set_ylim(len(months) - 0.45, -0.95)
        ax.set_xlim(0, float(values.max()) * 1.22)
        ax.set_xlabel("月累计电量 / MWh", color=INK)
        tidy(ax, grid_axis="x")
        ax.set_title(f"{name}：{sub}", loc="left", fontsize=11.5,
                     color=INK, pad=26)
        ax.annotate(f"全年 {values.sum():,.0f} MWh", xy=(1.0, 1.0),
                    xycoords="axes fraction", xytext=(0, 20),
                    textcoords="offset points", ha="right", va="center",
                    fontsize=9.5, color=color, fontweight="bold")

    fig.suptitle("供需错配的两种结果：紧急补购与弃光", fontsize=13.5,
                 color=INK, y=0.985)
    fig.text(0.5, 0.012,
             "两栏横轴刻度不同，仅可比各自月内差异，不可跨栏比条长。",
             ha="center", color=MUTED, fontsize=8.5)
    fig.subplots_adjust(left=0.072, right=0.978, bottom=0.115, top=0.845,
                        wspace=0.32)
    save(fig, "fig_q2_emergency_curtailment.png")


# ------------------------------------------------------------------ 图6 参数候选
def figure_parameter_selection(res):
    """保留散点图型，只统一配色与坐标区样式。"""
    tune = res["tuning"]["joint"]
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    sc = ax.scatter(tune.validation_total_cost / 1e4,
                    tune.validation_emergency_cost / 1e4,
                    c=tune.beta, s=30, alpha=0.8, cmap="cividis",
                    edgecolors="white", linewidths=0.4)
    chosen = tune[tune.is_selected]
    ax.scatter(chosen.validation_total_cost / 1e4,
               chosen.validation_emergency_cost / 1e4,
               marker="*", s=340, color=RED, edgecolors="white", linewidths=0.9,
               zorder=5, label="仅历史期选中参数")
    ax.set_xlabel("验证期总费用 / 万元", color=INK)
    ax.set_ylabel("验证期紧急购电费 / 万元", color=INK)
    tidy(ax, grid_axis="both")
    cbar = fig.colorbar(sc, ax=ax, fraction=0.042, pad=0.025)
    cbar.set_label("风险权重 β", color=INK, fontsize=9)
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(length=2, width=0.5, color=TICK, labelsize=8,
                        labelcolor=INK)
    ax.legend(frameon=False, fontsize=9.5, loc="upper right",
              handletextpad=0.4)
    fig.subplots_adjust(left=0.10, right=0.985, bottom=0.115, top=0.965)
    save(fig, "fig_q2_cvar_frontier.png")


def run():
    ds, fc, res = load("q2_dataset.pkl"), load("forecasts.pkl"), load("q2_rolling_results.pkl")
    sc = load(f"scenarios_M{res['m_best']}.pkl")
    logs = res["report_logs"]
    worst = max(logs, key=lambda x: x["cost_emergency"])

    figure_forecast_fan(ds, fc, sc)
    figure_error_dumbbell()
    figure_settlement(worst)
    figure_soc_profile(logs)
    figure_monthly_outcomes(logs)
    figure_parameter_selection(res)
    print(f"six Q2 figures written to {PICS}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"figure generation failed: {exc}")
        raise
