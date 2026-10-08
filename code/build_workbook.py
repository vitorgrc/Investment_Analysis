"""Builds spreadsheets/var_portfolio_analysis.xlsx (all calculations are live Excel formulas).

Run:  python code/build_workbook.py
Reads data/stock_prices.csv. The three optimised weight vectors are computed here with a quadratic
optimiser and written as inputs (blue); the workbook then evaluates every risk metric with formulas.
To reproduce them in Excel, run Solver as described on the 'Optimization' sheet.
"""
from pathlib import Path
import numpy as np, pandas as pd
from scipy.optimize import minimize
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.formatting.rule import ColorScaleRule
import datetime as dt

ROOT = Path(__file__).resolve().parent.parent
prices = pd.read_csv(ROOT / "data" / "stock_prices.csv", parse_dates=["Date"]).set_index("Date").sort_index()
names = list(prices.columns); n = len(names)
ret = prices.pct_change().dropna(); NR = len(ret)           # 491 returns
R1, RN = 2, NR + 1                                          # first/last data row on Returns (2..492)

# ------------------------------------------------ optimised weights (inputs)
def min_var(cov, ub=1.0):
    res = minimize(lambda w: w @ cov @ w, np.repeat(1 / n, n), method="SLSQP", bounds=[(0, ub)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}], options={"ftol": 1e-14, "maxiter": 1000})
    return res.x
crash = (ret.index >= "2020-02-20") & (ret.index <= "2020-04-30")
W_MV = min_var(ret.cov().values); W_CAP = min_var(ret.cov().values, .30)
W_TRAIN = min_var(ret.loc[:"2020-08-26"].cov().values); W_EXC = min_var(ret[~crash].cov().values)

# ------------------------------------------------------------- styling
F = "Arial"
def font(**k): return Font(name=F, size=k.pop("size", 10), **k)
BLUE, GREEN, BLACK = "0000FF", "008000", "000000"
HFILL = PatternFill("solid", fgColor="1F3864"); SFILL = PatternFill("solid", fgColor="D9E1F2"); YFILL = PatternFill("solid", fgColor="FFFF00")
thin = Side(style="thin", color="BFBFBF"); BOX = Border(top=thin, bottom=thin, left=thin, right=thin)
PCT, PCT1, BRL, DATE, NUM = "0.00%;-0.00%;-", "0.0%", '"R$" #,##0;-"R$" #,##0;-', "yyyy-mm-dd", "#,##0.00"

def put(ws, ref, value, color=BLACK, fmt=None, bold=False, fill=None, align=None, wrap=False, italic=False, size=10):
    c = ws[ref]; c.value = value; c.font = font(color=color, bold=bold, italic=italic, size=size)
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
    if align or wrap: c.alignment = Alignment(horizontal=align, vertical="top" if wrap else "center", wrap_text=wrap)
    return c
def header(ws, row, c0, labels, height=30):
    for j, t in enumerate(labels):
        c = ws.cell(row, c0 + j, t); c.font = font(bold=True, color="FFFFFF"); c.fill = HFILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = height
def title(ws, text, sub=None):
    put(ws, "A1", text, bold=True, size=14)
    if sub: put(ws, "A2", sub, italic=True, color="595959")
def widths(ws, d):
    for k, v in d.items(): ws.column_dimensions[k].width = v

wb = Workbook()
S = wb.active; S.title = "Summary"
I = wb.create_sheet("Inputs"); P = wb.create_sheet("Prices"); Rt = wb.create_sheet("Returns")
H = wb.create_sheet("Returns_Helper"); M = wb.create_sheet("Risk_Metrics"); C = wb.create_sheet("Correlation")
O = wb.create_sheet("Optimization"); B = wb.create_sheet("Backtest")

# ---------------------------------------------------------------- Inputs
title(I, "Inputs and assumptions", "Blue cells are hardcoded inputs; change them and every sheet recalculates.")
header(I, 3, 2, ["Parameter", "Value", "Comment"])
rows = [
 ("Portfolio value (R$)", 1_000_000, BRL, "Hypothetical portfolio used to convert percentages into R$."),
 ("Tail probability (1 - confidence level)", 0.05, "0.0%", "5% = 95% confidence level for VaR and Expected Shortfall."),
 ("Crash window start", dt.date(2020, 2, 20), DATE, "Start of the Covid-19 crash window used in the 'with / without crash' comparison."),
 ("Crash window end", dt.date(2020, 4, 30), DATE, "End of the crash window."),
 ("Trading days per year", 252, "0", "Used to annualise daily volatility (x SQRT(252))."),
 ("Training period end", dt.date(2020, 8, 26), DATE, "Last day used to estimate VaR / weights in the out-of-sample and backtest checks."),
 ("Backtest window (trading days)", 245, "0", "Length of each period in the backtest (same as the course exercise)."),
 ("Weight cap in constrained scenario", 0.30, "0%", "Maximum weight per stock in the '30% cap' optimisation scenario."),
 ("Date excluded as series break (Lojas Americanas)", dt.date(2021, 7, 6), DATE, "-59.8% in one day while the other stocks moved between -4.1% and +0.5%."),
]
for i, (lab, val, fmt, com) in enumerate(rows, start=4):
    put(I, f"B{i}", lab); put(I, f"C{i}", val, color=BLUE, fmt=fmt, fill=YFILL); put(I, f"D{i}", com, color="595959")
put(I, "B15", "Colour legend", bold=True)
put(I, "B16", "Blue font", color=BLUE); put(I, "C16", "Hardcoded input (prices, optimiser weights, parameters)")
put(I, "B17", "Black font"); put(I, "C17", "Formula calculated in the same sheet")
put(I, "B18", "Green font", color=GREEN); put(I, "C18", "Formula linking to another sheet")
put(I, "B19", "Yellow fill", fill=YFILL); put(I, "C19", "Key assumption you can change")
widths(I, {"A": 3, "B": 48, "C": 16, "D": 95})
VAL, TAIL, CS, CE, DAYS, TRAIN, WIN, CAP, BRK = (f"Inputs!$C${r}" for r in range(4, 13))

# ---------------------------------------------------------------- Prices
title(P, "Daily closing prices (R$)", "Source: Yahoo Finance Brazil, as provided in the course exercise. Hardcoded inputs.")
header(P, 3, 1, ["Date"] + names)
for i, (d, row) in enumerate(prices.iterrows(), start=4):
    put(P, f"A{i}", d.to_pydatetime(), color=BLUE, fmt=DATE)
    for j, v in enumerate(row.values, start=2): put(P, f"{L(j)}{i}", float(v), color=BLUE, fmt=NUM)
widths(P, {"A": 12, **{L(j): 14 for j in range(2, 11)}}); P.freeze_panes = "B4"
PR1 = 4                                                      # first price row

# ---------------------------------------------------------------- Returns
title(Rt, "Daily returns and portfolio series", "Return = price today / price yesterday - 1. Portfolio columns use the weight rows of the 'Optimization' sheet.")
heads = ["Date"] + names + ["Portfolio: equal weights", "Portfolio: min. variance", "Portfolio: min. variance, 30% cap",
         "Portfolio: min. variance (trained to training end)", "In crash window (1 = yes)", "Portfolio index (equal weights, base 100)",
         "Running peak", "Drawdown", "Lojas Americanas excl. series-break day", "Peak recovered (1 = yes)", "Equal-weight portfolio excl. series-break day"]
header(Rt, 3, 1, heads, height=60)
OFF = 2                                                       # Returns data rows start at row 4 -> use offset helpers
r0 = 4; rl = r0 + NR - 1                                      # 4..494
for k in range(NR):
    r = r0 + k; pr = PR1 + k + 1                              # price row of day t; previous = pr-1
    put(Rt, f"A{r}", f"=Prices!A{pr}", color=GREEN, fmt=DATE)
    for j in range(n):
        col = L(2 + j); put(Rt, f"{col}{r}", f"=Prices!{col}{pr}/Prices!{col}{pr-1}-1", color=GREEN, fmt=PCT)
    for j, wrow in enumerate((7, 8, 9, 10)):
        put(Rt, f"{L(11 + j)}{r}", f"=SUMPRODUCT(B{r}:J{r},Optimization!$C${wrow}:$K${wrow})", color=GREEN, fmt=PCT)
    put(Rt, f"O{r}", f"=IF(AND(A{r}>={CS},A{r}<={CE}),1,0)", color=GREEN, fmt="0")
    put(Rt, f"P{r}", f"=100*(1+K{r})" if k == 0 else f"=P{r-1}*(1+K{r})", fmt=NUM)
    put(Rt, f"Q{r}", f"=MAX(100,P{r})" if k == 0 else f"=MAX(Q{r-1},P{r})", fmt=NUM)
    put(Rt, f"R{r}", f"=P{r}/Q{r}-1", fmt=PCT)
    put(Rt, f"S{r}", f'=IF(A{r}={BRK},"",F{r})', color=GREEN, fmt=PCT)
    put(Rt, f"T{r}", "=0" if k == 0 else f"=IF(AND(A{r}>Risk_Metrics!$C$28,P{r}>=Risk_Metrics!$C$30),1,0)", color=GREEN, fmt="0")
    put(Rt, f"U{r}", f'=IF(A{r}={BRK},"",K{r})', color=GREEN, fmt=PCT)
widths(Rt, {"A": 12, **{L(j): 12 for j in range(2, 11)}, **{L(j): 15 for j in range(11, 22)}}); Rt.freeze_panes = "B4"
def rng(col, sheet="Returns"): return f"{sheet}!${col}${r0}:${col}${rl}"

# ---------------------------------------------------------------- Returns_Helper
title(H, "Helper series for the 'excluding crash' and 'crash only' calculations", "Cells are blank (text) when the day is outside / inside the crash window, so statistics functions ignore them.")
header(H, 3, 1, ["Date"] + [f"{x} (excl. crash)" for x in names] + [f"{x} (crash only)" for x in names] + ["Equal-weight portfolio (excl. crash)"], height=45)
for k in range(NR):
    r = r0 + k
    put(H, f"A{r}", f"=Returns!A{r}", color=GREEN, fmt=DATE)
    for j in range(n):
        src = L(2 + j)
        put(H, f"{L(2 + j)}{r}", f'=IF(Returns!$O{r}=1,"",Returns!{src}{r})', color=GREEN, fmt=PCT)
        put(H, f"{L(11 + j)}{r}", f'=IF(Returns!$O{r}=1,Returns!{src}{r},"")', color=GREEN, fmt=PCT)
    put(H, f"T{r}", f'=IF(Returns!$O{r}=1,"",Returns!K{r})', color=GREEN, fmt=PCT)
widths(H, {"A": 12, **{L(j): 13 for j in range(2, 21)}}); H.freeze_panes = "B4"

# ---------------------------------------------------------------- Risk_Metrics
title(M, "Risk metrics: equal-weight portfolio", "VaR and Expected Shortfall use the historical method (percentile of actual daily returns).")
K_ = rng("K"); Kh = rng("T", "Returns_Helper")
def sec(r, text): put(M, f"B{r}", text, bold=True, fill=SFILL); [put(M, f"{c}{r}", None, fill=SFILL) for c in "CD"]
sec(3, "1. Portfolio risk, full period")
items = [(5, "Daily volatility (standard deviation)", f"=STDEV({K_})", PCT, "STDEV is the sample standard deviation."),
 (6, "Annualised volatility", f"=C5*SQRT({DAYS})", PCT1, ""),
 (7, "VaR 95% (historical)", f"=PERCENTILE({K_},{TAIL})", PCT, "Loss exceeded only on the worst 5% of days."),
 (8, "Expected Shortfall 95%", f'=AVERAGEIF({K_},"<="&C7)', PCT, "Average loss on the days that exceed the VaR."),
 (9, "VaR 95% (R$)", f"=C7*{VAL}", BRL, ""), (10, "Expected Shortfall 95% (R$)", f"=C8*{VAL}", BRL, ""),
 (11, "Number of daily returns", f"=COUNT({K_})", "0", ""), (12, "Days in the tail (return <= VaR)", f'=COUNTIF({K_},"<="&C7)', "0", "")]
for r, lab, f, fmt, com in items: put(M, f"B{r}", lab); put(M, f"C{r}", f, fmt=fmt, color=GREEN if "Inputs" in f or "Returns" in f else BLACK); put(M, f"D{r}", com, color="595959")
sec(14, "2. Weight of the crash window (Feb-Apr 2020)")
items = [(16, "Days inside the crash window", f"=SUM({rng('O')})", "0", ""), (17, "Share of all days", "=C16/C11", PCT1, ""),
 (18, "Tail days that fall inside the crash window", f'=COUNTIFS({K_},"<="&C7,{rng("O")},1)', "0", ""),
 (19, "Share of tail days inside the crash window", "=C18/C12", PCT1, "A small share of days concentrates most of the worst days."),
 (20, "VaR 95% excluding the crash window", f"=PERCENTILE({Kh},{TAIL})", PCT, ""),
 (21, "Expected Shortfall 95% excluding the crash window", f'=AVERAGEIF({Kh},"<="&C20)', PCT, ""),
 (22, "Days used excluding the crash window", f"=COUNT({Kh})", "0", ""),
 (23, "Change in Expected Shortfall without the crash", "=C21/C8-1", PCT1, "")]
for r, lab, f, fmt, com in items: put(M, f"B{r}", lab); put(M, f"C{r}", f, fmt=fmt, color=GREEN if ("Returns" in f or "Inputs" in f) else BLACK); put(M, f"D{r}", com, color="595959")
sec(25, "3. Drawdown of the equal-weight portfolio")
items = [(27, "Maximum drawdown", f"=MIN({rng('R')})", PCT1, ""),
 (28, "Trough date", f"=INDEX({rng('A')},E28)", DATE, ""),
 (29, "Index at trough", f"=INDEX({rng('P')},MATCH(C28,{rng('A')},0))", NUM, ""),
 (30, "Peak index before the trough", f"=INDEX({rng('Q')},MATCH(C28,{rng('A')},0))", NUM, ""),
 (31, "Peak date", f"=INDEX({rng('A')},MATCH(C30,{rng('P')},0))", DATE, ""),
 (32, "Date the previous peak was recovered", f"=INDEX({rng('A')},MATCH(1,{rng('T')},0))", DATE, "")]
for r, lab, f, fmt, com in items: put(M, f"B{r}", lab); put(M, f"C{r}", f, fmt=fmt, color=GREEN); put(M, f"D{r}", com, color="595959")
put(M, "E28", f"=MATCH(C27,{rng('R')},0)", fmt="0"); put(M, "F28", "<- position of the trough in the Returns table (helper)", color="595959")
sec(34, "4. Risk by stock (daily returns)")
header(M, 35, 2, ["Stock", "Weight (equal)", "Daily volatility", "Annualised volatility", "VaR 95%", "Expected Shortfall 95%"], height=32)
for j, nm in enumerate(names):
    r = 36 + j; col = L(2 + j); rg = rng(col)
    put(M, f"B{r}", nm); put(M, f"C{r}", f"=Optimization!{L(3 + j)}7", color=GREEN, fmt=PCT1)
    put(M, f"D{r}", f"=STDEV({rg})", color=GREEN, fmt=PCT); put(M, f"E{r}", f"=D{r}*SQRT({DAYS})", color=GREEN, fmt=PCT1)
    put(M, f"F{r}", f"=PERCENTILE({rg},{TAIL})", color=GREEN, fmt=PCT); put(M, f"G{r}", f'=AVERAGEIF({rg},"<="&F{r})', color=GREEN, fmt=PCT)
put(M, "B45", "Average of the 9 stocks", bold=True); put(M, "D45", "=AVERAGE(D36:D44)", fmt=PCT, bold=True)
put(M, "B46", "Equal-weight portfolio", bold=True); put(M, "D46", "=C5", fmt=PCT, bold=True)
put(M, "B47", "Diversification gain (portfolio vs. average stock)"); put(M, "D47", "=D46/D45-1", fmt=PCT1)
sec(49, "5. Sensitivity: excluding the Lojas Americanas series-break day")
put(M, "B51", "Lojas Americanas daily volatility, excluding the break day"); put(M, "C51", f"=STDEV({rng('S')})", color=GREEN, fmt=PCT)
put(M, "B52", "Portfolio VaR 95%, excluding the break day"); put(M, "C52", f"=PERCENTILE({rng('U')},{TAIL})", color=GREEN, fmt=PCT)
put(M, "B53", "Portfolio Expected Shortfall 95%, excluding the break day"); put(M, "C53", f'=AVERAGEIF({rng("U")},"<="&C52)', color=GREEN, fmt=PCT)
widths(M, {"A": 3, "B": 58, "C": 18, "D": 18, "E": 18, "F": 14, "G": 18})

# ---------------------------------------------------------------- Correlation
title(C, "Correlation matrices (Pearson, daily returns)", "Excluding / crash-only matrices use helper series; Excel ignores the blank cells pair-wise.")
def corr_block(top, label, src_sheet, cols, ttl):
    put(C, f"B{top-1}", ttl, bold=True, fill=SFILL)
    header(C, top, 3, names, height=34)
    for i, nm in enumerate(names):
        r = top + 1 + i; put(C, f"B{r}", nm, bold=True)
        for j in range(n):
            a, b = L(cols[i]), L(cols[j])
            put(C, f"{L(3 + j)}{r}", f"=CORREL({rng(a, src_sheet)},{rng(b, src_sheet)})", color=GREEN, fmt="0.00")
    c1, c2, rr = "C", "K", (top + 1, top + n)
    C.conditional_formatting.add(f"C{rr[0]}:K{rr[1]}", ColorScaleRule(start_type="num", start_value=0, start_color="F3F7FD", mid_type="num", mid_value=0.35, mid_color="9EC1EE", end_type="num", end_value=0.7, end_color="2A78D6"))
    put(C, f"B{top + n + 1}", "Average pair correlation", bold=True)
    put(C, f"C{top + n + 1}", f"=(SUM(C{rr[0]}:K{rr[1]})-{n})/({n}*({n}-1))", bold=True, fmt="0.00")
corr_block(4, "full", "Returns", list(range(2, 11)), "1. Full period")
corr_block(18, "excl", "Returns_Helper", list(range(2, 11)), "2. Excluding the crash window (Feb-Apr 2020)")
corr_block(32, "crash", "Returns_Helper", list(range(11, 20)), "3. Crash window only (Feb-Apr 2020)")
widths(C, {"A": 3, "B": 28, **{L(j): 13 for j in range(3, 12)}})

# ---------------------------------------------------------------- Optimization
title(O, "Portfolio optimisation (minimum variance)", "Weights in blue are inputs (optimiser output). Every metric next to them is a live formula.")
header(O, 6, 2, ["Scenario"] + names + ["Sum of weights", "Portfolio variance", "Daily volatility", "Volatility vs. equal weights", "VaR 95%", "Expected Shortfall 95%", "VaR 95% (R$)", "ES 95% (R$)", "Largest weight"], height=48)
scen = [(7, "Equal weights", None, "K"), (8, "Minimum variance (long only)", W_MV, "L"),
        (9, "Minimum variance, 30% cap per stock", W_CAP, "M"), (10, "Minimum variance fitted only to the training period", W_TRAIN, "N")]
for r, lab, w, rc in scen:
    put(O, f"B{r}", lab, bold=True)
    for j in range(n):
        if w is None: put(O, f"{L(3 + j)}{r}", f"=1/{n}", fmt=PCT1)
        else: put(O, f"{L(3 + j)}{r}", float(w[j]), color=BLUE, fmt=PCT1, fill=YFILL if r in (8, 9) else None)
    put(O, f"L{r}", f"=SUM(C{r}:K{r})", fmt="0.0%")
    put(O, f"M{r}", f"=SUMPRODUCT(MMULT(C{r}:K{r},$C$15:$K$23),C{r}:K{r})", fmt="0.000000")
    put(O, f"N{r}", f"=SQRT(M{r})", fmt=PCT); put(O, f"O{r}", f"=N{r}/$N$7-1", fmt=PCT1)
    put(O, f"P{r}", f"=PERCENTILE({rng(rc)},{TAIL})", color=GREEN, fmt=PCT)
    put(O, f"Q{r}", f'=AVERAGEIF({rng(rc)},"<="&P{r})', color=GREEN, fmt=PCT)
    put(O, f"R{r}", f"=P{r}*{VAL}", color=GREEN, fmt=BRL); put(O, f"S{r}", f"=Q{r}*{VAL}", color=GREEN, fmt=BRL)
    put(O, f"T{r}", f"=MAX(C{r}:K{r})", fmt=PCT1)
put(O, "B11", "Reference: minimum variance fitted without the crash window", bold=True)
for j in range(n): put(O, f"{L(3 + j)}11", float(W_EXC[j]), color=BLUE, fmt=PCT1)
put(O, "L11", "=SUM(C11:K11)", fmt="0.0%")
put(O, "B12", "Check: the 30% cap scenario respects the cap"); put(O, "C12", f'=IF(T9<={CAP}+0.000001,"OK","Check")', color=GREEN)
put(O, "B14", "Covariance matrix of daily returns (sample)", bold=True, fill=SFILL); header(O, 14, 3, names, height=34)
for i, nm in enumerate(names):
    r = 15 + i; put(O, f"B{r}", nm, bold=True)
    for j in range(n):
        put(O, f"{L(3 + j)}{r}", f"=_xlfn.COVARIANCE.S({rng(L(2 + i))},{rng(L(2 + j))})", color=GREEN, fmt="0.000000")
put(O, "B26", "How to reproduce the optimal weights with Excel Solver", bold=True, fill=SFILL)
for k, t in enumerate([
 "1. Data > Solver. Set Objective: cell M8 (portfolio variance of the 'Minimum variance' row). To: Min.",
 "2. By Changing Variable Cells: C8:K8.",
 "3. Subject to the Constraints: L8 = 1 (weights sum to 100%) and C8:K8 >= 0 (no short selling). Tick 'Make Unconstrained Variables Non-Negative'.",
 "4. Solving method: GRG Nonlinear. For the capped scenario use row 9 and add the constraint C9:K9 <= Inputs!C11.",
 "5. The blue weights above were obtained with a quadratic optimiser in Python (code/build_workbook.py), which solves the same problem."], start=27):
    put(O, f"B{k}", t)
put(O, "B33", "Out-of-sample check: weights fitted on the training period, tested afterwards", bold=True, fill=SFILL)
put(O, "B34", "Last training row (position of the training end date)"); put(O, "C34", f"=MATCH({TRAIN},{rng('A')},1)", color=GREEN, fmt="0")
header(O, 36, 2, ["Portfolio", "Training-period volatility", "Test-period volatility", "Test-period VaR 95%"], height=34)
for r, lab, col in ((37, "Equal weights", "K"), (38, "Minimum variance fitted to the training period", "N")):
    rg = rng(col); tr = f"INDEX({rg},1):INDEX({rg},$C$34)"; te = f"INDEX({rg},$C$34+1):INDEX({rg},COUNT({rng('A')}))"
    put(O, f"B{r}", lab); put(O, f"C{r}", f"=STDEV({tr})", color=GREEN, fmt=PCT); put(O, f"D{r}", f"=STDEV({te})", color=GREEN, fmt=PCT)
    put(O, f"E{r}", f"=PERCENTILE({te},{TAIL})", color=GREEN, fmt=PCT)
put(O, "B39", "Test-period volatility vs. equal weights"); put(O, "D39", "=D38/D37-1", fmt=PCT1)
widths(O, {"A": 3, "B": 50, **{L(j): 12 for j in range(3, 12)}, "L": 12, "M": 14, "N": 12, "O": 14, "P": 11, "Q": 13, "R": 14, "S": 14, "T": 11})

# ---------------------------------------------------------------- Backtest
title(B, "Backtest of the VaR (course exercise, with a Kupiec test)", "VaR estimated on period 1 is compared with the actual returns of period 2.")
put(B, "B4", "Window length (days)"); put(B, "C4", f"={WIN}", color=GREEN, fmt="0")
put(B, "B5", "Last day of period 1"); put(B, "C5", f"={TRAIN}", color=GREEN, fmt=DATE)
put(B, "B6", "Position of that day in the return series"); put(B, "C6", f"=MATCH(C5,{rng('A')},1)", color=GREEN, fmt="0")
put(B, "B7", "Total number of daily returns"); put(B, "C7", f"=COUNT({rng('A')})", color=GREEN, fmt="0")
K = rng("K")
p1 = f"INDEX({K},C6-C4+1):INDEX({K},C6)"; p2 = f"INDEX({K},C7-C4+1):INDEX({K},C7)"
rowsb = [(9, "Period 1: first day", f"=INDEX({rng('A')},C6-C4+1)", DATE), (10, "Period 1: last day", f"=INDEX({rng('A')},C6)", DATE),
 (11, "Period 2: first day", f"=INDEX({rng('A')},C7-C4+1)", DATE), (12, "Period 2: last day", f"=INDEX({rng('A')},C7)", DATE),
 (14, "VaR 95% estimated on period 1", f"=PERCENTILE({p1},{TAIL})", PCT), (15, "5th percentile actually observed in period 2", f"=PERCENTILE({p2},{TAIL})", PCT),
 (16, "VaR 95% in R$ (period 1)", f"=C14*{VAL}", BRL),
 (18, "Days in period 2 with a loss beyond the period-1 VaR (violations)", f'=COUNTIF({p2},"<"&C14)', "0"),
 (19, "Expected number of violations", f"=C4*{TAIL}", "0.0"), (20, "Observed violation rate", "=C18/C4", PCT1),
 (21, "Expected violation rate", f"={TAIL}", PCT1),
 (23, "Kupiec likelihood-ratio statistic", f"=IF(C18=0,-2*C4*LN(1-{TAIL}),-2*((C4-C18)*LN(1-{TAIL})+C18*LN({TAIL}))+2*((C4-C18)*LN(1-C18/C4)+C18*LN(C18/C4)))", "0.00"),
 (24, "p-value (chi-square, 1 degree of freedom)", "=CHIDIST(C23,1)", "0.0000"),
 (25, "Conclusion", '=IF(C24<0.05,"Reject: observed violations differ from the expected rate","Do not reject: consistent with the expected rate")', None)]
for r, lab, f, fmt in rowsb: put(B, f"B{r}", lab); put(B, f"C{r}", f, color=GREEN if ("Returns" in f or "Inputs" in f or "INDEX" in f) else BLACK, fmt=fmt)
put(B, "B27", "Reading: the VaR estimated on a window that contains the crash turned out too conservative for the following year (far fewer violations than the 5% expected).", color="595959", italic=True)
widths(B, {"A": 3, "B": 66, "C": 22})

# ---------------------------------------------------------------- Summary
title(S, "Portfolio risk analysis: VaR, Expected Shortfall and optimisation", "9 Brazilian stocks, equal weights, daily data from 2019-08-30 to 2021-08-27. All figures below are live links to the calculation sheets.")
header(S, 4, 2, ["Metric", "Value", "Where it comes from"])
summ = [("Portfolio value (R$)", f"={VAL}", BRL, "Inputs"), ("Daily returns used", "=Risk_Metrics!C11", "0", "Risk_Metrics"),
 ("Daily volatility, equal-weight portfolio", "=Risk_Metrics!C5", PCT, "Risk_Metrics"), ("VaR 95% (historical)", "=Risk_Metrics!C7", PCT, "Risk_Metrics"),
 ("VaR 95% (R$)", "=Risk_Metrics!C9", BRL, "Risk_Metrics"), ("Expected Shortfall 95%", "=Risk_Metrics!C8", PCT, "Risk_Metrics"),
 ("Expected Shortfall 95% (R$)", "=Risk_Metrics!C10", BRL, "Risk_Metrics"), ("VaR 95% excluding the crash window", "=Risk_Metrics!C20", PCT, "Risk_Metrics"),
 ("Expected Shortfall 95% excluding the crash window", "=Risk_Metrics!C21", PCT, "Risk_Metrics"),
 ("Share of days in the crash window", "=Risk_Metrics!C17", PCT1, "Risk_Metrics"), ("Share of the worst 5% days inside the crash window", "=Risk_Metrics!C19", PCT1, "Risk_Metrics"),
 ("Maximum drawdown (peak to trough)", "=Risk_Metrics!C27", PCT1, "Risk_Metrics"), ("Average volatility of the 9 stocks", "=Risk_Metrics!D45", PCT, "Risk_Metrics"),
 ("Average pair correlation: full period", "=Correlation!C14", "0.00", "Correlation"), ("Average pair correlation: excluding crash", "=Correlation!C28", "0.00", "Correlation"),
 ("Average pair correlation: crash window only", "=Correlation!C42", "0.00", "Correlation"),
 ("Daily volatility, minimum-variance portfolio", "=Optimization!N8", PCT, "Optimization"), ("Volatility vs. equal weights", "=Optimization!O8", PCT1, "Optimization"),
 ("Largest weight in the minimum-variance portfolio", "=Optimization!T8", PCT1, "Optimization"), ("Daily volatility, 30% cap portfolio", "=Optimization!N9", PCT, "Optimization"),
 ("Out-of-sample volatility vs. equal weights", "=Optimization!D39", PCT1, "Optimization"),
 ("Backtest: violations in period 2", "=Backtest!C18", "0", "Backtest"), ("Backtest: observed violation rate (5% expected)", "=Backtest!C20", PCT1, "Backtest"),
 ("Backtest: Kupiec p-value", "=Backtest!C24", "0.0000", "Backtest")]
for i, (lab, f, fmt, src) in enumerate(summ, start=5):
    put(S, f"B{i}", lab); put(S, f"C{i}", f, color=GREEN, fmt=fmt, align="right"); put(S, f"D{i}", src, color="595959")
r = 5 + len(summ) + 1
put(S, f"B{r}", "Sheet guide", bold=True, fill=SFILL); put(S, f"C{r}", None, fill=SFILL); put(S, f"D{r}", None, fill=SFILL)
for k, (a, b_) in enumerate([("Inputs", "Parameters you can change (portfolio value, confidence level, crash window, ...)."),
 ("Prices", "Daily closing prices (hardcoded inputs)."), ("Returns", "Daily returns, portfolio series, index, drawdown."),
 ("Returns_Helper", "Series excluding / inside the crash window (support for statistics)."), ("Risk_Metrics", "Volatility, VaR, Expected Shortfall, crash effect, drawdown, risk by stock."),
 ("Correlation", "Correlation matrices: full period, excluding the crash, crash only."), ("Optimization", "Minimum-variance weights, covariance matrix, Solver steps, out-of-sample check."),
 ("Backtest", "VaR backtest with Kupiec test.")], start=r + 1):
    put(S, f"B{k}", a, bold=True); put(S, f"C{k}", b_)
put(S, f"B{r + 10}", "Educational analysis based on two years of historical data. It is not investment advice.", italic=True, color="595959")
widths(S, {"A": 3, "B": 54, "C": 20, "D": 24})

for ws in wb.worksheets: ws.sheet_view.showGridLines = False
S.sheet_properties.tabColor = "1F3864"; I.sheet_properties.tabColor = "FFC000"
out = ROOT / "spreadsheets" / "var_portfolio_analysis.xlsx"; wb.save(out); print("saved", out)
