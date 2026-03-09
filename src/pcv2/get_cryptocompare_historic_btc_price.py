import requests
import pandas as pd
from datetime import datetime, timedelta
import sys

def fetch_crypto_hourly_1year(symbol: str, api_key: str) -> pd.DataFrame:
    """
    Fetch exactly 1 year of hourly data for ANY cryptocurrency from CryptoCompare (CCCAGG).
    symbol: e.g. 'BTC', 'SOL', 'ETH', 'XRP'
    datetime column is timezone-aware UTC (+00:00).
    """
    symbol = symbol.upper().strip()
    
    if not api_key or not api_key.strip():
        print("❌ ERROR: A valid CryptoCompare API key is required.")
        sys.exit(1)
    
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    all_data = []
    
    to_ts = int(datetime.now().timestamp())
    target_start = int((datetime.now() - timedelta(days=390)).timestamp())
    
    print(f"🚀 Fetching 1 year of {symbol} hourly data from CryptoCompare...")
    print("   (Timezone-aware UTC output + fast key mode)\n")
    
    for i in range(10):
        params = {
            'fsym': symbol,
            'tsym': 'USD',
            'limit': 2000,
            'toTs': to_ts,
            'api_key': api_key.strip()
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            print(f"❌ HTTP Error: {response.status_code}")
            sys.exit(1)
        
        data = response.json()
        if data.get('Response') != 'Success':
            print("❌ API Error:", data.get('Message', 'Unknown error'))
            sys.exit(1)
        
        batch = data['Data']['Data']
        if not batch:
            break
            
        all_data.extend(batch)
        
        oldest_ts = batch[0]['time']
        to_ts = oldest_ts - 1
        
        print(f"   Batch {i+1}: +{len(batch):,} records | Oldest: {datetime.fromtimestamp(oldest_ts)}")
        
        if oldest_ts < target_start:
            break
    
    if not all_data:
        print("❌ No data received.")
        sys.exit(1)
    
    # Convert to clean DataFrame with timezone-aware UTC
    df = pd.DataFrame(all_data)
    df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    
    # Trim exactly to last 365 days
    cutoff = datetime.now() - timedelta(days=365)
    cutoff = pd.Timestamp(cutoff, tz='UTC')
    df = df[df['datetime'] >= cutoff].reset_index(drop=True)
    
    # Keep only the most useful columns
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
    
    print(f"\n✅ SUCCESS! Fetched {len(df):,} hourly candles for {symbol}")
    print(f"   Date range: {df['datetime'].min()} → {df['datetime'].max()}")
    print(f"   Latest close price: ${df['close'].iloc[-1]:,.2f}")
    print("   Timezone: UTC (fully aware with +00:00)")
    
    return df


# ====================== RUN IT ======================
if __name__ == "__main__":
    print("🔑 CryptoCompare API Key Required")
    print("   (Get your free key at: https://min-api.cryptocompare.com/)\n")
    
    # Get symbol from command line or default to BTC
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
        print(f"📈 Target coin: {symbol}")
    else:
        symbol = "BTC"
        print("ℹ️  No coin symbol provided → defaulting to BTC")
    
    api_key = input("Paste your CryptoCompare API key here and press Enter: ").strip()
    
    if not api_key:
        print("❌ ERROR: You must provide a CryptoCompare API key to run this script.")
        sys.exit(1)
    
    df = fetch_crypto_hourly_1year(symbol, api_key)
    
    filename = f'{symbol.lower()}_hourly_1year_cryptocompare.csv'
    df.to_csv(filename, index=False)
    print(f"\n💾 Saved to {filename}")
    print("   (Now with timezone-aware UTC timestamps like 2025-03-09 14:00:00+00:00)")
    
    # Quick preview
    print("\nFirst 5 rows preview:")
    print(df.head().to_string(index=False))
