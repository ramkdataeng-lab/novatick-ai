import SwiftUI
import Charts

struct StockDetailView: View {
    let data: StockResponse
    @ObservedObject var viewModel: StockViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            
            // Header Info
            HStack(alignment: .top) {
                VStack(alignment: .leading) {
                    Text(data.name)
                        .font(.title2)
                        .bold()
                        .foregroundColor(.white)
                    Text(data.ticker.uppercased())
                        .font(.subheadline)
                        .foregroundColor(.gray)
                }
                Spacer()
                Text(String(format: "$%.2f", data.current_price))
                    .font(.title)
                    .fontWeight(.heavy)
                    .foregroundColor(.white)
            }
            
            // SwiftUI Core Chart
            Chart {
                ForEach(data.history) { item in
                    if let date = item.parsedDate {
                        LineMark(
                            x: .value("Date", date),
                            y: .value("Price", item.close)
                        )
                        .foregroundStyle(Color(red: 99/255, green: 102/255, blue: 241/255))
                    }
                }
                
                ForEach(data.forecast) { item in
                    if let date = item.parsedDate {
                        LineMark(
                            x: .value("Date", date),
                            y: .value("Predicted", item.predicted_close)
                        )
                        .foregroundStyle(Color(red: 245/255, green: 158/255, blue: 11/255))
                        .lineStyle(StrokeStyle(lineWidth: 2, dash: [5, 5]))
                    }
                }
            }
            .frame(height: 250)
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 4))
            }
            
            // AI Signals Card
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Image(systemName: "cpu")
                    Text("Agent Alpha Signal")
                        .font(.headline)
                    Spacer()
                    Text(data.agent_signal)
                        .bold()
                        .foregroundColor(signalColor(data.agent_signal))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 4)
                        .background(signalColor(data.agent_signal).opacity(0.2))
                        .cornerRadius(8)
                }
                
                Divider().background(.gray).opacity(0.3)
                
                HStack {
                    Text("RSI (14)")
                    Spacer()
                    Text("\(String(format: "%.1f", data.indicators.rsi)) (\(data.indicators.rsi_label))")
                        .foregroundColor(.gray)
                }
                HStack {
                    Text("MA Trend")
                    Spacer()
                    Text(data.indicators.ma_trend)
                        .foregroundColor(.gray)
                }
            }
            .padding()
            .background(.ultraThinMaterial)
            .cornerRadius(15)
        }
    }
    
    func signalColor(_ signal: String) -> Color {
        switch signal {
        case "BUY": return .green
        case "SELL": return .red
        default: return .yellow
        }
    }
}
