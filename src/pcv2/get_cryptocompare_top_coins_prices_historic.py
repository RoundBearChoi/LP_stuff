import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import time

def get_top100_symbols(txt_file: str = "gecko_top_100_non_stable_coins.txt") -> list:
    """Robust parser for your exact gecko_top_100_non_stable_coins.txt file.
    FIXED: len(symbol) >= 1 so single-letter coins like M (MemeCore) are included."""
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
                        # FIXED: changed >=2 → >=1 so "M" (MemeCore) is kept
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
        
        response = requests.get(url, params=params, timeout=15)
        
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
        time.sleep(0.65)  # gentle intra-coin delay
    
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
    print("🚀 CryptoCompare Top-100 Non-Stablecoins → Individual + GIANT Combined CSV")
    print("   (NOW INCLUDES MemeCore with symbol 'M' — 100 coins total)\n")
    
    api_key = input("Paste your CryptoCompare API key and press Enter: ").strip()
    if not api_key:
        print("❌ ERROR: API key required.")
        sys.exit(1)
    
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
            
            # Save individual file
            individual_file = f"{symbol.lower()}_hourly_1year_cryptocompare.csv"
            df.to_csv(individual_file, index=False)
            
            all_dfs.append(df)
            success += 1
            print(f"   💾 Saved {individual_file}\n")
        except Exception as e:
            print(f"   ❌ Skipped: {e}\n")
            failed.append(symbol)
        
        time.sleep(1.8)  # free-tier safety between coins
    
    # ====================== CREATE GIANT COMBINED CSV ======================
    if all_dfs:
        print("🔄 Creating ONE GIANT combined CSV with all 100 coins...")
        combined = pd.concat(all_dfs, ignore_index=True)
        combined = combined[['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
        combined = combined.sort_values(['symbol', 'datetime']).reset_index(drop=True)
        
        giant_file = "top100_hourly_1year_combined.csv"
        combined.to_csv(giant_file, index=False)
        
        print(f"\n🎉 FINISHED!")
        print(f"   Giant file saved → {giant_file}")
        print(f"   Total rows: {len(combined):,} (≈ {len(combined)//100:,} hours × {combined['symbol'].nunique()} coins)")
        print(f"   Date range: {combined['datetime'].min()} → {combined['datetime'].max()}")
        print(f"   Successfully downloaded: {success}/{len(symbols)} coins")
    
    if failed:
        print(f"\n⚠️  Failed coins ({len(failed)}): {', '.join(failed)}")
    
    print("\nAll files are ready in the current folder!")
    print("   • 100 individual CSVs (one per coin, including m_hourly_1year_cryptocompare.csv)")
    print("   • top100_hourly_1year_combined.csv ← this is your main file for analysis")
