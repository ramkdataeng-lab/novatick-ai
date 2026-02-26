from dotenv import load_dotenv
load_dotenv()
import os
from alpaca.trading.client import TradingClient

c = TradingClient(os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY'), paper=True)
a = c.get_account()
print(f"Account : {a.account_number}")
print(f"Status  : {a.status}")
print(f"Equity  : ${float(a.equity):,.2f}")
print(f"Buying  : ${float(a.buying_power):,.2f}")
clk = c.get_clock()
print(f"Market  : {'OPEN' if clk.is_open else 'CLOSED'}")
print("Connection OK")
