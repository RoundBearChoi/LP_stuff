import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


class CryptoPriceFetcher:
    # Yahoo Finance has naming conflicts for some popular tokens
    TICKER_MAPPING = {
        "UNI": "UNI7083-USD",   # Uniswap (not UNICORN Token)
        "FART": "FARTCOIN-USD", # ← The popular Solana Fartcoin (not the tiny Base one)
        "PUMP": "PUMP36507-USD",
    }

    def __init__(self, token1: str, token2: str):
        self.raw1 = token1.upper()
        self.raw2 = token2.upper()

        # Get correct internal Yahoo ticker
        self.symbol1 = self.TICKER_MAPPING.get(self.raw1, f"{self.raw1}-USD")
        self.symbol2 = self.TICKER_MAPPING.get(self.raw2, f"{self.raw2}-USD")

        # Keep clean names for columns + filename
        self.name1 = self.raw1
        self.name2 = self.raw2

    def fetch_and_save(self):
        end_date = datetime.today().date()
        start_date = end_date - timedelta(days=730 + 7)  # 2 years + buffer

        print(f"Fetching daily closing prices for {self.symbol1} and {self.symbol2}...")
        print(f"Period: {start_date} → {end_date}")

        df = yf.download(
            tickers=[self.symbol1, self.symbol2],
            start=start_date,
            end=end_date,
            interval="1d",
            progress=False,
            auto_adjust=True
        )

        closing_prices = df["Close"].copy()
        
        # FIXED: Rename columns by actual ticker (not by position)
        # This prevents swapping when yfinance returns columns alphabetically sorted
        closing_prices = closing_prices.rename(columns={
            self.symbol1: self.name1,
            self.symbol2: self.name2
        })
        
        # Force column order to always match user input (SOL first, then FART, etc.)
        closing_prices = closing_prices[[self.name1, self.name2]]
        
        closing_prices = closing_prices.dropna()

        print(f"\n✅ Downloaded {len(closing_prices):,} trading days")
        print(closing_prices.tail(5))

        filename = f"{self.name1}_{self.name2}_daily_closing_prices_2y.csv"
        closing_prices.to_csv(filename)
        print(f"\n💾 Saved to: {filename}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python getPrices.py <token1> <token2>")
        print("Example: python getPrices.py btc eth")
        print("         python getPrices.py eth uni")
        print("         python getPrices.py sol fart")
        sys.exit(1)

    token1 = sys.argv[1]
    token2 = sys.argv[2]

    fetcher = CryptoPriceFetcher(token1, token2)
    fetcher.fetch_and_save()
