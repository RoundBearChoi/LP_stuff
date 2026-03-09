import requests
import time
import pandas as pd
from datetime import datetime, timedelta

def fetch_btc_hourly_1year(api_key: str = None) -> pd.DataFrame:
    """
    Fetch ~1 year of hourly BTC/USD data from CryptoCompare (CCCAGG aggregate).
    Works WITHOUT any API key (with safe delays). 
    Highly recommended to use a free key for faster/unlimited use.
    """
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    all_data = []
    
    # Start from now and go back ~390 days (buffer to guarantee full year)
    to_ts = int(time.time())
    target_start = int((datetime.now() - timedelta(days=390)).timestamp())
    
    print("🚀 Fetching 1 year of BTC hourly data from CryptoCompare...")
    print("   (No API key = slower but works. ~5 requests total)\n")
    
    for i in range(10):  # safety cap, never needed
        params = {
            'fsym': 'BTC',
            'tsym': 'USD',
            'limit': 2000,
            'toTs': to_ts
        }
        if api_key:
            params['api_key'] = api_key
        
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            print(f"❌ HTTP Error: {response.status_code}")
            break
        
        data = response.json()
        if data.get('Response') != 'Success':
            print("❌ API Error:", data.get('Message'))
            break
        
        batch = data['Data']['Data']
        if not batch:
            break
            
        all_data.extend(batch)
        
        # Oldest timestamp in this batch becomes next 'toTs'
        oldest_ts = batch[0]['time']
        to_ts = oldest_ts - 1
        
        print(f"   Batch {i+1}: +{len(batch):,} records | Oldest: {datetime.fromtimestamp(oldest_ts)}")
        
        if oldest_ts < target_start:
            break
        
        # CRITICAL for free/no-key tier: respect rate limits
        time.sleep(2.0)   # 2 seconds = very safe for unauthenticated IP limits
    
    if not all_data:
        print("❌ No data received.")
        return pd.DataFrame()
    
    # Convert to clean DataFrame
    df = pd.DataFrame(all_data)
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    df = df.sort_values('time').reset_index(drop=True)
    
    # Trim exactly to last 365 days
    cutoff = datetime.now() - timedelta(days=365)
    df = df[df['datetime'] >= cutoff].reset_index(drop=True)
    
    # Keep only useful columns
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
    
    print(f"\n✅ SUCCESS! Fetched {len(df):,} hourly candles")
    print(f"   Date range: {df['datetime'].min()} → {df['datetime'].max()}")
    print(f"   Sample close price now: ${df['close'].iloc[-1]:,.2f}")
    
    return df


# ====================== RUN IT ======================
if __name__ == "__main__":
    # OPTION 1: No API key (as you requested - uses the 2-second delay)
    df = fetch_btc_hourly_1year()
    
    # OPTION 2: Uncomment and add your free key for faster runs (no delay needed)
    # df = fetch_btc_hourly_1year(api_key="YOUR_FREE_API_KEY_HERE")
    
    # Save to CSV (ready for Excel, TradingView, backtesting, etc.)
    df.to_csv('btc_hourly_1year_cryptocompare.csv', index=False)
    print("\n💾 Saved to btc_hourly_1year_cryptocompare.csv")
    
    # Quick preview
    print("\nFirst 5 rows:")
    print(df.head())
