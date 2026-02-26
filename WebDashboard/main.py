from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import timedelta
import os
import urllib.request
import xml.etree.ElementTree as ET

app = FastAPI(title="NovaTick AI Engine")

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

@app.get("/top50.html")
def serve_top50():
    return FileResponse(os.path.join(BASE_DIR, "top50.html"))


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

        # Manual Linear Regression forecast for next 7 days
        days = list(range(len(df)))
        closes = df["Close"].tolist()
        
        n = len(days)
        sum_x = sum(days)
        sum_y = sum(closes)
        sum_xy = sum(x * y for x, y in zip(days, closes))
        sum_xx = sum(x * x for x in days)
        
        denominator = (n * sum_xx - sum_x * sum_x)
        if denominator == 0:
            m = 0
            b = sum_y / n if n > 0 else 0
        else:
            m = (n * sum_xy - sum_x * sum_y) / denominator
            b = (sum_y - m * sum_x) / n
            
        forecast = []
        last_date = df.index[-1]
        for i in range(1, 8):
            future_x = n - 1 + i
            pred = m * future_x + b
            future_date = (last_date + timedelta(days=i)).strftime("%Y-%m-%d")
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
        summary = summary_raw[:200] + "..." if len(summary_raw) > 200 else summary_raw

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



# ─── News Endpoint ───────────────────────────────────────────────────────────
@app.get("/api/news/{ticker}")
def get_news(ticker: str):
    """Fetch latest news headlines via Yahoo Finance RSS."""
    try:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker.upper()}&region=US&lang=en-US"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        ns = ""
        items = root.findall(".//item")
        articles = []
        for item in items[:6]:  # top 6 headlines
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            pub   = item.findtext("pubDate", "").strip()
            # Simple sentiment: check for positive/negative keywords
            title_lower = title.lower()
            pos_words = ["rise", "gain", "surge", "jump", "beat", "record", "rally", "up", "bull", "strong", "growth", "profit"]
            neg_words = ["fall", "drop", "loss", "miss", "crash", "decline", "down", "bear", "weak", "layoff", "cut", "warn"]
            pos = sum(1 for w in pos_words if w in title_lower)
            neg = sum(1 for w in neg_words if w in title_lower)
            sentiment = "positive" if pos > neg else ("negative" if neg > pos else "neutral")
            articles.append({"title": title, "link": link, "pub": pub, "sentiment": sentiment})
        return {"ticker": ticker.upper(), "articles": articles}
    except Exception as e:
        # Fallback: try yfinance news
        try:
            stock = yf.Ticker(ticker.upper())
            news = stock.news or []
            articles = []
            for n in news[:6]:
                articles.append({
                    "title": n.get("title", ""),
                    "link": n.get("link", ""),
                    "pub": "",
                    "sentiment": "neutral"
                })
            return {"ticker": ticker.upper(), "articles": articles}
        except:
            raise HTTPException(status_code=500, detail=str(e))


# Serve CSS, JS, and other static assets AFTER API routes
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    print("NovaTick AI starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
