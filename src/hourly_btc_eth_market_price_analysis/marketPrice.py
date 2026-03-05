import yfinance as yf
import pandas as pd
import pytz


class CryptoPriceDownloader:
    """Downloads BTC & ETH hourly data, extracts exact 10:00 / 22:00 KST prices."""

    def __init__(self):
        self.kst_tz = pytz.timezone('Asia/Seoul')
        self.start_date = '2024-02-26'
        
        self.output_file = 'btc_eth_prices_kst_10am_10pm_2years.csv'
        self.btc_raw_file = 'btc_usd_hourly_raw.csv'
        self.eth_raw_file = 'eth_usd_hourly_raw.csv'

    def _download_data(self):
        print('')
        print("Downloading hourly BTC-USD & ETH-USD data...")
        btc_data = yf.download('BTC-USD', start=self.start_date, interval='1h', progress=False)
        eth_data = yf.download('ETH-USD', start=self.start_date, interval='1h', progress=False)
        return btc_data, eth_data

    def _extract_kst_prices(self, df, asset):
        """Extract rows that fall exactly on 10:00 and 22:00 KST."""
        if df.empty:
            print(f"⚠️ No data for {asset}")
            return pd.DataFrame()

        # Convert to KST
        if df.index.tz is None:
            df.index = pd.to_datetime(df.index).tz_localize('UTC')
        df = df.tz_convert(self.kst_tz).copy()

        # Exactly 10:00 and 22:00 KST
        mask = (df.index.hour.isin([10, 22])) & (df.index.minute == 0)
        filtered = df[mask].copy()

        filtered['KST_Datetime'] = filtered.index.strftime('%Y-%m-%d %H:%M KST')
        filtered['Time_of_Day'] = filtered.index.strftime('%H:%M')
        filtered['Price'] = filtered['Open']

        # CRITICAL FIXES to prevent MultiIndex bug
        filtered = filtered.reset_index(drop=True)
        
        # Force flat column names (kills any hidden MultiIndex)
        if isinstance(filtered.columns, pd.MultiIndex):
            filtered.columns = filtered.columns.get_level_values(0)
        else:
            filtered.columns = [col[0] if isinstance(col, tuple) else col for col in filtered.columns]

        return filtered[['KST_Datetime', 'Time_of_Day', 'Price', 'High', 'Low', 'Close', 'Volume']]

    def run(self):
        """Run the full pipeline."""
        btc_data, eth_data = self._download_data()

        # Save raw data
        print("\n💾 Saving raw hourly data...")
        btc_data.to_csv(self.btc_raw_file)
        eth_data.to_csv(self.eth_raw_file)
        print(f"   • Raw BTC-USD saved → {self.btc_raw_file}")
        print(f"   • Raw ETH-USD saved → {self.eth_raw_file}")

        btc_prices = self._extract_kst_prices(btc_data, 'BTC')
        eth_prices = self._extract_kst_prices(eth_data, 'ETH')

        if btc_prices.empty and eth_prices.empty:
            print("❌ Still no data. Try again in a few minutes.")
            return

        # Prepare subsets (extra safety)
        btc_subset = btc_prices[['KST_Datetime', 'Time_of_Day', 'Price']].rename(columns={'Price': 'BTC_Price'}).copy()
        eth_subset = eth_prices[['KST_Datetime', 'Price']].rename(columns={'Price': 'ETH_Price'}).copy()

        # Final MultiIndex protection
        for df in [btc_subset, eth_subset]:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

        # Merge
        combined = pd.merge(
            btc_subset,
            eth_subset,
            on='KST_Datetime',
            how='outer'
        ).sort_values('KST_Datetime').reset_index(drop=True)

        print(f"\n✅ Success! Total data points: {len(combined):,}")
        print("Columns:", combined.columns.tolist())
        print("\nLast 5 rows:")
        print(combined.tail(5).to_string(index=False))

        combined.to_csv(self.output_file, index=False)
        print(f"\n💾 Clean CSV saved to: {self.output_file}")


if __name__ == "__main__":
    downloader = CryptoPriceDownloader()
    downloader.run()
