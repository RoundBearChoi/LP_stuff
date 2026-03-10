import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import time
import os

# ====================== CONFIG ======================
FORCE_REDOWNLOAD = False  # ← Change to True only when you want fresh data for everything
# ===================================================

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


def fetch_crypto_hourly_1year(symbol: str, api_key: str) -> tuple[pd.DataFrame, str]:
    """Smart fallback: CCCAGG → major exchanges (fixes RAIN, ADI, etc.)"""
    symbol = symbol.upper().strip()
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    
    # Try CCCAGG first, then direct exchange data (USDT pair)
    attempts = [
        ('USD', None),          # CCCAGG USD
        ('USDT', None),         # CCCAGG USDT
        ('USDT', 'Binance'),
        ('USDT', 'Bybit'),
        ('USDT', 'OKX'),
        ('USDT', 'Gate.io'),
        ('USDT', 'KuCoin'),
    ]
    
    all_data = []
    used_source = None
    
    for base, exchange in attempts:
        source_name = f"{base} CCCAGG" if exchange is None else f"{base} on {exchange}"
        print(f"   🚀 Fetching {symbol} (trying {source_name})...")
        
        all_data = []
        to_ts = int(datetime.now().timestamp())
        target_start = int((datetime.now() - timedelta(days=390)).timestamp())
        
        success = False
        for i in range(10):
            params = {
                'fsym': symbol,
                'tsym': base,
                'limit': 2000,
                'toTs': to_ts,
                'api_key': api_key.strip()
            }
            if exchange:
                params['e'] = exchange
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                raise ConnectionError(f"HTTP {response.status_code} for {symbol}")
            
            data = response.json()
            if data.get('Response') != 'Success':
                msg = data.get('Message', 'Unknown error')
                print(f"   ⚠️  {source_name}: {msg}")
                
                if "CCCAGG market does not exist" in msg and exchange is None:
                    break
                if not all_data and exchange is not None:
                    break
                raise Exception(f"API error for {symbol}: {msg}")
            
            batch = data['Data']['Data']
            if not batch:
                break
                
            all_data.extend(batch)
            
            oldest_ts = batch[0]['time']
            to_ts = oldest_ts - 1
            
            print(f"     Batch {i+1}: +{len(batch):,} records | Oldest: {datetime.fromtimestamp(oldest_ts)}")
            
            if oldest_ts < target_start:
                success = True
                break
            time.sleep(0.65)
        
        if success or all_data:
            used_source = source_name
            break
    
    if not all_data:
        raise ValueError(f"{symbol} has no hourly data on CryptoCompare (tried CCCAGG + 5 major exchanges)")
    
    df = pd.DataFrame(all_data)
    df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=365), tz='UTC')
    df = df[df['datetime'] >= cutoff].reset_index(drop=True)
    
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
    
    # ====================== ZERO-PRICE CLEANING ======================
    original_rows = len(df)
    df = df[
        (df['open'] > 0) &
        (df['high'] > 0) &
        (df['low'] > 0) &
        (df['close'] > 0)
    ].reset_index(drop=True)
    
    dropped = original_rows - len(df)
    if dropped > 0:
        print(f"   🧹 Dropped {dropped:,} zero-price rows")
    
    actual_days = (df['datetime'].max() - df['datetime'].min()).days if not df.empty else 0
    print(f"   ✅ {symbol}: {len(df):,} valid hourly candles ({actual_days} days) → {used_source}")
    
    return df, used_source


# ====================== RUN IT ======================
if __name__ == "__main__":
    print("🚀 CryptoCompare Top-100 → raw_data/ folder + GIANT combined CSV")
    print("   💡 Skips existing files (set FORCE_REDOWNLOAD = True to refresh)")
    print("   ✨ Exchange fallback + NEW WARNING for non-CCCAGG coins\n")
    
    api_key = input("Paste your CryptoCompare API key and press Enter: ").strip()
    if not api_key:
        print("❌ ERROR: API key required.")
        sys.exit(1)
    
    os.makedirs("raw_data", exist_ok=True)
    print("📁 Created/verified folder: raw_data/\n")
    
    symbols = get_top100_symbols()
    print(f"📋 Parsed {len(symbols)} coins from gecko_top_100_non_stable_coins.txt\n")
    
    all_dfs = []
    success = 0
    failed = []
    fallback_coins = []          # ← NEW: tracks coins that used an exchange
    
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i:3d}/{len(symbols)}] {symbol}")
        
        individual_file = f"raw_data/{symbol.lower()}_hourly_1year_cryptocompare.csv"
        
        # === SKIP IF FILE ALREADY EXISTS ===
        if os.path.exists(individual_file) and not FORCE_REDOWNLOAD:
            print("   📂 File already exists → loading from disk")
            try:
                df = pd.read_csv(individual_file)
                if 'datetime' in df.columns:
                    df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
                if 'symbol' not in df.columns:
                    df['symbol'] = symbol
                
                all_dfs.append(df)
                success += 1
                print(f"   ✅ Loaded existing data: {len(df):,} hourly candles\n")
                continue
            except Exception as e:
                print(f"   ⚠️  Could not load existing file ({e}). Re-downloading...\n")
        
        # === DOWNLOAD (with smart fallback) ===
        try:
            df, used_source = fetch_crypto_hourly_1year(symbol, api_key)
            df['symbol'] = symbol
            
            df.to_csv(individual_file, index=False)
            
            all_dfs.append(df)
            success += 1
            
            # Track if this coin used an exchange fallback
            if "on " in used_source:
                fallback_coins.append((symbol, used_source))
            
            print(f"   💾 Saved → raw_data/{symbol.lower()}_hourly_1year_cryptocompare.csv\n")
        except Exception as e:
            print(f"   ❌ Skipped: {e}\n")
            failed.append(symbol)
        
        time.sleep(1.8)
    
    # ====================== GIANT COMBINED CSV ======================
    if all_dfs:
        print("🔄 Creating ONE GIANT combined CSV...")
        combined = pd.concat(all_dfs, ignore_index=True)
        combined = combined[['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
        combined = combined.sort_values(['symbol', 'datetime']).reset_index(drop=True)
        
        giant_file = "top100_hourly_1year_combined.csv"
        combined.to_csv(giant_file, index=False)
        
        print(f"\n🎉 FINISHED!")
        print(f"   Giant file saved → {giant_file}")
        print(f"   Total rows: {len(combined):,} (≈ {len(combined)//success:,} hours × {success} coins)")
        print(f"   Successfully processed: {success}/{len(symbols)} coins")
    
    if failed:
        print(f"\n⚠️  Failed coins ({len(failed)}): {', '.join(failed)}")
        print("      (These coins currently have no hourly data on CryptoCompare even via exchanges)")
    
    # ====================== NEW FALLBACK WARNING ======================
    if fallback_coins:
        print("\n⚠️  WARNING: The following coins used direct exchange data (not CCCAGG aggregate):")
        for sym, src in fallback_coins:
            print(f"   • {sym} → {src}")
        print("      → Prices and volume come from that single exchange only.")
        print("      → This is completely normal for newer or low-liquidity top-100 coins.")
        print("      → Data is still 100% valid for analysis, but keep it in mind for cross-exchange comparisons.")
    
    print("\n📂 Final structure:")
    print(f"   • raw_data/          ← contains {success} individual CSVs")
    print("   • top100_hourly_1year_combined.csv  ← your main analysis file")
    print("   • get_cryptocompare_top_coins_prices_historic.py")
