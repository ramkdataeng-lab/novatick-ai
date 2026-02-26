let mainChart = null;
let paperBalance = 100.00;
let holdings = {};   // { ticker: { shares, avgPrice } }
let tradeLog = [];
let autoTrading = false;
let autoInterval = null;
let currentHistory = [];

// ─── Fetch & update UI ────────────────────────────────────────────────────────
async function fetchStockData(ticker) {
    try {
        setLoadingState(true);
        // Same-origin API call when served from FastAPI
        const response = await fetch(`/api/stock/${ticker.toUpperCase()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        updateUI(data);
        return data;
    } catch (err) {
        console.error('Fetch error:', err);
        alert(`Could not load data for "${ticker}". Check the ticker symbol or server.`);
    } finally {
        setLoadingState(false);
    }
}

function setLoadingState(loading) {
    const btn = document.getElementById('analyzeBtn');
    btn.textContent = loading ? '...' : 'Analyze';
    btn.disabled = loading;
}

function updateUI(data) {
    // Header strip
    document.getElementById('stockName').textContent = data.name;
    document.getElementById('stockTicker').textContent = data.ticker;
    document.getElementById('currentPrice').textContent = `$${data.current_price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    // Price change vs first close in history
    const firstClose = data.history[0].close;
    const pct = ((data.current_price - firstClose) / firstClose * 100).toFixed(2);
    const chgEl = document.getElementById('priceChange');
    chgEl.textContent = `${pct >= 0 ? '+' : ''}${pct}% (1Y)`;
    chgEl.className = `price-change ${pct >= 0 ? 'positive' : 'negative'}`;

    // Company blurb
    document.getElementById('companySummary').textContent = data.summary;

    // Agent signal
    const signalEl = document.getElementById('signalValue');
    signalEl.textContent = data.agent_signal;
    const sigColour = { BUY: 'var(--positive)', SELL: 'var(--negative)', HOLD: 'var(--warning)' };
    signalEl.style.color = sigColour[data.agent_signal] || 'white';

    // Technical signals panel
    const ind = data.indicators;
    updateSignalPanel(ind);

    // Forecast list
    const forecastList = document.getElementById('forecastList');
    forecastList.innerHTML = '';
    const lastClose = data.history.at(-1).close;
    data.forecast.forEach(item => {
        const diff = item.predicted_close - lastClose;
        const colour = diff >= 0 ? 'var(--positive)' : 'var(--negative)';
        const arrow = diff >= 0 ? '▲' : '▼';
        const div = document.createElement('div');
        div.className = 'forecast-item';
        div.innerHTML = `
            <span>${item.date}</span>
            <span style="font-weight:700;color:${colour}">
                ${arrow} $${item.predicted_close.toFixed(2)}
            </span>`;
        forecastList.appendChild(div);
    });

    // Wallet display
    document.querySelector('.virtual-balance .value').textContent =
        `$${paperBalance.toFixed(2)}`;

    // Render chart
    currentHistory = data.history;
    renderChart(data.history, data.forecast);

    // Zoom chart if a period is selected
    const activeBtn = document.querySelector('.chart-controls button.active');
    if (activeBtn) {
        zoomChart(activeBtn.dataset.period);
    }

    // If auto-trading is on, act on the signal
    if (autoTrading) {
        executeAgentAction(data.ticker, data.current_price, data.agent_signal);
    }
}

function updateSignalPanel(ind) {
    const rsiStatus = ind.rsi > 70 ? 'negative' : (ind.rsi < 30 ? 'positive' : 'neutral');
    const maStatus = ind.ma_trend === 'Bullish' ? 'positive' : 'negative';
    document.getElementById('rsiDisplay').textContent = `${ind.rsi} (${ind.rsi_label})`;
    document.getElementById('rsiDisplay').className = `status ${rsiStatus}`;
    document.getElementById('maDisplay').textContent = `${ind.ma_trend} (MA20: $${ind.ma20})`;
    document.getElementById('maDisplay').className = `status ${maStatus}`;
}

// ─── Chart rendering ─────────────────────────────────────────────────────────
function renderChart(history, forecast) {
    const candleData = history.map(item => ({
        x: new Date(item.date),
        y: [item.open, item.high, item.low, item.close],
    }));

    const forecastLine = forecast.map(item => ({
        x: new Date(item.date),
        y: item.predicted_close,
    }));

    // Add the last real close as the start of the forecast line so it connects smoothly
    forecastLine.unshift({ x: new Date(history.at(-1).date), y: history.at(-1).close });

    const options = {
        series: [
            { name: 'OHLC', type: 'candlestick', data: candleData },
            { name: 'AI Forecast', type: 'line', data: forecastLine },
        ],
        chart: {
            height: 420,
            background: 'transparent',
            toolbar: { show: false },
            animations: { enabled: true, speed: 600 },
        },
        theme: { mode: 'dark' },
        plotOptions: {
            candlestick: { colors: { upward: '#22c55e', downward: '#ef4444' } },
        },
        stroke: { width: [1, 2], curve: 'smooth', dashArray: [0, 4] },
        colors: ['#6366f1', '#f59e0b'],
        xaxis: { type: 'datetime' },
        yaxis: { tooltip: { enabled: true }, labels: { formatter: v => `$${v.toFixed(0)}` } },
        grid: { borderColor: 'rgba(255,255,255,0.05)' },
        legend: { labels: { colors: '#a1a1aa' } },
        tooltip: { theme: 'dark' },
    };

    if (mainChart) mainChart.destroy();
    mainChart = new ApexCharts(document.querySelector('#mainChart'), options);
    mainChart.render();
}

function zoomChart(period) {
    if (!mainChart || currentHistory.length === 0) return;
    const lastDate = new Date(currentHistory.at(-1).date).getTime();
    let minDate;
    const DAY = 24 * 60 * 60 * 1000;

    if (period === '1W') minDate = lastDate - 7 * DAY;
    else if (period === '2W') minDate = lastDate - 14 * DAY;
    else if (period === '1M') minDate = lastDate - 30 * DAY;
    else if (period === '6M') minDate = lastDate - 180 * DAY;
    else minDate = new Date(currentHistory[0].date).getTime();

    const maxDate = lastDate + 8 * DAY; // Include 7-day forecast
    mainChart.zoomX(minDate, maxDate);
}

// ─── Paper-trading agent ──────────────────────────────────────────────────────
function executeAgentAction(ticker, price, signal) {
    const timestamp = new Date().toLocaleTimeString();
    let action = null;

    if (signal === 'BUY' && paperBalance >= price) {
        const maxShares = Math.floor(paperBalance / price);
        const buyShares = Math.max(1, Math.floor(maxShares * 0.2)); // invest 20% of balance
        const cost = buyShares * price;
        if (cost <= paperBalance) {
            paperBalance -= cost;
            holdings[ticker] = holdings[ticker] || { shares: 0, avgPrice: 0 };
            holdings[ticker].avgPrice =
                (holdings[ticker].avgPrice * holdings[ticker].shares + cost) /
                (holdings[ticker].shares + buyShares);
            holdings[ticker].shares += buyShares;
            action = { time: timestamp, type: 'BUY', ticker, shares: buyShares, price, cost };
        }
    } else if (signal === 'SELL' && holdings[ticker]?.shares > 0) {
        const sellShares = Math.ceil(holdings[ticker].shares / 2); // sell half
        const proceeds = sellShares * price;
        paperBalance += proceeds;
        holdings[ticker].shares -= sellShares;
        action = { time: timestamp, type: 'SELL', ticker, shares: sellShares, price, proceeds };
    }

    if (action) {
        tradeLog.unshift(action);
        renderTradeLog();
        document.querySelector('.virtual-balance .value').textContent =
            `$${paperBalance.toFixed(2)}`;
    }
}

function renderTradeLog() {
    let logEl = document.getElementById('tradeLog');
    if (!logEl) return;
    logEl.innerHTML = tradeLog.slice(0, 5).map(t => {
        const colour = t.type === 'BUY' ? 'var(--positive)' : 'var(--negative)';
        const detail = t.type === 'BUY'
            ? `Bought ${t.shares} share(s) @ $${t.price.toFixed(2)} — cost $${t.cost.toFixed(2)}`
            : `Sold ${t.shares} share(s) @ $${t.price.toFixed(2)} — earned $${t.proceeds.toFixed(2)}`;
        return `<li><span style="color:${colour};font-weight:700">${t.type}</span> ${t.ticker} — ${detail} <small style="color:var(--text-dim)">${t.time}</small></li>`;
    }).join('');
}

// ─── Event listeners ──────────────────────────────────────────────────────────
document.querySelectorAll('.chart-controls button').forEach(btn => {
    btn.addEventListener('click', (e) => {
        document.querySelectorAll('.chart-controls button').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        zoomChart(e.target.dataset.period);
    });
});

document.getElementById('analyzeBtn').addEventListener('click', () => {
    const ticker = document.getElementById('tickerInput').value.trim();
    if (ticker) fetchStockData(ticker);
});

document.getElementById('tickerInput').addEventListener('keypress', e => {
    if (e.key === 'Enter') {
        const ticker = document.getElementById('tickerInput').value.trim();
        if (ticker) fetchStockData(ticker);
    }
});

document.getElementById('autoTradeBtn').addEventListener('click', function () {
    autoTrading = !autoTrading;
    if (autoTrading) {
        this.textContent = '🔴 Stop Agent';
        this.style.background = 'var(--negative)';
        // Re-check signal every 60 seconds
        autoInterval = setInterval(() => {
            const ticker = document.getElementById('tickerInput').value.trim() || 'NVDA';
            fetchStockData(ticker);
        }, 60000);
        // Fire once immediately
        const ticker = document.getElementById('tickerInput').value.trim() || 'NVDA';
        fetchStockData(ticker);
    } else {
        this.textContent = '🤖 Enable Auto-Trading';
        this.style.background = 'var(--primary)';
        if (autoInterval) clearInterval(autoInterval);
    }
});

// Initial load
window.addEventListener('load', () => fetchStockData('NVDA'));
