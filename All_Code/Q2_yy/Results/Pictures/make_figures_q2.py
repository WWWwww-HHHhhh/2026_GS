from pathlib import Path
import pickle

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, to_rgb
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
def _figure_monthly_outcomes_legacy(logs):
    """上下双面板 + 弃光率色条：两个指标量级差近一个数量级，故各自独立纵轴。

    上幅为紧急购电电量、下幅为弃光电量，两幅共用月份横轴，季节节律可直接对齐；
    底部窄色条给出月度弃光率，把「绝对量」与「相对占比」压进同一张图。
    不再使用镜像归一化面积带——归一化后两半高度不可比，会掩盖 9 倍的量级差。
    """
    monthly = pd.DataFrame({
        "month": [int(x["date"][5:7]) for x in logs],
        "emergency": [x["emergency_kwh"] for x in logs],
        "curtail": [x["curtail_kwh"] for x in logs],
        "cost_emergency": [x["cost_emergency"] for x in logs],
        "pv": [float(np.asarray(x["pv_actual"], dtype=float).sum()) for x in logs],
    }).groupby("month").sum()
    months = monthly.index.to_numpy()
    emergency = monthly["emergency"].to_numpy(dtype=float) / 1000
    curtail = monthly["curtail"].to_numpy(dtype=float) / 1000
    pv = monthly["pv"].to_numpy(dtype=float) / 1000
    cost = monthly["cost_emergency"].to_numpy(dtype=float)
    rate = curtail / (pv + curtail) * 100
    x = np.arange(len(months), dtype=float)
    xlim = (-0.72, len(x) - 0.28)

    fig = plt.figure(figsize=(11.4, 6.3))
    gs = fig.add_gridspec(3, 1, height_ratios=[3.0, 3.5, 0.62], hspace=0.30,
                          left=0.092, right=0.975, top=0.935, bottom=0.115)
    ax_top = fig.add_subplot(gs[0])
    ax_bot = fig.add_subplot(gs[1], sharex=ax_top)
    ax_rb = fig.add_subplot(gs[2], sharex=ax_top)

    # 两幅共用的季节底纹：光伏高发期，解释弃光为何集中在 4—9 月
    for ax in (ax_top, ax_bot):
        ax.set_facecolor("#FAFBFC")
        ax.axvspan(1.5, 7.5, color="#F8F3E9", zorder=0)

    label_effect = [Stroke(linewidth=2.4, foreground="white"), Normal()]

    def panel(ax, values, color, unit_ticks, peak_note):
        """一幅月度渐变柱：数值标签 + 月均参考线 + 峰值环。"""
        ymax = float(values.max()) * 1.30
        gradient_col(ax, x, values, 0.62, color, zorder=3)
        for j, value in enumerate(values):
            ax.text(x[j], value + ymax * 0.024, f"{value:.1f}", ha="center",
                    va="bottom", fontsize=8.4, color=color, zorder=6,
                    path_effects=label_effect,
                    fontweight="bold" if j == int(np.argmax(values)) else "normal")
        mean = float(values.mean())
        ax.axhline(mean, color=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=5)
        ax.text(xlim[0] + 0.06, mean, f"月均 {mean:.1f}", ha="left",
                va="bottom", fontsize=8.2, color=MUTED, zorder=6,
                path_effects=label_effect)
        ax.bar(x[int(np.argmax(values))], values.max(), width=0.62, color="none",
               edgecolor=color, linewidth=1.25, zorder=7)
        ax.set_ylim(0, ymax)
        ax.set_yticks(unit_ticks)
        ax.set_xlim(*xlim)
        tidy(ax)
        ax.tick_params(labelbottom=False)
        ax.text(0.997, 0.965, peak_note, transform=ax.transAxes, ha="right",
                va="top", fontsize=8.5, color=MUTED, zorder=6)

    panel(ax_top, emergency, RED, np.arange(0, 31, 10),
          f"合计 {emergency.sum():,.1f} MWh ｜ 紧急购电费 {cost.sum()/1e4:,.1f} 万元")
    year_rate = curtail.sum() / (pv.sum() + curtail.sum()) * 100
    panel(ax_bot, curtail, GOLD, np.arange(0, 301, 100),
          f"合计 {curtail.sum():,.1f} MWh ｜ 全年弃光率 {year_rate:.1f}%")

    ax_top.set_title("紧急购电", loc="left", fontsize=11.5, color=RED, pad=9)
    ax_bot.set_title("弃光", loc="left", fontsize=11.5, color="#A87822", pad=9)
    ax_top.set_ylabel("月度电量 / MWh", color=INK)
    ax_bot.set_ylabel("月度电量 / MWh", color=INK)
    ax_top.text((1.5 + 7.5) / 2, float(emergency.max()) * 1.30 * 0.955,
                "光伏高发期 4—9月", ha="center", va="top", fontsize=8.2,
                color="#B08A4A", zorder=6)

    # 底部窄色条：月度弃光率，颜色深浅随占比变化
    lo, hi = float(rate.min()), float(rate.max())
    ax_rb.set_ylim(0, 1)
    ax_rb.set_yticks([])
    for j, value in enumerate(rate):
        factor = 0.20 + 0.65 * (value - lo) / (hi - lo)
        ax_rb.add_patch(Rectangle((x[j] - 0.46, 0.05), 0.92, 0.90,
                                  facecolor=tint(GOLD, factor), edgecolor="white",
                                  linewidth=0.9, zorder=2))
        ax_rb.text(x[j], 0.50, f"{value:.1f}%", ha="center", va="center",
                   fontsize=8.0, color=INK, zorder=3)
    ax_rb.set_ylabel("弃光率", rotation=0, ha="right", va="center", fontsize=9,
                     color=INK, labelpad=14)
    ax_rb.set_xticks(x, [f"{m}月" for m in months])
    ax_rb.set_xlim(*xlim)
    for side in ["top", "right", "left"]:
        ax_rb.spines[side].set_visible(False)
    ax_rb.spines["bottom"].set_color(SPINE)
    ax_rb.tick_params(axis="x", length=3, color=TICK, labelsize=9, labelcolor=INK)

    fig.text(0.5, 0.018,
             f"注：上幅为紧急购电、下幅为弃光，两栏纵轴量级相差约 9 倍"
             f"（弃光 {curtail.sum():,.1f} MWh 约为紧急购电 {emergency.sum():,.1f} MWh 的 "
             f"{curtail.sum() / emergency.sum():.1f} 倍），柱高不可跨栏比较；"
             f"底部色条为月度弃光率（弃光量 ÷ 光伏可发量）",
             ha="center", va="bottom", fontsize=8.3, color=MUTED)
    save(fig, "fig_q2_emergency_curtailment.png")


def figure_monthly_outcomes(logs):
    """宽幅镜像面积图，突出两类供需偏差的季节分布与峰值月份。"""
    monthly = pd.DataFrame({
        "month": [int(x["date"][5:7]) for x in logs],
        "emergency": [x["emergency_kwh"] for x in logs],
        "curtail": [x["curtail_kwh"] for x in logs],
    }).groupby("month").sum()
    months = monthly.index.to_numpy()
    emergency = monthly["emergency"].to_numpy(dtype=float) / 1000
    curtail = monthly["curtail"].to_numpy(dtype=float) / 1000
    x = np.arange(len(months), dtype=float)

    def smooth_profile(values, points_per_interval=55):
        values = np.asarray(values, dtype=float)
        slopes = np.gradient(values)
        dense_x, dense_y = [], []
        for i in range(len(values) - 1):
            u = np.linspace(0, 1, points_per_interval, endpoint=False)
            h00 = 2 * u ** 3 - 3 * u ** 2 + 1
            h10 = u ** 3 - 2 * u ** 2 + u
            h01 = -2 * u ** 3 + 3 * u ** 2
            h11 = u ** 3 - u ** 2
            segment = (h00 * values[i] + h10 * slopes[i] +
                       h01 * values[i + 1] + h11 * slopes[i + 1])
            dense_x.extend(i + u)
            dense_y.extend(segment)
        dense_x.append(float(len(values) - 1))
        dense_y.append(float(values[-1]))
        return np.asarray(dense_x), np.clip(np.asarray(dense_y), 0, 1.05)

    top_values = emergency / emergency.max()
    bottom_values = curtail / curtail.max()
    dense_x, top = smooth_profile(top_values)
    _, bottom_abs = smooth_profile(bottom_values)
    bottom = -bottom_abs

    fig, ax = plt.subplots(figsize=(12.8, 2.75))
    ax.set_facecolor("white")
    ax.fill_between(dense_x, 0, top, color=tint(RED, 0.48), alpha=0.96,
                    linewidth=0, zorder=2)
    ax.fill_between(dense_x, 0, bottom, color=tint(GOLD, 0.50), alpha=0.96,
                    linewidth=0, zorder=2)
    ax.fill_between(dense_x, top * 0.73, top,
                    color=tint(RED, 0.84), alpha=0.30, linewidth=0, zorder=3)
    ax.fill_between(dense_x, bottom, bottom * 0.73,
                    color=tint(GOLD, 0.86), alpha=0.28, linewidth=0, zorder=3)
    ax.axhline(0, color=SPINE, lw=0.85, zorder=4)

    for j, month in enumerate(months):
        ax.plot([j, j], [-0.035, 0.035], color=SPINE, lw=0.65, zorder=5)
        ax.text(j, -0.075, f"{month}月", ha="center", va="top",
                fontsize=8.0, color=INK, zorder=5)

    emergency_peak = int(np.argmax(emergency))
    curtail_peak = int(np.argmax(curtail))
    ax.scatter(emergency_peak, top_values[emergency_peak], s=42, color=RED,
               edgecolors="white", linewidths=0.8, zorder=6)
    ax.scatter(curtail_peak, -bottom_values[curtail_peak], s=42, color=GOLD,
               edgecolors="white", linewidths=0.8, zorder=6)
    ax.annotate(f"峰值  {emergency[emergency_peak]:.1f} MWh",
                xy=(emergency_peak, top_values[emergency_peak]),
                xytext=(0, 13), textcoords="offset points",
                ha="center", va="bottom", fontsize=8.4, color=RED,
                fontweight="bold")
    ax.annotate(f"峰值  {curtail[curtail_peak]:.1f} MWh",
                xy=(curtail_peak, -bottom_values[curtail_peak]),
                xytext=(0, -14), textcoords="offset points",
                ha="center", va="top", fontsize=8.4, color="#A87822",
                fontweight="bold")

    ax.text(-0.42, 0.71, f"紧急购电\n合计 {emergency.sum():,.0f} MWh",
            color=RED, fontsize=9.2, fontweight="bold", ha="right",
            va="center", linespacing=1.35)
    ax.text(-0.42, -0.71, f"弃光\n合计 {curtail.sum():,.0f} MWh",
            color="#A87822", fontsize=9.2, fontweight="bold", ha="right",
            va="center", linespacing=1.35)

    ax.set_xlim(-0.95, len(months) - 0.82)
    ax.set_ylim(-1.25, 1.25)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.subplots_adjust(left=0.07, right=0.995, bottom=0.05, top=0.98)
    save(fig, "fig_q2_emergency_curtailment.png")


# ------------------------------------------------------------------ 图6 参数候选
def figure_parameter_selection(res):
    """用并列热力矩阵展示 96 组候选的费用与风险，突出最终选点。"""
    tune = res["tuning"]["joint"]
    betas = sorted(tune.beta.unique())
    m_values = sorted(tune.M.unique())
    kappa_values = sorted(tune.kappa_mult.unique())
    columns = [(m, k) for m in m_values for k in kappa_values]

    def matrix(field, scale):
        values = np.empty((len(betas), len(columns)))
        for i, beta in enumerate(betas):
            for j, (m, kappa) in enumerate(columns):
                row = tune[(tune.beta == beta) &
                           (tune.M == m) &
                           (tune.kappa_mult == kappa)].iloc[0]
                values[i, j] = row[field] / scale
        return values

    total_cost = matrix("validation_total_cost", 1e4)
    emergency_cost = matrix("validation_emergency_cost", 1e4)
    selected = tune[tune.is_selected].iloc[0]
    selected_row = betas.index(selected.beta)
    selected_col = columns.index((selected.M, selected.kappa_mult))

    blue_map = LinearSegmentedColormap.from_list(
        "cost_blue", ["#F5F8FA", "#C9DCE7", "#557F9A"])
    warm_map = LinearSegmentedColormap.from_list(
        "risk_warm", ["#FFF8EB", "#F1CE8A", "#C96F48"])

    fig, axes = plt.subplots(1, 2, figsize=(12.6, 3.0), sharey=True)
    panels = [
        (axes[0], total_cost, blue_map, "验证期总费用", "万元"),
        (axes[1], emergency_cost, warm_map, "紧急购电费用", "万元"),
    ]
    xlabels = [f"{m}/{k:g}" for m, k in columns]

    for ax, values, cmap, title, unit in panels:
        image_obj = ax.imshow(values, cmap=cmap, aspect="auto",
                              interpolation="nearest")
        ax.set_title(title, fontsize=11.5, color=INK, pad=8,
                     fontweight="bold")
        ax.set_xticks(np.arange(len(columns)), xlabels, fontsize=7.2)
        ax.set_yticks(np.arange(len(betas)), [f"{b:g}" for b in betas],
                      fontsize=7.8)
        ax.set_xlabel("场景数 $M$ / 软终端倍数 $\\lambda$", color=INK,
                      labelpad=6)
        ax.tick_params(axis="both", length=0, colors=INK)
        for x in np.arange(-0.5, len(columns), 1):
            ax.axvline(x, color="white", lw=0.8, alpha=0.85)
        for y in np.arange(-0.5, len(betas), 1):
            ax.axhline(y, color="white", lw=0.8, alpha=0.85)
        ax.add_patch(Rectangle((selected_col - 0.48, selected_row - 0.48),
                               0.96, 0.96, fill=False, edgecolor=RED,
                               linewidth=2.0, zorder=5))
        ax.scatter(selected_col, selected_row, marker="*", s=82,
                   color=RED, edgecolors="white", linewidths=0.6, zorder=6)
        for spine in ax.spines.values():
            spine.set_visible(False)
        cbar = fig.colorbar(image_obj, ax=ax, fraction=0.026, pad=0.018)
        cbar.set_label(unit, color=INK, fontsize=8)
        cbar.outline.set_visible(False)
        cbar.ax.tick_params(length=2, width=0.5, labelsize=7,
                            color=TICK, labelcolor=INK)

    axes[0].set_ylabel("风险权重 $\\beta$", color=INK)
    fig.subplots_adjust(left=0.055, right=0.965, bottom=0.19, top=0.88,
                        wspace=0.16)
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
