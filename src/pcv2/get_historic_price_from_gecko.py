import pandas as pd
import requests
from datetime import datetime


class CoinGeckoBTCDailyDownloader:
    """CoinGecko Free Demo - ~1 Year BTC Daily OHLC Downloader (Real candles)."""

    def __init__(self):
        print("🚀 CoinGecko Free Demo - ~1 Year BTC Daily OHLC Downloader")
        print("=" * 65)

        self.api_key = None
        self.headers = None
        self.df_daily = None   # final daily OHLC

    def get_api_key(self):
        """Prompt user for valid CoinGecko Demo API key."""
        while True:
            api_key = input("\nEnter your CoinGecko Demo API key (starts with CG-...): ").strip()
            if api_key.startswith("CG-") and len(api_key) > 20:
                print("✅ Key accepted")
                self.api_key = api_key
                self.headers = {"x-cg-demo-api-key": api_key}
                break
            print("❌ Invalid format. Try again.")

    def download_data(self):
        """Download ~1 year of real daily OHLC candles."""
        print("\n📥 Downloading ~1 year of BTC daily OHLC data...")

        url = "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc?vs_currency=usd&days=365"

        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()

        data = resp.json()  # format: [[timestamp, open, high, low, close], ...]
        self.df_daily = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        self.df_daily['timestamp'] = pd.to_datetime(self.df_daily['timestamp'], unit='ms')
        self.df_daily = self.df_daily.set_index('timestamp')

        print(f"✅ Loaded {len(self.df_daily):,} daily OHLC candles")

    def save_results(self):
        """Print success message and save to CSV with clear CoinGecko branding."""
        print(f"\n🎉 SUCCESS! You now have {len(self.df_daily):,} daily OHLC candles (~1 full year)")
        print(f"Date range: {self.df_daily.index[0].date()} → {self.df_daily.index[-1].date()}")
        print("\nLast 5 candles:")
        print(self.df_daily.tail(5))

        # ←←← UPDATED FILENAME WITH COINGECKO FOR CLARITY ←←←
        filename = f"btc_coingecko_daily_ohlc_1year_free_{datetime.now().strftime('%Y%m%d')}.csv"
        self.df_daily.to_csv(filename)
        print(f"\n💾 Saved to: {filename}")
        print("   Open in Excel, TradingView, or your backtester!")

    def run(self):
        """Run the complete pipeline."""
        self.get_api_key()
        self.download_data()
        self.save_results()


# ====================== RUN AS SCRIPT ======================
if __name__ == "__main__":
    downloader = CoinGeckoBTCDailyDownloader()
    downloader.run()
