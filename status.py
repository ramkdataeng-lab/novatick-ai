from dotenv import load_dotenv
load_dotenv()
import os
from alpaca.trading.client import TradingClient
from datetime import datetime

c = TradingClient(os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY'), paper=True)

# ── Account summary ───────────────────────────────────────────────────────────
a = c.get_account()
equity        = float(a.equity)
cash          = float(a.cash)
buying_power  = float(a.buying_power)
portfolio_val = float(a.portfolio_value)
last_equity   = float(a.last_equity)
pnl_today     = equity - last_equity
pnl_pct       = (pnl_today / last_equity * 100) if last_equity else 0

print("=" * 55)
print("  AlphaTrade Bot — Account Status")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 55)
print(f"  Portfolio Value : ${portfolio_val:>12,.2f}")
print(f"  Total Equity    : ${equity:>12,.2f}")
print(f"  Cash Available  : ${cash:>12,.2f}")
print(f"  Buying Power    : ${buying_power:>12,.2f}")
print(f"  Today's P&L     : ${pnl_today:>+12,.2f}  ({pnl_pct:+.2f}%)")
print("=" * 55)

# ── Open positions ────────────────────────────────────────────────────────────
positions = c.get_all_positions()
if positions:
    print(f"\n  Open Positions ({len(positions)} total):")
    print(f"  {'Ticker':<8} {'Qty':>6} {'Entry $':>10} {'Current $':>10} {'P&L $':>10} {'P&L %':>8}")
    print("  " + "-" * 56)
    total_unr = 0.0
    for p in positions:
        unr = float(p.unrealized_pl)
        total_unr += unr
        print(
            f"  {p.symbol:<8} {float(p.qty):>6.0f} "
            f"${float(p.avg_entry_price):>9,.2f} "
            f"${float(p.current_price):>9,.2f} "
            f"${unr:>+9,.2f} "
            f"{float(p.unrealized_plpc)*100:>+7.2f}%"
        )
    print("  " + "-" * 56)
    print(f"  {'TOTAL UNREALIZED P&L':>42}  ${total_unr:>+9,.2f}")
else:
    print("\n  No open positions.")

# ── Recent orders ─────────────────────────────────────────────────────────────
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=10)
orders = c.get_orders(req)
if orders:
    print(f"\n  Recent Orders (last {len(orders)}):")
    print(f"  {'Symbol':<8} {'Side':<5} {'Qty':>5} {'Status':<12} {'Submitted'}")
    print("  " + "-" * 55)
    for o in orders:
        submitted = o.submitted_at.strftime('%m/%d %H:%M') if o.submitted_at else '---'
        print(f"  {o.symbol:<8} {str(o.side).split('.')[-1]:<5} {float(o.qty or 0):>5.0f} {str(o.status).split('.')[-1]:<12} {submitted}")
else:
    print("\n  No recent orders found.")

print("\n  Bot watches: NVDA AAPL TSLA MSFT AMD INTC META GOOGL AMZN")
print("               + 41 more stocks across all sectors")
print("=" * 55)
