import Foundation

enum APIError: Error {
    case invalidURL
    case invalidResponse
    case decodingError
}

class APIService {
    static let shared = APIService()
    
    // Defaulting to the local host for simulator testing, or Vercel URL
    let baseURL = "http://localhost:8000/api/stock/"
    
    private init() {}
    
    func fetchStockData(for ticker: String) async throws -> StockResponse {
        guard let url = URL(string: "\(baseURL)\(ticker.uppercased())") else {
            throw APIError.invalidURL
        }
        
        // Simulating network delay to show off shiny loading states
        if baseURL.contains("localhost") {
            try await Task.sleep(nanoseconds: 500_000_000)
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        do {
            let decoder = JSONDecoder()
            let stockData = try decoder.decode(StockResponse.self, from: data)
            return stockData
        } catch {
            print("Decoding error: \(error)")
            throw APIError.decodingError
        }
    }
}
