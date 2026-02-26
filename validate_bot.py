import bot

print("Bot v2 loaded OK")
print(f"Watchlist  : {len(bot.WATCHLIST)} stocks")

spy = bot.get_spy_rsi()
print(f"SPY RSI    : {spy}")

bear = spy < bot.MARKET_REGIME_RSI
print(f"Bear mode  : {bear} (threshold RSI < {bot.MARKET_REGIME_RSI})")

pos = bot.get_all_positions()
print(f"Positions  : {len(pos)} open -> {list(pos.keys())}")

eq = bot.get_equity()
print(f"Equity     : ${eq:,.2f}")

is_open, past_buf = bot.market_status()
print(f"Market open: {is_open}  |  Past buffer: {past_buf}")
print("All checks passed.")
