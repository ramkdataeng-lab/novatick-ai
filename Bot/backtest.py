"""
NovaTick - 5-Day Strategy Backtest
======================================
Replays the exact bot v2 strategy on the last 5 trading days
using hourly OHLCV data from yfinance.

Outputs:
  - Every simulated trade (entry, exit, reason, P&L)
  - Win rate, total return, best/worst trade
  - Per-sector breakdown
  - Final equity curve
  - Saves full report to backtest_report.txt
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# --- Config (must match bot.py) -----------------------------------------------
STARTING_CAPITAL    = 100_000.00
POSITION_SIZE_PCT   = 0.03       # 3% of equity per trade
MAX_POSITIONS       = 15
MAX_PER_SECTOR      = 4
STOP_LOSS_PCT       = -0.05      # -5%
TAKE_PROFIT_PCT     =  0.08      # +8%
RSI_OVERSOLD        = 32
RSI_OVERBOUGHT      = 68
MARKET_REGIME_RSI   = 45         # SPY RSI below this = no new buys
OPEN_BUFFER_BARS    = 1          # skip first hourly bar (= first 60 min)
ATR_MULTIPLIER      = 2.5        # Trailing stop volatility multiplier
LOOKBACK_DAYS       = 5

WATCHLIST = [
    "AAPL","MSFT","NVDA","AMD","INTC","TSLA","META","GOOGL",
    "AMZN","AVGO","ORCL","CRM","ADBE","QCOM","TXN",
    "JPM","BAC","WFC","GS","MS","BRK-B","V","MA","PYPL","AXP",
    "JNJ","UNH","PFE","MRK","ABBV","LLY","TMO",
    "WMT","COST","HD","MCD","NKE","SBUX","KO","PEP",
    "XOM","CVX","COP","SLB",
    "BA","CAT","GE","UPS","SPY","QQQ",
]

SECTORS = {
    "Tech":        ["AAPL","MSFT","NVDA","AMD","INTC","TSLA","META","GOOGL","AMZN","AVGO","ORCL","CRM","ADBE","QCOM","TXN"],
    "Financials":  ["JPM","BAC","WFC","GS","MS","BRK-B","V","MA","PYPL","AXP"],
    "Healthcare":  ["JNJ","UNH","PFE","MRK","ABBV","LLY","TMO"],
    "Consumer":    ["WMT","COST","HD","MCD","NKE","SBUX","KO","PEP"],
    "Energy":      ["XOM","CVX","COP","SLB"],
    "Industrial":  ["BA","CAT","GE","UPS","SPY","QQQ"],
}

def get_sector(sym):
    for s, members in SECTORS.items():
        if sym in members:
            return s
    return "Other"

# --- Indicator helpers --------------------------------------------------------
def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def compute_macd(series):
    ema12  = series.ewm(span=12, adjust=False).mean()
    ema26  = series.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9,  adjust=False).mean()
    return macd, signal

def compute_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_cp = np.abs(df['High'] - df['Close'].shift())
    low_cp = np.abs(df['Low'] - df['Close'].shift())
    df_tr = pd.concat([high_low, high_cp, low_cp], axis=1)
    true_range = df_tr.max(axis=1)
    atr = true_range.rolling(period).mean()
    return atr

# --- Fetch data ---------------------------------------------------------------
print("=" * 65)
print("  NovaTick - 5-Day Backtest Engine")
print(f"  Simulation date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"  Capital: ${STARTING_CAPITAL:,.0f}  |  Stocks: {len(WATCHLIST)}")
print("=" * 65)
print("\nFetching 2 months of hourly data for all 50 stocks...")

all_data = {}
failed   = []
for sym in WATCHLIST + ["SPY"]:
    try:
        df = yf.download(sym, period="2mo", interval="1h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 30:
            failed.append(sym)
            continue
        df.index = pd.to_datetime(df.index)
        df["RSI"]   = compute_rsi(df["Close"])
        macd, sig   = compute_macd(df["Close"])
        df["MACD"]  = macd
        df["MSIG"]  = sig
        df["MA20"]  = df["Close"].rolling(20).mean()
        df["MA50"]  = df["Close"].rolling(50).mean()
        df["ATR"]   = compute_atr(df)
        all_data[sym] = df
    except Exception as e:
        failed.append(sym)

print(f"Loaded {len(all_data)} / {len(WATCHLIST)+1} symbols  |  Failed: {failed or 'none'}")

# --- Get last 5 trading days --------------------------------------------------
spy_df    = all_data.get("SPY", pd.DataFrame())
all_bars  = sorted(spy_df.index.unique()) if not spy_df.empty else []
trade_days = sorted(set(b.date() for b in all_bars))[-LOOKBACK_DAYS:]
if trade_days:
    print(f"Backtest window: {trade_days[0]} -> {trade_days[-1]}\n")
else:
    print("Error: No trading data found in the window.")
    exit(1)

# --- Simulation state ---------------------------------------------------------
equity    = STARTING_CAPITAL
cash      = STARTING_CAPITAL
positions = {}    # sym -> {qty, entry_price, entry_time, sector, max_price, trailing_stop}
trades    = []    # completed round-trips
equity_curve = [{"date": str(trade_days[0]), "equity": equity}]

def sector_count(sector):
    return sum(1 for p in positions.values() if p["sector"] == sector)

# --- Bar-by-bar replay --------------------------------------------------------
for day in trade_days:
    # All hourly bars for this day, sorted
    day_bars = [b for b in all_bars if b.date() == day]
    day_bars.sort()

    for bar_idx, bar_ts in enumerate(day_bars):
        # Skip first bar (open buffer)
        if bar_idx < OPEN_BUFFER_BARS:
            continue

        # Market regime: SPY RSI at this bar
        if "SPY" in all_data:
            spy_row = all_data["SPY"].loc[all_data["SPY"].index == bar_ts]
            spy_rsi = float(spy_row["RSI"].iloc[0]) if not spy_row.empty and not pd.isna(spy_row["RSI"].iloc[0]) else 50.0
        else:
            spy_rsi = 50.0
        bear_mode = spy_rsi < MARKET_REGIME_RSI

        # Mark-to-market equity
        mtm = cash
        for sym, pos in positions.items():
            if sym in all_data:
                row = all_data[sym].loc[all_data[sym].index <= bar_ts].tail(1)
                if not row.empty:
                    mtm += pos["qty"] * float(row["Close"].iloc[0])
        equity = mtm

        for sym in list(WATCHLIST):
            if sym not in all_data:
                continue
            df  = all_data[sym]
            row = df.loc[df.index <= bar_ts].tail(1)
            if row.empty:
                continue

            price      = float(row["Close"].iloc[0])
            rsi        = float(row["RSI"].iloc[0])  if not pd.isna(row["RSI"].iloc[0])  else 50.0
            macd_val   = float(row["MACD"].iloc[0]) if not pd.isna(row["MACD"].iloc[0]) else 0.0
            msig_val   = float(row["MSIG"].iloc[0]) if not pd.isna(row["MSIG"].iloc[0]) else 0.0
            ma20       = float(row["MA20"].iloc[0]) if not pd.isna(row["MA20"].iloc[0]) else price
            macd_bull  = macd_val > msig_val

            # --- Exit logic (check existing positions first) -------------------
            if sym in positions:
                pos    = positions[sym]
                entry  = pos["entry_price"]
                qty    = pos["qty"]
                pl_pct = (price - entry) / entry
                reason = None

                # Update trailing stop if price moved up
                if price > pos["max_price"]:
                    pos["max_price"] = price
                    atr_val = float(row["ATR"].iloc[0]) if not pd.isna(row["ATR"].iloc[0]) else (price * 0.02)
                    new_stop = price - (atr_val * ATR_MULTIPLIER)
                    pos["trailing_stop"] = max(pos["trailing_stop"], new_stop)

                if price <= pos["trailing_stop"]:
                    reason = f"TRAILING-STOP @ {pos['trailing_stop']:.2f}"
                elif pl_pct <= STOP_LOSS_PCT:
                    reason = f"STOP-LOSS {pl_pct*100:+.1f}%"
                elif pl_pct >= TAKE_PROFIT_PCT:
                    reason = f"TAKE-PROFIT {pl_pct*100:+.1f}%"
                elif rsi > RSI_OVERBOUGHT and not macd_bull:
                    reason = f"RSI={rsi:.1f} overbought+bear MACD"

                if reason:
                    proceeds = qty * price
                    pl_usd   = proceeds - (qty * entry)
                    cash    += proceeds
                    trades.append({
                        "symbol":      sym,
                        "sector":      pos["sector"],
                        "entry_time":  pos["entry_time"],
                        "exit_time":   bar_ts,
                        "entry_price": entry,
                        "exit_price":  price,
                        "qty":         qty,
                        "pl_usd":      pl_usd,
                        "pl_pct":      pl_pct * 100,
                        "exit_reason": reason,
                    })
                    del positions[sym]
                continue

            # --- Entry logic ---------------------------------------------------
            if (
                len(positions) < MAX_POSITIONS
                and not bear_mode
                and sector_count(get_sector(sym)) < MAX_PER_SECTOR
                and rsi < RSI_OVERSOLD
                and macd_bull
                and price < ma20
            ):
                budget = equity * POSITION_SIZE_PCT
                qty    = int(budget // price)
                if qty >= 1 and cash >= qty * price:
                    cost = qty * price
                    cash -= cost
                    atr_val = float(row["ATR"].iloc[0]) if not pd.isna(row["ATR"].iloc[0]) else (price * 0.02)
                    positions[sym] = {
                        "qty":         qty,
                        "entry_price": price,
                        "entry_time":  bar_ts,
                        "sector":      get_sector(sym),
                        "max_price":   price,
                        "trailing_stop": price - (atr_val * ATR_MULTIPLIER)
                    }

    # End of day - record equity
    equity_curve.append({"date": str(day), "equity": round(equity, 2)})

# --- Close all remaining positions at last price ------------------------------
for sym, pos in positions.items():
    if sym not in all_data:
        continue
    last_price = float(all_data[sym]["Close"].iloc[-1])
    qty        = pos["qty"]
    pl_usd     = (last_price - pos["entry_price"]) * qty
    pl_pct     = (last_price - pos["entry_price"]) / pos["entry_price"] * 100
    cash      += qty * last_price
    trades.append({
        "symbol":      sym,
        "sector":      pos["sector"],
        "entry_time":  pos["entry_time"],
        "exit_time":   "End of Backtest",
        "entry_price": pos["entry_price"],
        "exit_price":  last_price,
        "qty":         qty,
        "pl_usd":      pl_usd,
        "pl_pct":      pl_pct,
        "exit_reason": "End of period",
    })

final_equity = cash

# --- Results ------------------------------------------------------------------
lines = []
def p(s=""):
    print(s)
    lines.append(s)

p()
p("=" * 65)
p("  BACKTEST RESULTS - Last 5 Trading Days")
p(f"  {trade_days[0]}  ->  {trade_days[-1]}")
p("=" * 65)
p(f"  Starting Capital  : ${STARTING_CAPITAL:>12,.2f}")
p(f"  Final Equity      : ${final_equity:>12,.2f}")
total_pnl = final_equity - STARTING_CAPITAL
total_pct = total_pnl / STARTING_CAPITAL * 100
p(f"  Total P&L         : ${total_pnl:>+12,.2f}  ({total_pct:+.2f}%)")
p(f"  Total Trades      : {len(trades)}")

if trades:
    winners = [t for t in trades if t["pl_usd"] > 0]
    losers  = [t for t in trades if t["pl_usd"] <= 0]
    win_rate = len(winners) / len(trades) * 100
    p(f"  Win Rate          : {win_rate:.1f}%  ({len(winners)}W / {len(losers)}L)")

    best  = max(trades, key=lambda t: t["pl_usd"])
    worst = min(trades, key=lambda t: t["pl_usd"])
    p(f"  Best Trade        : {best['symbol']}  ${best['pl_usd']:>+,.2f}  ({best['pl_pct']:+.1f}%)")
    p(f"  Worst Trade       : {worst['symbol']}  ${worst['pl_usd']:>+,.2f}  ({worst['pl_pct']:+.1f}%)")

    avg_win  = np.mean([t["pl_usd"] for t in winners]) if winners else 0
    avg_loss = np.mean([t["pl_usd"] for t in losers])  if losers  else 0
    p(f"  Avg Win           : ${avg_win:>+,.2f}")
    p(f"  Avg Loss          : ${avg_loss:>+,.2f}")
    p(f"  Profit Factor     : {abs(avg_win/avg_loss):.2f}x" if avg_loss != 0 else "  Profit Factor     : N/A")

p()
p("-" * 65)
p("  EQUITY CURVE")
p("-" * 65)
for pt in equity_curve:
    bar_len = int((pt["equity"] - STARTING_CAPITAL + 1000) / 200)
    bar_len = max(0, min(bar_len, 40))
    arrow = "UP" if pt["equity"] >= STARTING_CAPITAL else "DOWN"
    p(f"  {pt['date']}   ${pt['equity']:>12,.2f}  {arrow}  {'#' * bar_len}")

if trades:
    p()
    p("-" * 65)
    p("  ALL TRADES")
    p("-" * 65)
    p(f"  {'Symbol':<7} {'Sector':<12} {'Entry $':>8} {'Exit $':>8} {'Qty':>4} {'P&L $':>9} {'P&L%':>7}  Exit Reason")
    p("  " + "-" * 80)
    for t in sorted(trades, key=lambda x: x["pl_usd"], reverse=True):
        flag = "WIN " if t["pl_usd"] > 0 else "LOSS"
        p(
            f"  {t['symbol']:<7} {t['sector']:<12} "
            f"${t['entry_price']:>7.2f} ${t['exit_price']:>7.2f} "
            f"{t['qty']:>4}  ${t['pl_usd']:>+8.2f} {t['pl_pct']:>+6.1f}%  "
            f"[{flag}] {t['exit_reason']}"
        )

    p()
    p("-" * 65)
    p("  SECTOR BREAKDOWN")
    p("-" * 65)
    sector_pnl = {}
    for t in trades:
        sector_pnl.setdefault(t["sector"], []).append(t["pl_usd"])
    for sec, pnls in sorted(sector_pnl.items(), key=lambda x: -sum(x[1])):
        tot  = sum(pnls)
        wins = sum(1 for x in pnls if x > 0)
        p(f"  {sec:<12}  {len(pnls):>2} trades  W/L: {wins}/{len(pnls)-wins}  P&L: ${tot:>+9,.2f}")

p()
p("=" * 65)
p(f"  Strategy: RSI({RSI_OVERSOLD}/{RSI_OVERBOUGHT}) + MACD + SL{STOP_LOSS_PCT*100:.0f}% + TP+{TAKE_PROFIT_PCT*100:.0f}%")
p(f"  Regime filter: SPY RSI < {MARKET_REGIME_RSI} = no buys")
p(f"  Max positions: {MAX_POSITIONS}  |  Max/sector: {MAX_PER_SECTOR}")
p("=" * 65)

# Save report
with open("backtest_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"\n  Full report saved to backtest_report.txt")
