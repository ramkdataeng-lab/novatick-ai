import Foundation

// MARK: - Root Response
struct StockResponse: Codable {
    let ticker: String
    let name: String
    let current_price: Double
    let currency: String
    let history: [HistoryItem]
    let forecast: [ForecastItem]
    let agent_signal: String
    let summary: String
    let indicators: TechnicalIndicators
}

// MARK: - History Item
struct HistoryItem: Codable, Identifiable {
    let date: String
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Int
    
    var id: String { date }
    
    var parsedDate: Date? {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: date)
    }
}

// MARK: - Forecast Item
struct ForecastItem: Codable, Identifiable {
    let date: String
    let predicted_close: Double
    
    var id: String { date }
    
    var parsedDate: Date? {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: date)
    }
}

// MARK: - Indicators
struct TechnicalIndicators: Codable {
    let rsi: Double
    let rsi_label: String
    let ma20: Double
    let ma50: Double
    let ma_trend: String
}

// MARK: - Paper Trade Holding
struct PortfolioHolding: Codable, Identifiable, Hashable {
    var id: String { ticker }
    let ticker: String
    var shares: Int
    var averagePrice: Double
}
