import SwiftUI

struct WalletView: View {
    @ObservedObject var viewModel: StockViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            
            HStack {
                Image(systemName: "case.fill")
                    .foregroundColor(Color(red: 99/255, green: 102/255, blue: 241/255))
                Text("Paper Wallet")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                Text(String(format: "$%.2f", viewModel.paperBalance))
                    .font(.headline)
                    .foregroundColor(.green)
            }
            
            if let data = viewModel.stockData {
                HStack(spacing: 15) {
                    Button(action: {
                        viewModel.executePaperTrade(action: "BUY", shares: 1)
                    }) {
                        Text("Simulate BUY")
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.green.opacity(0.2))
                            .foregroundColor(.green)
                            .cornerRadius(10)
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.green, lineWidth: 1))
                    }
                    
                    Button(action: {
                        viewModel.executePaperTrade(action: "SELL", shares: 1)
                    }) {
                        Text("Simulate SELL")
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.red.opacity(0.2))
                            .foregroundColor(.red)
                            .cornerRadius(10)
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.red, lineWidth: 1))
                    }
                }
            }
            
            if !viewModel.holdings.isEmpty {
                Divider().background(.gray).opacity(0.3)
                Text("Holdings")
                    .font(.subheadline)
                    .foregroundColor(.gray)
                
                ForEach(viewModel.holdings) { holding in
                    HStack {
                        Text(holding.ticker)
                            .bold()
                            .foregroundColor(.white)
                        Spacer()
                        Text("\(holding.shares) sh")
                            .foregroundColor(.gray)
                        Text(String(format: "$%.2f avg", holding.averagePrice))
                            .foregroundColor(.gray)
                    }
                    .font(.footnote)
                }
            }
        }
        .padding()
        .background(.ultraThinMaterial)
        .cornerRadius(15)
    }
}
