import SwiftUI
import Charts

struct ContentView: View {
    @StateObject var viewModel = StockViewModel()
    @State private var searchTicker = "NVDA"
    
    var body: some View {
        NavigationView {
            ZStack {
                // Background
                Color(red: 15/255, green: 23/255, blue: 42/255).edgesIgnoringSafeArea(.all)
                
                VStack(spacing: 20) {
                    
                    // Header Search Bar
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.gray)
                        TextField("Enter Ticker...", text: $searchTicker)
                            .foregroundColor(.white)
                            .submitLabel(.search)
                            .onSubmit {
                                viewModel.analyzeTicker(searchTicker)
                            }
                        if viewModel.isLoading {
                            ProgressView().tint(.white)
                        } else {
                            Button("Analyze") {
                                viewModel.analyzeTicker(searchTicker)
                            }
                            .bold()
                            .foregroundColor(Color(red: 99/255, green: 102/255, blue: 241/255))
                        }
                    }
                    .padding()
                    .background(.ultraThinMaterial)
                    .cornerRadius(15)
                    .padding(.horizontal)
                    
                    if let data = viewModel.stockData {
                        ScrollView(showsIndicators: false) {
                            StockDetailView(data: data, viewModel: viewModel)
                                .padding(.horizontal)
                            
                            WalletView(viewModel: viewModel)
                                .padding(.horizontal)
                                .padding(.top, 10)
                        }
                    } else if let err = viewModel.errorMessage {
                        Text(err).foregroundColor(.red).padding()
                        Spacer()
                    } else {
                        Spacer()
                        Text("Search a ticker to view AI inference")
                            .foregroundColor(.gray)
                        Spacer()
                    }
                }
            }
            .navigationBarHidden(true)
        }
        .onAppear {
            viewModel.analyzeTicker(searchTicker)
        }
        .preferredColorScheme(.dark)
    }
}
