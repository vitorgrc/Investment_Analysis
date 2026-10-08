"""Generates the charts used in the README and the article.

Run from anywhere:  python code/generate_charts.py
Reads  data/stock_prices.csv  and writes PNG files to  images/.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "images"; OUT.mkdir(exist_ok=True)

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID, SHADE = "#0b0b0b", "#52514e", "#e4e3df", "#f0efeb"
plt.rcParams.update({"font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK})

# ----------------------------------------------------------------- data
prices = pd.read_csv(ROOT / "data" / "stock_prices.csv", parse_dates=["Date"]).set_index("Date").sort_index()
ret = prices.pct_change().dropna()
n = ret.shape[1]
w_eq = np.repeat(1 / n, n)                       # equal weights (1/9 each)
r = ret @ w_eq                                   # equal-weight portfolio daily return
CRASH_START, CRASH_END = pd.Timestamp("2020-02-20"), pd.Timestamp("2020-04-30")
crash = (ret.index >= CRASH_START) & (ret.index <= CRASH_END)
PORTFOLIO_VALUE = 1_000_000


def style(ax, grid="y"):
    ax.spines[["top", "right"]].set_visible(False)
    if grid:
        ax.grid(axis=grid, color=GRID, lw=.7); ax.set_axisbelow(True)


def pct(x, d=1): return f"{x * 100:.{d}f}%"
def brl(v): return "R\\$ " + f"{v:,.0f}"          # escaped $ so matplotlib does not read it as math text
def var_es(x):
    v = np.percentile(x, 5); return v, x[x <= v].mean()


# ---------------------------------------------------- 1) portfolio value
idx = pd.concat([pd.Series([100.0], index=[prices.index[0]]), (1 + r).cumprod() * 100])
pk = idx.loc[:"2020-03-18"].idxmax(); tr = idx.loc["2020-02-01":"2020-06-30"].idxmin()
rec = idx.loc[tr:][idx.loc[tr:] >= idx[pk]].index.min()
fig, ax = plt.subplots(figsize=(10, 5.6)); style(ax)
ax.axvspan(CRASH_START, CRASH_END, color=SHADE, zorder=0)
ax.plot(idx.index, idx.values, color=BLUE, lw=2)
ax.scatter([pk, tr, rec], [idx[pk], idx[tr], idx[pk]], color=[BLUE, ORANGE, BLUE], s=55, zorder=5, edgecolor="white", linewidth=1.5)
ax.annotate(f"Peak: {idx[pk]:.0f}\n({pk:%Y-%m-%d})", (pk, idx[pk]), xytext=(-12, 8), textcoords="offset points", ha="right", va="bottom", fontsize=9.5)
ax.annotate(f"Trough: {idx[tr]:.0f}\n({tr:%Y-%m-%d})", (tr, idx[tr]), xytext=(14, -4), textcoords="offset points", ha="left", va="top", fontsize=9.5)
ax.annotate(f"Peak recovered\n({rec:%Y-%m-%d})", (rec, idx[pk]), xytext=(12, -16), textcoords="offset points", ha="left", va="top", fontsize=9.5)
dd = idx[tr] / idx[pk] - 1
ax.text(CRASH_END + pd.Timedelta(days=14), 84, f"{abs(dd) * 100:.0f}% drop\npeak to trough\n(8 weeks)", ha="left", va="center", fontsize=10)
ax.set_ylim(55, idx.max() + 8)
ax.set_title("Portfolio value (base 100, equal weights): the March 2020 crash erased almost half of it", loc="left", fontsize=12)
ax.set_ylabel("Index (2019-08-30 = 100)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
plt.tight_layout(); plt.savefig(OUT / "01_portfolio_value.png", dpi=200, facecolor="white"); plt.close()

# ----------------------------------------------- 2) histogram, VaR and ES
var95, es95 = var_es(r)
fig, ax = plt.subplots(figsize=(10, 5.6)); style(ax)
bins = np.arange(-0.17, 0.14, 0.005)
counts, edges, patches = ax.hist(r, bins=bins, edgecolor="white", lw=.5)
for p, left in zip(patches, edges[:-1]):
    tail = left + 0.005 <= var95 + 1e-12
    p.set_facecolor(ORANGE if tail else BLUE); p.set_alpha(0.95 if tail else 0.85)
ax.axvline(var95, color=INK, lw=2); ax.axvline(es95, color=INK, lw=2, ls="--")
ymax = counts.max() * 1.38; ax.set_ylim(0, ymax)
ax.text(var95 + 0.003, ymax * 0.97, f"VaR 95%: {pct(var95, 2)}\n({brl(abs(var95) * PORTFOLIO_VALUE)} on a R\\$ 1 million portfolio)", ha="left", va="top", fontsize=10)
ax.text(es95 - 0.003, ymax * 0.62, f"Expected Shortfall 95%:\n{pct(es95, 2)} ({brl(abs(es95) * PORTFOLIO_VALUE)})", ha="right", va="top", fontsize=10)
ax.text(-0.168, ymax * 0.2, "The worst 5% of days\n(in orange)", fontsize=9.5, color=MUTED, ha="left", va="bottom")
ax.set_title("Daily portfolio returns: ES is the average loss on the days when VaR is exceeded", loc="left", fontsize=12)
ax.set_xlabel("Daily portfolio return"); ax.set_ylabel("Number of days")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
plt.tight_layout(); plt.savefig(OUT / "02_histogram_var_es.png", dpi=200, facecolor="white"); plt.close()

# ----------------------------------------- 3) VaR and ES with/without crash
v_f, e_f = var_es(r); v_x, e_x = var_es(r[~crash])
fig, ax = plt.subplots(figsize=(8.5, 5.2)); style(ax)
x = np.arange(2); w = .34
b1 = ax.bar(x - w / 2 - .01, [abs(v_f), abs(e_f)], w, color=BLUE, label=f"Full period ({len(r)} days)")
b2 = ax.bar(x + w / 2 + .01, [abs(v_x), abs(e_x)], w, color=ORANGE, label=f"Excluding Feb-Apr 2020 ({int((~crash).sum())} days)")
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + .0012, "-" + pct(b.get_height(), 2), ha="center", fontsize=10.5)
ax.set_xticks(x); ax.set_xticklabels(["VaR 95%", "Expected Shortfall 95%"], fontsize=11)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
ax.set_ylabel("Daily loss (absolute value)"); ax.set_ylim(0, .072); ax.legend(frameon=False, loc="upper left")
ax.set_title(f"Without the crash, ES is cut in half ({pct(e_f, 1)} to {pct(e_x, 1)})", loc="left", fontsize=12)
plt.tight_layout(); plt.savefig(OUT / "03_var_es_with_without_crash.png", dpi=200, facecolor="white"); plt.close()

# ------------------------------------------------- optimisation (Markowitz)
cov = ret.cov().values
def min_var(ub=1.0):
    res = minimize(lambda w: w @ cov @ w, w_eq, method="SLSQP", bounds=[(0, ub)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}], options={"ftol": 1e-14, "maxiter": 1000})
    return res.x
w_mv, w_cap = min_var(), min_var(0.30)
vol_eq, vol_mv, vol_cap = (np.sqrt(w @ cov @ w) for w in (w_eq, w_mv, w_cap))

# --------------------------------------------------- 4) volatility by stock
vol = ret.std().sort_values()
vol_la_adj = ret["Lojas Americanas"].drop(pd.Timestamp("2021-07-06")).std()
fig, ax = plt.subplots(figsize=(10, 5.6)); style(ax, "x"); ax.grid(axis="y", visible=False)
yy = np.arange(n)
ax.barh(yy, vol.values * 100, height=.62, color=BLUE)
for i, (_, v) in enumerate(vol.items()):
    ax.text(v * 100 + .04, i, f"{v * 100:.2f}%", va="center", fontsize=10)
la_i = list(vol.index).index("Lojas Americanas")
ax.scatter([vol_la_adj * 100], [la_i], marker="D", s=48, color=ORANGE, zorder=5, edgecolor="white", linewidth=1.2)
ax.scatter([vol.iloc[la_i] * 100 + .72], [la_i], marker="D", s=48, color=ORANGE, zorder=5, edgecolor="white", linewidth=1.2)
ax.text(vol.iloc[la_i] * 100 + .82, la_i, f"{vol_la_adj * 100:.2f}% excluding 2021-07-06", va="center", ha="left", fontsize=9.5)
ax.set_yticks(yy); ax.set_yticklabels(vol.index)
ax.axvline(vol_eq * 100, color=INK, lw=2); ax.axvline(vol_mv * 100, color=INK, lw=2, ls="--")
ax.text(vol_eq * 100 + .03, -.95, f"Equal-weight portfolio: {vol_eq * 100:.2f}%", fontsize=9.5, va="top", ha="left")
ax.text(vol_mv * 100 - .03, -.95, f"Optimal portfolio: {vol_mv * 100:.2f}%", fontsize=9.5, va="top", ha="right")
ax.set_ylim(-1.3, n - .4); ax.set_xlim(0, 7.2)
ax.set_xlabel("Daily volatility (standard deviation of returns, %)")
ax.set_title("Volatility: the portfolio is less risky than any single stock", loc="left", fontsize=12)
plt.tight_layout(); plt.savefig(OUT / "04_volatility_by_stock.png", dpi=200, facecolor="white"); plt.close()

# --------------------------------------------------- 5) optimiser weights
order = np.argsort(-w_mv); names = np.array(ret.columns)[order]
fig, ax = plt.subplots(figsize=(10, 6)); style(ax, "x"); ax.grid(axis="y", visible=False)
yy = np.arange(n); h = .26
ax.barh(yy - h - .01, w_eq[order] * 100, h, color=MUTED, alpha=.55, label=f"Equal weights (volatility {vol_eq * 100:.2f}%)")
ax.barh(yy, w_mv[order] * 100, h, color=BLUE, label=f"Minimum variance (volatility {vol_mv * 100:.2f}%)")
ax.barh(yy + h + .01, w_cap[order] * 100, h, color=ORANGE, label=f"Minimum variance, 30% cap ({vol_cap * 100:.2f}%)")
for i in range(n):
    for off, val in ((-h - .01, w_eq[order][i]), (0, w_mv[order][i]), (h + .01, w_cap[order][i])):
        ax.text(val * 100 + .5, i + off, "0%" if val < 0.0005 else f"{val * 100:.1f}%", va="center", fontsize=8.5)
ax.set_yticks(yy); ax.set_yticklabels(names); ax.invert_yaxis()
ax.set_xlim(0, 52); ax.set_xlabel("Weight in the portfolio (%)"); ax.legend(frameon=False, loc="lower right", fontsize=9.5)
ax.set_title("Optimiser: the lowest variability concentrates the portfolio in Klabin", loc="left", fontsize=12)
plt.tight_layout(); plt.savefig(OUT / "05_optimizer_weights.png", dpi=200, facecolor="white"); plt.close()

# ---------------------------------------------------- 6) correlation matrix
cmap = LinearSegmentedColormap.from_list("seq", ["#f3f7fd", "#9ec1ee", "#2a78d6", "#123a73"])
c_full, c_ex = ret.corr(), ret[~crash].corr(); iu = np.triu_indices(n, 1)
fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))
for ax, c, ttl in ((axes[0], c_full, f"Full period (average pair: {c_full.values[iu].mean():.2f})"),
                   (axes[1], c_ex, f"Excluding Feb-Apr 2020 (average pair: {c_ex.values[iu].mean():.2f})")):
    m = c.values; cols = list(c.columns)
    show = np.full((n - 1, n - 1), np.nan)
    for i in range(1, n):
        for j in range(i): show[i - 1, j] = m[i, j]
    im = ax.imshow(show, cmap=cmap, vmin=0, vmax=.7)
    for i in range(1, n):
        for j in range(i):
            v = round(m[i, j], 2); v = 0.0 if v == 0 else v
            ax.text(j, i - 1, f"{v:.2f}", ha="center", va="center", fontsize=9.5, color="white" if v > .42 else INK)
    ax.set_xticks(range(n - 1)); ax.set_yticks(range(n - 1))
    ax.set_xticklabels(cols[:-1], rotation=40, ha="right", fontsize=10); ax.set_yticklabels(cols[1:], fontsize=10)
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.tick_params(length=0); ax.set_title(ttl, loc="left", fontsize=11.5)
    ax.set_xticks(np.arange(-.5, n - 1, 1), minor=True); ax.set_yticks(np.arange(-.5, n - 1, 1), minor=True)
    ax.grid(which="minor", color="white", lw=2); ax.tick_params(which="minor", length=0)
cb = fig.colorbar(im, ax=axes, shrink=.7, pad=.015); cb.outline.set_visible(False); cb.set_label("Pearson correlation", color=MUTED)
fig.suptitle("Correlation between stocks: the 2020 crash almost doubles the average correlation", x=.06, ha="left", fontsize=13, y=.97)
plt.savefig(OUT / "06_correlation_matrix.png", dpi=200, facecolor="white", bbox_inches="tight"); plt.close()

# ------------------------------------------- 7) Lojas Americanas price break
la = prices["Lojas Americanas"]; d = pd.Timestamp("2021-07-06")
fig, ax = plt.subplots(figsize=(10, 5.4)); style(ax)
ax.plot(la.index, la.values, color=BLUE, lw=1.8)
ax.scatter([d], [la[d]], color=ORANGE, s=60, zorder=5, edgecolor="white", linewidth=1.5)
ax.annotate("2021-07-06: R\\$ 21.11 to R\\$ 8.49 (-59.8%)\nOne single day, with no similar move in the\nother stocks: consistent with a corporate\nevent rather than a market loss", (d, la[d]), xytext=(-18, -4), textcoords="offset points", ha="right", va="top", fontsize=9.5)
ax.set_ylim(0, 40)
ax.set_title("Lojas Americanas: the \"biggest drop\" in the data is a break in the price series", loc="left", fontsize=12)
ax.set_ylabel("Closing price (R\\$, source: Yahoo Finance)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
plt.tight_layout(); plt.savefig(OUT / "07_lojas_americanas_price.png", dpi=200, facecolor="white"); plt.close()

print("Charts saved to", OUT)
print(f"Equal-weight: vol {vol_eq:.4%}, VaR95 {var95:.4%}, ES95 {es95:.4%}")
print(f"Min variance: vol {vol_mv:.4%}; weights {np.round(w_mv * 100, 1)}")
print(f"30% cap     : vol {vol_cap:.4%}; weights {np.round(w_cap * 100, 1)}")
