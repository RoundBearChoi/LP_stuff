import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import time
import os   # ← NEW: for creating the raw_data folder

def get_top100_symbols(txt_file: str = "gecko_top_100_non_stable_coins.txt") -> list:
    """Robust parser — now correctly includes M (MemeCore)."""
    symbols = []
    with open(txt_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or not line[0].isdigit():
                continue
            parts = line.split()
            for i, part in enumerate(parts):
                if part.startswith("$"):
                    if i > 0:
                        symbol = parts[i-1]
                        if symbol.isalnum() and len(symbol) >= 1 and symbol.isupper():
                            if symbol not in symbols:
                                symbols.append(symbol)
                    break
    return symbols


def fetch_crypto_hourly_1year(symbol: str, api_key: str) -> pd.DataFrame:
    symbol = symbol.upper().strip()
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    all_data = []
    
    to_ts = int(datetime.now().timestamp())
    target_start = int((datetime.now() - timedelta(days=390)).timestamp())
    
    print(f"   🚀 Fetching {symbol}...")
    
    for i in range(10):
        params = {
            'fsym': symbol,
            'tsym': 'USD',
            'limit': 2000,
            'toTs': to_ts,
            'api_key': api_key.strip()
        }
        
        response = requests.get(url, params=params, timeout=30)  # increased timeout for stability
        
        if response.status_code != 200:
            raise ConnectionError(f"HTTP {response.status_code} for {symbol}")
        
        data = response.json()
        if data.get('Response') != 'Success':
            msg = data.get('Message', 'Unknown')
            if "does not exist" in msg.lower() or "invalid" in msg.lower():
                raise ValueError(f"{symbol} not supported on CryptoCompare")
            raise Exception(f"API error for {symbol}: {msg}")
        
        batch = data['Data']['Data']
        if not batch:
            break
            
        all_data.extend(batch)
        
        oldest_ts = batch[0]['time']
        to_ts = oldest_ts - 1
        
        print(f"     Batch {i+1}: +{len(batch):,} records | Oldest: {datetime.fromtimestamp(oldest_ts)}")
        
        if oldest_ts < target_start:
            break
        time.sleep(0.65)
    
    if not all_data:
        raise ValueError(f"No data for {symbol}")
    
    df = pd.DataFrame(all_data)
    df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=365), tz='UTC')
    df = df[df['datetime'] >= cutoff].reset_index(drop=True)
    
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
    
    print(f"   ✅ {symbol}: {len(df):,} hourly candles")
    return df


# ====================== RUN IT ======================
if __name__ == "__main__":
    print("🚀 CryptoCompare Top-100 → raw_data/ folder + GIANT combined CSV")
    print("   (Individual files now go into raw_data/ — giant file stays here)\n")
    
    api_key = input("Paste your CryptoCompare API key and press Enter: ").strip()
    if not api_key:
        print("❌ ERROR: API key required.")
        sys.exit(1)
    
    # Create raw_data folder automatically
    os.makedirs("raw_data", exist_ok=True)
    print("📁 Created/verified folder: raw_data/\n")
    
    symbols = get_top100_symbols()
    print(f"📋 Parsed {len(symbols)} coins from gecko_top_100_non_stable_coins.txt\n")
    
    all_dfs = []
    success = 0
    failed = []
    
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i:3d}/{len(symbols)}] {symbol}")
        try:
            df = fetch_crypto_hourly_1year(symbol, api_key)
            df['symbol'] = symbol
            
            # ← CHANGED: save to raw_data/ folder
            individual_file = f"raw_data/{symbol.lower()}_hourly_1year_cryptocompare.csv"
            df.to_csv(individual_file, index=False)
            
            all_dfs.append(df)
            success += 1
            print(f"   💾 Saved → raw_data/{symbol.lower()}_hourly_1year_cryptocompare.csv\n")
        except Exception as e:
            print(f"   ❌ Skipped: {e}\n")
            failed.append(symbol)
        
        time.sleep(1.8)
    
    # ====================== CREATE GIANT COMBINED CSV ======================
    if all_dfs:
        print("🔄 Creating ONE GIANT combined CSV...")
        combined = pd.concat(all_dfs, ignore_index=True)
        combined = combined[['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
        combined = combined.sort_values(['symbol', 'datetime']).reset_index(drop=True)
        
        giant_file = "top100_hourly_1year_combined.csv"
        combined.to_csv(giant_file, index=False)
        
        print(f"\n🎉 FINISHED!")
        print(f"   Giant file saved → {giant_file}  (in current folder)")
        print(f"   Total rows: {len(combined):,} (≈ {len(combined)//success:,} hours × {success} coins)")
        print(f"   Successfully downloaded: {success}/{len(symbols)} coins")
    
    if failed:
        print(f"\n⚠️  Failed coins ({len(failed)}): {', '.join(failed)}")
    
    print("\n📂 Final structure:")
    print(f"   • raw_data/          ← contains {success} individual CSVs")
    print("   • top100_hourly_1year_combined.csv  ← your main analysis file (stays here)")
    print("   • get_cryptocompare_top_coins_prices_historic.py")
