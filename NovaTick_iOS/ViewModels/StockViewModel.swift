import Foundation
import SwiftUI

@MainActor
class StockViewModel: ObservableObject {
    @Published var stockData: StockResponse?
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    
    // Paper Trading Wallet State
    @Published var paperBalance: Double = 100.00
    @Published var holdings: [PortfolioHolding] = []
    
    func analyzeTicker(_ ticker: String) {
        guard !ticker.isEmpty else { return }
        
        Task {
            self.isLoading = true
            self.errorMessage = nil
            do {
                self.stockData = try await APIService.shared.fetchStockData(for: ticker)
            } catch {
                self.errorMessage = "Failed to load data. Please check the ticker."
            }
            self.isLoading = false
        }
    }
    
    func executePaperTrade(action: String, shares: Int) {
        guard let data = stockData else { return }
        let cost = Double(shares) * data.current_price
        
        if action == "BUY" && paperBalance >= cost {
            paperBalance -= cost
            
            if let index = holdings.firstIndex(where: { $0.ticker == data.ticker }) {
                let currentAvg = holdings[index].averagePrice
                let currentShares = holdings[index].shares
                
                let newShares = currentShares + shares
                let newAvg = ((currentAvg * Double(currentShares)) + cost) / Double(newShares)
                
                holdings[index].shares = newShares
                holdings[index].averagePrice = newAvg
            } else {
                holdings.append(PortfolioHolding(ticker: data.ticker, shares: shares, averagePrice: data.current_price))
            }
            
            // Haptic Feedback for success
            let impact = UIImpactFeedbackGenerator(style: .medium)
            impact.impactOccurred()
            
        } else if action == "SELL" {
            if let index = holdings.firstIndex(where: { $0.ticker == data.ticker }), holdings[index].shares >= shares {
                paperBalance += cost
                holdings[index].shares -= shares
                
                if holdings[index].shares == 0 {
                    holdings.remove(at: index)
                }
                
                let impact = UIImpactFeedbackGenerator(style: .medium)
                impact.impactOccurred()
            }
        }
    }
}
