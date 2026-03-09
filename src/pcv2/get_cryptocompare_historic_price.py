import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import time

def parse_symbols_from_txt(filename="top_100_non_stable_coins.txt"):
    """Extract all symbols from your text file (works with the exact format you provided)."""
    symbols = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and line[0].isdigit():   # only data rows
                parts = line.split()
                for part in parts:
                    if (part.isupper() and len(part) >= 2 
                        and not part.startswith('$') 
                        and part not in ['T', 'B', 'M', 'KST']):
                        symbols.append(part)
                        break
    return symbols


def fetch_crypto_hourly_1year(symbol: str, api_key: str) -> pd.DataFrame:
    """Fetch 1 year hourly data for any symbol (same logic as before)."""
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    all_data = []
    
    to_ts = int(datetime.now().timestamp())
    target_start = int((datetime.now() - timedelta(days=390)).timestamp())
    
    print(f"  → {symbol:<12} ", end="")
    
    for i in range(12):
        params = {
            'fsym': symbol,
            'tsym': 'USD',
            'limit': 2000,
            'toTs': to_ts,
            'api_key': api_key.strip()
        }
        
        try:
            r = requests.get(url, params=params, timeout=20)
            data = r.json()
            
            if data.get('Response') != 'Success':
                print("API error")
                return pd.DataFrame()
                
            batch = data['Data']['Data']
            if not batch:
                break
                
            all_data.extend(batch)
            to_ts = batch[0]['time'] - 1
            
            if batch[0]['time'] < target_start:
                break
        except Exception:
            print("Request failed")
            return pd.DataFrame()
    
    if not all_data:
        print("No data")
        return pd.DataFrame()
    
    # Clean DataFrame exactly like your original script
    df = pd.DataFrame(all_data)
    df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    
    # Trim exactly to last 365 days (timezone-aware UTC)
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=365), tz='UTC')
    df = df[df['datetime'] >= cutoff].reset_index(drop=True)
    
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
    
    print(f"✅ {len(df):,} candles")
    return df


# ====================== RUN IT ======================
if __name__ == "__main__":
    symbols = parse_symbols_from_txt()
    print(f"✅ Loaded {len(symbols)} coins from top_100_non_stable_coins.txt\n")
    
    api_key = input("Paste your CryptoCompare API key here and press Enter: ").strip()
    if not api_key:
        print("❌ API key required")
        sys.exit(1)
    
    dataframes = []
    success = 0
    
    print("🚀 Starting fetch for all 100 coins...\n")
    
    for i, sym in enumerate(symbols, 1):
        print(f"[{i:2d}/{len(symbols)}]", end="")
        df = fetch_crypto_hourly_1year(sym, api_key)
        
        if len(df) > 500:  # reasonable threshold
            df = df.copy()
            df['symbol'] = sym
            dataframes.append(df)
            success += 1
        else:
            print("   skipped (not enough data)")
        
        time.sleep(1.2)  # polite rate limit
    
    # === CREATE GIANT CSV ===
    if dataframes:
        print("\n📊 Combining all data into one giant CSV...")
        big_df = pd.concat(dataframes, ignore_index=True)
        big_df = big_df.sort_values(['symbol', 'datetime']).reset_index(drop=True)
        
        filename = "top100_non_stablecoins_hourly_1year_cryptocompare.csv"
        big_df.to_csv(filename, index=False)
        
        print(f"\n🎉 SUCCESS! Giant file saved:")
        print(f"   📁 {filename}")
        print(f"   📏 {len(big_df):,} total rows ({success} coins)")
        print(f"   📅 Date range: {big_df['datetime'].min()} → {big_df['datetime'].max()}")
        print(f"   🏷️  Columns: symbol + open/high/low/close + volumes")
        print("\n   Ready to load in pandas: df = pd.read_csv(filename, parse_dates=['datetime'])")
    else:
        print("\n❌ No data was collected.")
