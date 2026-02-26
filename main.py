from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import timedelta
import os

app = FastAPI(title="AlphaTrade AI Engine")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))


@app.get("/api/stock/{ticker}")
async def get_stock_data(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for ticker '{ticker}'")

        # Build OHLCV history
        history = []
        for index, row in df.iterrows():
            history.append({
                "date": index.strftime("%Y-%m-%d"),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })

        # Linear Regression forecast for next 7 days
        df_reset = df.reset_index()
        df_reset["days"] = range(len(df_reset))
        X = df_reset[["days"]].values
        y = df_reset["Close"].values

        model = LinearRegression()
        model.fit(X, y)

        future_days = np.array([[len(df_reset) + i] for i in range(1, 8)])
        predictions = model.predict(future_days)

        forecast = []
        last_date = df.index[-1]
        for i, pred in enumerate(predictions):
            future_date = (last_date + timedelta(days=i + 1)).strftime("%Y-%m-%d")
            forecast.append({
                "date": future_date,
                "predicted_close": round(float(pred), 2),
            })

        # Technical Indicators — MA20, MA50, basic RSI
        df["MA20"] = df["Close"].rolling(window=20).mean()
        df["MA50"] = df["Close"].rolling(window=50).mean()

        def compute_rsi(series, period=14):
            delta = series.diff()
            gain = delta.clip(lower=0).rolling(period).mean()
            loss = -delta.clip(upper=0).rolling(period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))

        df["RSI14"] = compute_rsi(df["Close"])

        current_price = history[-1]["close"]
        ma20 = round(df["MA20"].iloc[-1], 2) if not pd.isna(df["MA20"].iloc[-1]) else current_price
        ma50 = round(df["MA50"].iloc[-1], 2) if not pd.isna(df["MA50"].iloc[-1]) else current_price
        rsi = round(df["RSI14"].iloc[-1], 1) if not pd.isna(df["RSI14"].iloc[-1]) else 50.0

        # Signal logic
        signal = "HOLD"
        if current_price < ma20 * 0.98 and rsi < 40:
            signal = "BUY"
        elif current_price > ma20 * 1.02 and rsi > 65:
            signal = "SELL"

        # RSI label
        if rsi > 70:
            rsi_label = "Overbought"
        elif rsi < 30:
            rsi_label = "Oversold"
        else:
            rsi_label = "Neutral"

        # MA trend
        ma_trend = "Bullish" if ma20 > ma50 else "Bearish"

        info = stock.info
        summary_raw = info.get("longBusinessSummary", "No company summary available.")
        summary = summary_raw[:350] + "..." if len(summary_raw) > 350 else summary_raw

        return {
            "ticker": ticker.upper(),
            "name": info.get("longName", ticker.upper()),
            "current_price": current_price,
            "currency": info.get("currency", "USD"),
            "history": history,
            "forecast": forecast,
            "agent_signal": signal,
            "summary": summary,
            "indicators": {
                "rsi": rsi,
                "rsi_label": rsi_label,
                "ma20": ma20,
                "ma50": ma50,
                "ma_trend": ma_trend,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve CSS, JS, and other static assets AFTER API routes
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    print("AlphaTrade AI starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
