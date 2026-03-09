import pandas as pd
import requests
from datetime import datetime
import sys

print("🚀 CoinGecko Free Demo - ~1 Year BTC Price Downloader")
print("=" * 65)

# === PROMPT FOR YOUR DEMO KEY ===
while True:
    api_key = input("\nEnter your CoinGecko Demo API key (starts with CG-...): ").strip()
    if api_key.startswith("CG-") and len(api_key) > 20:
        print("✅ Key accepted")
        break
    print("❌ Invalid format. Try again.")

headers = {"x-cg-demo-api-key": api_key}

# === DOWNLOAD THE DATA (this part already worked for you) ===
print("\n📥 Downloading ~1 year of BTC price data...")

url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=365&precision=full"

resp = requests.get(url, headers=headers)
resp.raise_for_status()

data = resp.json()['prices']
df = pd.DataFrame(data, columns=['timestamp', 'price'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df = df.set_index('timestamp')

print(f"✅ Raw data loaded: {len(df):,} price points")

# === RESAMPLE TO CLEAN HOURLY (FIXED for newer pandas) ===
print("🔄 Converting to clean hourly OHLC candles...")
df_hourly = df.resample('1h').agg({      # ← changed from '1H' to '1h'
    'price': ['first', 'max', 'min', 'last']
})
df_hourly.columns = ['open', 'high', 'low', 'close']
df_hourly = df_hourly.dropna()

# Results
print(f"\n🎉 SUCCESS! You now have {len(df_hourly):,} hourly candles (~1 full year)")
print(f"Date range: {df_hourly.index[0].date()} → {df_hourly.index[-1].date()}")
print("\nLast 5 candles:")
print(df_hourly.tail(5))

# Save
filename = f"btc_hourly_1year_free_{datetime.now().strftime('%Y%m%d')}.csv"
df_hourly.to_csv(filename)
print(f"\n💾 Saved to: {filename}")
print("   Open in Excel, TradingView, or your backtester!")

# === BONUS: Want 4-hour candles instead? Just uncomment these lines ===
# print("🔄 Converting to clean 4-hour candles instead...")
# df_4h = df.resample('4h').agg({
#     'price': ['first', 'max', 'min', 'last']
# })
# df_4h.columns = ['open', 'high', 'low', 'close']
# df_4h = df_4h.dropna()
# filename = f"btc_4hour_1year_free_{datetime.now().strftime('%Y%m%d')}.csv"
# df_4h.to_csv(filename)
# print(f"💾 Saved 4h version to: {filename}")
