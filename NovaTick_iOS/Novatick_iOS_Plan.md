# NovaTick AI — iOS App Plan (Free Version)

## 1. Product Vision & Value Proposition
The free tier of the NovaTick iOS app will serve as a high-performance, mobile-first companion to the NovaTick AI dashboard. It provides retail traders with immediate access to predictive AI stock intelligence, straightforward technical signals, and paper-trading capabilities on the go.

### Core Goals:
- Deliver a premium, glassmorphism UI experience optimized for iOS natively.
- Provide high-speed ticker lookups with linear-regression AI forecasts.
- Allow users to test strategies freely using the built-in paper-trading wallet.

---

## 2. Key Features (Free Tier)

### 📊 Dashboard & AI Search
- **Stock Lookup:** High-speed lookup for up to 50 curated tickers.
- **AI Forecast Generation:** 7-day linear regression predictive graphs built natively using SwiftUI Charts.
- **Micro-Animations:** Fluid transitions as stock data loads and prices update.

### 🧠 Agent Alpha Signals
- **Technical Readouts:** Live RSI (Oversold/Overbought/Neutral) and Moving Average Cross (Bullish/Bearish) displays.
- **Actionable AI Status:** Instant 'BUY', 'SELL', or 'HOLD' recommendation based on the backend algorithm.

### 💼 Virtual Paper Trading Account
- **Free Wallet:** Users start with a $100.00 virtual iOS paper trading account.
- **One-Tap Market Orders:** Instant simulated order fills using current market prices.
- **Portfolio Tracking:** Simple list view of current holdings and cumulative Return on Investment (ROI %).

### 🔔 Basic Notifications
- **End-of-Day Summary:** Push notification detailing portfolio performance at market close.
- **Actionable Market Shifts (Optional):** Alert when the S&P 500 (SPY) indicates a bearish/bullish regime shift.

---

## 3. UI/UX & Design Language (SwiftUI)

- **Color Palette:**
  - **Background:** Deep slate (`#0f172a`) with subtle glassmorphic blur effects.
  - **Accents:** Electric Indigo (`#6366f1`) for charts, vibrant Green (`#22c55e`) for bullish momentum, and bright Amber (`#f59e0b`) for active processes.
- **Typography:** Apple's native San Francisco (SF Pro) font customized with varying weights for hierarchy.
- **Haptic Feedback:** Strategic use of `UIImpactFeedbackGenerator` when executing paper trades or pulling to refresh.

---

## 4. Technical Architecture

- **Frontend:** Swift / SwiftUI (Targeting iOS 16+)
- **Architecture Pattern:** MVVM (Model-View-ViewModel) to cleanly separate UI state, business logic, and backend networking.
- **Backend API Integration:**
  - Consume the existing `main.py` (FastAPI) endpoints hosted on Vercel.
  - Endpoints: `GET /api/stock/{ticker}` for fetching indicators, signals, and historical/forecast data.
- **Local Storage:** Use `CoreData` or `SwiftData` to store the virtual paper portfolio locally on the device (avoids needing a complex authentication backend for the free tier).

---

## 5. Development Roadmap

### Phase 1: Foundation (Weeks 1-2)
- Setup SwiftUI project, wire up MVVM architecture.
- Integrate network requests to the Vercel FastAPI endpoint.
- Build the core Charting View using SwiftUI Charts.

### Phase 2: Trading Engine & UI Polish (Weeks 3-4)
- Implement Local Storage (SwiftData) for paper trading wallet.
- Build the Agent Signal views and execute simulated trades natively.
- Apply glassmorphism styling, haptics, and micro-animations.

### Phase 3: Testing & Submission (Weeks 5-6)
- Beta testing via TestFlight.
- Implement Apple App Store requirements (Terms, Privacy Policy, Support link).
- Finalize App Icon, Screenshots, and App Store submission optimizations.

---

## 6. Monetization Strategy (Future Paid Tier v2.0)
While this is the free tier, the architecture should be built to optionally support a "NovaTick Pro" tier later via In-App Purchases, which could unlock:
- Real-time WebSockets data (vs delayed/hourly API pulls).
- Automated execution matching (auto-trade slider).
- Expanded stock lookup beyond the top 50 curated lists.
- Advanced neural-network forecasting models.
