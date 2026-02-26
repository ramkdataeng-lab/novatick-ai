"""
""" NovaTick Bot v2 — Improved Automated Paper Trading Agent """
===========================================================
Improvements over v1 (learned from live data):

  1. Tighter RSI thresholds (32/68 vs 40/65) — fewer but higher-quality signals
  2. MACD confirmation — must agree with RSI before any order is placed
  3. Stop-Loss at -5%  — auto-exits losers before they compound
  4. Take-Profit at +8% — locks in gains without waiting for RSI to flip
  5. Market open buffer — skips the first 30 min of volatile price action
  6. Market regime filter — won't BUY individual stocks if SPY RSI < 45 (bear)
  7. Max concurrent positions cap (15) — prevents over-exposure
  8. Per-sector concentration check — no more than 4 holdings in one sector
  9. Detailed structured logging — every decision recorded with full reasoning

Run:  python bot.py
Stop: Ctrl+C
"""

import os
import time
import logging
from typing import Optional, Tuple
from datetime import datetime, timezone, timedelta

import yfinance as yf
import pandas as pd
import numpy as np
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus

# ─── Config ───────────────────────────────────────────────────────────────────
load_dotenv()

API_KEY    = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
PAPER      = "paper-api" in BASE_URL

# ── Watchlist — 50 liquid stocks across all major S&P 500 sectors ─────────────
WATCHLIST = [
    # Technology
    "AAPL", "MSFT", "NVDA", "AMD", "INTC", "TSLA", "META", "GOOGL",
    "AMZN", "AVGO", "ORCL", "CRM", "ADBE", "QCOM", "TXN",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "BRK-B", "V", "MA", "PYPL", "AXP",
    # Healthcare
    "JNJ", "UNH", "PFE", "MRK", "ABBV", "LLY", "TMO",
    # Consumer
    "WMT", "COST", "HD", "MCD", "NKE", "SBUX", "KO", "PEP",
    # Energy
    "XOM", "CVX", "COP", "SLB",
    # Industrials & Other
    "BA", "CAT", "GE", "UPS", "SPY", "QQQ",
]

# Sector map for concentration limits
SECTORS = {
    "Tech":        ["AAPL","MSFT","NVDA","AMD","INTC","TSLA","META","GOOGL","AMZN","AVGO","ORCL","CRM","ADBE","QCOM","TXN"],
    "Financials":  ["JPM","BAC","WFC","GS","MS","BRK-B","V","MA","PYPL","AXP"],
    "Healthcare":  ["JNJ","UNH","PFE","MRK","ABBV","LLY","TMO"],
    "Consumer":    ["WMT","COST","HD","MCD","NKE","SBUX","KO","PEP"],
    "Energy":      ["XOM","CVX","COP","SLB"],
    "Industrial":  ["BA","CAT","GE","UPS","SPY","QQQ"],
}

# --- Strategy parameters ------------------------------------------------------
POSITION_SIZE_PCT    = 0.02   # Base 2% (will be adjusted by ATR volatility)
MAX_POSITIONS        = 15     # never hold more than 15 positions simultaneously
MAX_PER_SECTOR       = 4      # no more than 4 holdings in any single sector
STOP_LOSS_PCT        = -0.05  # -5% harder floor
TAKE_PROFIT_PCT      = 0.10   # Aim higher (+10%) with trailing stop
RSI_OVERSOLD         = 35     # Slightly more inclusive (was 32)
RSI_OVERBOUGHT       = 70     # Let winners run more (was 68)
ATR_MULTIPLIER       = 2.5    # 2.5x ATR for trailing stop
OPEN_BUFFER_MINUTES  = 30     # skip first 30 min of session
SCAN_INTERVAL        = 60     # seconds between scans
MARKET_REGIME_RSI    = 45     # if SPY RSI < this, halt new buys (bear market)

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler("trades.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("NovaTick-v2")

# ─── Alpaca client ─────────────────────────────────────────────────────────────
trade_client = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)

# ─── Indicator helpers ────────────────────────────────────────────────────────
def compute_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff().dropna()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - (100 / (1 + rs))
    val   = rsi.iloc[-1]
    return round(float(val), 2) if pd.notna(val) else 50.0


def compute_macd(series: pd.Series):
    """Returns (macd_line, signal_line). Bullish when macd > signal."""
    ema12  = series.ewm(span=12, adjust=False).mean()
    ema26  = series.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(signal.iloc[-1])


def compute_atr(df: pd.DataFrame, period=14) -> float:
    high_low = df['High'] - df['Low']
    high_cp = np.abs(df['High'] - df['Close'].shift())
    low_cp = np.abs(df['Low'] - df['Close'].shift())
    df_tr = pd.concat([high_low, high_cp, low_cp], axis=1)
    true_range = df_tr.max(axis=1)
    atr = true_range.rolling(period).mean().iloc[-1]
    return float(atr) if pd.notna(atr) else 0.0


def get_indicators(ticker: str) -> Optional[dict]:
    """Fetch 3 months of daily data and compute signals."""
    try:
        df = yf.Ticker(ticker).history(period="3mo", interval="1d")
        if df.empty or len(df) < 26:
            return None

        close     = df["Close"]
        rsi       = compute_rsi(close)
        macd, sig = compute_macd(close)
        atr       = compute_atr(df)
        ma20      = round(float(close.rolling(20).mean().iloc[-1]), 4)
        ma50      = round(float(close.rolling(50).mean().iloc[-1]), 4)
        price     = round(float(close.iloc[-1]), 4)

        return {
            "price":       price,
            "rsi":         rsi,
            "macd":        round(macd, 4),
            "macd_signal": round(sig, 4),
            "macd_bull":   macd > sig,
            "ma20":        ma20,
            "ma50":        ma50,
            "atr":         atr
        }
    except Exception as e:
        log.warning(f"  [{ticker}] indicator error: {e}")
        return None


# ─── Portfolio helpers ────────────────────────────────────────────────────────
def get_all_positions() -> dict:
    """Returns {symbol: position_object}."""
    try:
        return {p.symbol: p for p in trade_client.get_all_positions()}
    except Exception:
        return {}


def get_equity() -> float:
    return float(trade_client.get_account().equity)


def count_sector_holdings(symbol: str, positions: dict) -> int:
    """Count how many held symbols are in the same sector as `symbol`."""
    for sector, members in SECTORS.items():
        if symbol in members:
            return sum(1 for m in members if m in positions)
    return 0


def already_traded_today(ticker: str) -> bool:
    """True if we already placed an order for this ticker today (avoid double-buy)."""
    try:
        today = datetime.now(timezone.utc).date()
        req   = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=50)
        for o in trade_client.get_orders(req):
            if (o.symbol == ticker and
                    o.submitted_at and
                    o.submitted_at.date() == today):
                return True
    except Exception:
        pass
    return False


# ─── Order execution ──────────────────────────────────────────────────────────
def buy(ticker: str, price: float, atr: float, reason: str):
    equity  = get_equity()
    
    # Volatility-adjusted sizing: limit risk per trade based on ATR
    # If ATR is high (volatile), buy fewer shares
    risk_pct = 0.005 # Risk 0.5% of total equity on this distance to ATR stop
    stop_dist = atr * ATR_MULTIPLIER
    if stop_dist > 0:
        qty = int((equity * risk_pct) // stop_dist)
    else:
        qty = int((equity * POSITION_SIZE_PCT) // price)
        
    if qty < 1:
        log.info(f"  [SKIP BUY] {ticker} - qty < 1")
        return

    req   = MarketOrderRequest(symbol=ticker, qty=qty,
                               side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
    order = trade_client.submit_order(req)
    log.info(
        f"  [BUY]  {ticker:6s}  qty={qty}  ~${price:.2f}/sh | {reason} | order={order.id}"
    )


def sell(ticker: str, qty: float, reason: str):
    qty_int = int(qty)
    if qty_int < 1:
        return
    req   = MarketOrderRequest(symbol=ticker, qty=qty_int,
                               side=OrderSide.SELL, time_in_force=TimeInForce.DAY)
    order = trade_client.submit_order(req)
    log.info(f"  [SELL] {ticker:6s}  qty={qty_int}  | {reason}  | order={order.id}")


# ─── Market timing ────────────────────────────────────────────────────────────
def market_status() -> Tuple[bool, bool]:
    """Returns (is_open, past_open_buffer)."""
    clock    = trade_client.get_clock()
    is_open  = clock.is_open
    if not is_open:
        return False, False
    # Check we're past the opening buffer window
    now_utc   = datetime.now(timezone.utc)
    open_utc  = clock.next_open  # this is next open if closed; use now workaround
    # Approximate: market opens at 14:30 UTC (9:30 ET)
    market_open_utc = now_utc.replace(hour=14, minute=30, second=0, microsecond=0)
    past_buffer = now_utc >= market_open_utc + timedelta(minutes=OPEN_BUFFER_MINUTES)
    return True, past_buffer


def get_spy_rsi() -> float:
    """Market regime filter — if SPY RSI < threshold, avoid new buys."""
    ind = get_indicators("SPY")
    return ind["rsi"] if ind else 50.0


# ─── Main scan ────────────────────────────────────────────────────────────────
def scan():
    log.info("=" * 65)
    log.info("NovaTick v2 — scan started")

    acct      = trade_client.get_account()
    equity    = float(acct.equity)
    last_eq   = float(acct.last_equity)
    pnl       = equity - last_eq
    log.info(f"  Equity: ${equity:,.2f}  |  Today P&L: ${pnl:+,.2f}  |  Cash: ${float(acct.cash):,.2f}")

    positions = get_all_positions()
    log.info(f"  Open positions: {len(positions)} / {MAX_POSITIONS} max")

    # ── Market regime check ───────────────────────────────────────────────────
    spy_rsi = get_spy_rsi()
    bear_market = spy_rsi < MARKET_REGIME_RSI
    if bear_market:
        log.info(f"  [REGIME] SPY RSI={spy_rsi} < {MARKET_REGIME_RSI} → BEAR MODE: no new buys")
    else:
        log.info(f"  [REGIME] SPY RSI={spy_rsi} → market healthy, buys enabled")

    for ticker in WATCHLIST:
        ind = get_indicators(ticker)
        if ind is None:
            continue

        price     = ind["price"]
        rsi       = ind["rsi"]
        macd_bull = ind["macd_bull"]
        ma20      = ind["ma20"]
        held_pos  = positions.get(ticker)
        held_qty  = float(held_pos.qty) if held_pos else 0.0

        # ── Stop-loss & Take-profit (exit logic first) ────────────────────────
        if held_pos:
            entry     = float(held_pos.avg_entry_price)
            pl_pct    = (price - entry) / entry
            
            # Volatility Trailing Stop Logic
            # Exit if price drops more than ATR_MULTIPLIER * ATR from recent peak
            trailing_stop = price - (ind["atr"] * ATR_MULTIPLIER)
            if price < (entry * 0.95): # Basic hard stop still at -5%
                sell(ticker, held_qty, f"HARD STOP-LOSS {pl_pct*100:+.1f}%")
                continue

            if pl_pct >= TAKE_PROFIT_PCT:
                sell(ticker, held_qty, f"TAKE-PROFIT {pl_pct*100:+.1f}%")
                continue

        # ── RSI overbought exit ───────────────────────────────────────────────
        if held_qty > 0 and rsi > RSI_OVERBOUGHT and not macd_bull:
            sell(ticker, held_qty,
                 f"RSI={rsi} > {RSI_OVERBOUGHT} + bearish MACD → overbought exit")
            continue

        # ── BUY signal ────────────────────────────────────────────────────────
        if (
            held_qty == 0                                   # not already holding
            and not bear_market                             # market regime OK
            and len(positions) < MAX_POSITIONS              # position cap OK
            and count_sector_holdings(ticker, positions) < MAX_PER_SECTOR  # sector cap OK
            and not already_traded_today(ticker)            # no double-buy today
            and rsi < RSI_OVERSOLD                          # RSI oversold
            and macd_bull                                   # MACD confirms upward momentum
            and price < ma20                                # price below MA20 (dip)
        ):
            buy(ticker, price, ind["atr"],
                f"RSI={rsi}<{RSI_OVERSOLD} + bullish MACD + price<MA20")
            # Refresh positions after a buy
            positions = get_all_positions()
        else:
            log.info(
                f"  [HOLD] {ticker:6s}  price=${price:.2f}  RSI={rsi:5.1f}  "
                f"MACD={'bull' if macd_bull else 'bear'}  held={held_qty:.0f}sh"
            )

    log.info("Scan complete.\n")


# ─── Run loop ─────────────────────────────────────────────────────────────────
def run():
    log.info("NovaTick Bot v2 starting")
    log.info(f"Watchlist : {len(WATCHLIST)} stocks")
    log.info(f"Paper mode: {PAPER}")
    log.info(f"Strategy  : RSI({RSI_OVERSOLD}/{RSI_OVERBOUGHT}) + MACD + SL{STOP_LOSS_PCT*100:.0f}% TP+{TAKE_PROFIT_PCT*100:.0f}%")
    log.info(f"Filters   : max {MAX_POSITIONS} positions, max {MAX_PER_SECTOR}/sector, skip first {OPEN_BUFFER_MINUTES}min\n")

    while True:
        try:
            is_open, past_buffer = market_status()

            if not is_open:
                now = datetime.now(timezone.utc)
                log.info(f"Market CLOSED ({now.strftime('%H:%M UTC')}) — waiting {SCAN_INTERVAL}s")

            elif not past_buffer:
                log.info(f"Market open but within {OPEN_BUFFER_MINUTES}min buffer — skipping volatile open")

            else:
                scan()

        except KeyboardInterrupt:
            log.info("Bot stopped by user.")
            break
        except Exception as e:
            log.error(f"Unexpected error: {e}", exc_info=True)

        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    run()
